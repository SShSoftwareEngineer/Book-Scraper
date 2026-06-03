"""
Celery tasks for book scraping using async Playwright
Optimized for Windows + Redis + Celery
"""

import json
import asyncio
import threading
from celery import Task  # pylint: disable=import-error
from playwright.async_api import async_playwright  # pylint: disable=import-error
import psycopg2  # pylint: disable=import-error
from psycopg2.extras import Json  # pylint: disable=import-error
from celery_app import app, cache
from config import const, db_settings
from parsers import book_parser_async

# Thread-local storage for Playwright instances (one per thread)
_thread_local = threading.local()


def get_event_loop():
    """Get or create event loop for current thread"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


class DatabaseTask(Task):
    """ Base task with database connection """
    _db_connection = None
    _db_cursor = None

    @property
    def db_connection(self):
        """ Create database connection """
        if self._db_connection is None:
            connection_string = (
                f'dbname={db_settings.name} host={db_settings.host} '
                f'port={db_settings.port} user={db_settings.user} password={db_settings.password}'
            )
            self._db_connection = psycopg2.connect(connection_string)
        return self._db_connection

    @property
    def db_cursor(self):
        """ Create database cursor and table if needed """
        if self._db_cursor is None:
            self._db_cursor = self.db_connection.cursor()
            # Create table if not exists
            self._db_cursor.execute("""
                                    CREATE TABLE IF NOT EXISTS books
                                    (
                                        id           SERIAL PRIMARY KEY,
                                        title        VARCHAR(255),
                                        category     VARCHAR(255),
                                        price        VARCHAR(255),
                                        rating       VARCHAR(255),
                                        available    VARCHAR(255),
                                        image_url    VARCHAR(255),
                                        description  TEXT,
                                        product_info JSONB,
                                        url          VARCHAR(255) UNIQUE
                                    )
                                    """)
            self.db_connection.commit()
        return self._db_cursor


async def parse_book_async(url: str, worker_id: str) -> dict | None:
    """
    Parse single book using async Playwright

    Args:
        url: Book URL to parse
        worker_id: Worker identifier for logging

    Returns:
        dict: Parsed book data or None if failed
    """
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until='networkidle', timeout=30000)

            # Parse book using your async parser
            book = await book_parser_async(page, url, worker_id)

            await browser.close()
            return book

    except asyncio.TimeoutError:
        print(f'Worker {worker_id} Timeout parsing: {url}')
        return None
    except Exception as err:  # pylint: disable=broad-exception-caught
        print(f'Worker {worker_id} Error parsing {url}: {err}')
        return None


@app.task(bind=True, max_retries=const.max_retries, default_retry_delay=5)
def parse_book(self, url: str):
    """
    Parse single book and store result in Redis cache

    Args:
        self: Celery task instance
        url: Book URL to parse

    Returns:
        str: Task ID (used as cache key)
    """
    try:
        worker_id = self.request.hostname.split('@')[0] if self.request.hostname else 'unknown'

        # Get or create event loop for this thread
        loop = get_event_loop()

        # Run async parser in thread's event loop
        book = loop.run_until_complete(parse_book_async(url, worker_id))

        if book:
            # Store in Redis cache with task_id as key
            cache_key = f'book:{self.request.id}'
            cache.set(cache_key, json.dumps(book), ex=3600)
            print(f'Worker {worker_id} Parsed and cached: {url}')
            return self.request.id

        raise ValueError(f'Failed to parse book: {url}')

    except Exception as exc:
        print(f'Task {self.request.id} error: {exc}')
        raise self.retry(exc=exc)


@app.task(base=DatabaseTask, bind=True)
def bulk_save_to_db(self, task_ids: list):
    """
    Save batch of books from Redis cache to PostgreSQL

    Args:
        self: Celery task instance with database connection
        task_ids: List of task IDs (cache keys)

    Returns:
        int: Number of books saved
    """
    if not task_ids:
        return 0

    saved_count = 0
    error_count = 0

    for task_id in task_ids:
        cache_key = f'book:{task_id}'
        book_json = cache.get(cache_key)

        if not book_json:
            continue

        try:
            # 1. Сначала безопасно парсим JSON
            try:
                book = json.loads(book_json)
            except json.JSONDecodeError as json_err:
                print(f"Scraper data error (Invalid JSON): {json_err}")
                # Здесь мы просто пропускаем битую книгу, rollback делать не нужно
                continue

            # 2. Выполняем операцию с базой данных
            self.db_cursor.execute("""
                                   INSERT INTO books (title, category, price, rating, available,
                                                      image_url, description, product_info, url)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                   ON CONFLICT (url) DO NOTHING
                                   """, (
                                       book.get('title'),
                                       book.get('category'),
                                       book.get('price'),
                                       book.get('rating'),
                                       book.get('available'),
                                       book.get('image_url'),
                                       book.get('description'),
                                       Json(book.get('product_info')),
                                       book.get('url')
                                   ))

            self.db_connection.commit()
            saved_count += 1
            cache.delete(cache_key)

        # Перехватываем специализированные ошибки PostgreSQL
        except psycopg2.DatabaseError as db_err:
            print(f"Database write error: {db_err}")
            self.db_connection.rollback()

    print(f'Saved {saved_count} books to database ({error_count} errors)')
    return saved_count


@app.task
def collect_and_save():
    """
    Periodic task: collect parsed books from Redis and save to database in batches

    Returns:
        int: Number of batches sent to database
    """
    # Get all book cache keys
    pattern = 'book:*'
    book_keys = cache.keys(pattern)

    if not book_keys:
        return 0

    # Extract task IDs from keys
    task_ids = [key.split(':')[1] for key in book_keys]

    # Split into batches
    batch_size = const.batch_size
    batches = [task_ids[i:i + batch_size] for i in range(0, len(task_ids), batch_size)]

    print(f'Collecting {len(task_ids)} books in {len(batches)} batches')

    # Send each batch to database writer
    for batch in batches:
        bulk_save_to_db.delay(batch)

    return len(batches)


if __name__ == '__main__':
    pass
