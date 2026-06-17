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
from psycopg2.extras import Json, execute_batch  # pylint: disable=import-error
from celery_app import app, cache
from config import const, db_settings
from parsers import parse_book_page

# Thread-local storage for Playwright instances (one per thread)
_thread_local = threading.local()


async def get_browser_context():
    """Get or create Playwright browser context for current Celery worker thread."""
    context = getattr(_thread_local, 'context', None)
    if context is not None:
        return context
    playwright = None
    browser = None

    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
    except Exception:
        if browser is not None:
            await browser.close()
        if playwright is not None:
            await playwright.stop()
        for attr in ('playwright', 'browser', 'context'):
            if hasattr(_thread_local, attr):
                delattr(_thread_local, attr)
        raise

    _thread_local.playwright = playwright
    _thread_local.browser = browser
    _thread_local.context = context
    return context


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


# pylint: disable=abstract-method
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


async def scrape_book_with_browser(url: str, worker_id: str) -> dict | None:
    """
    Parse single book using async Playwright

    Args:
        url: Book URL to parse
        worker_id: Worker identifier for logging

    Returns:
        dict: Parsed book data or None if failed
    """
    page = None
    try:
        context = await get_browser_context()
        page = await context.new_page()

        # Parse book using your async parser
        book = await parse_book_page(page, url, worker_id)
        return book

    except asyncio.TimeoutError:
        print(f'Worker {worker_id} Timeout parsing: {url}')
        return None
    except Exception as err:  # pylint: disable=broad-exception-caught
        print(f'Worker {worker_id} Error parsing {url}: {err}')
        return None
    finally:
        if page:
            await page.close()


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
        book = loop.run_until_complete(scrape_book_with_browser(url, worker_id))

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
def bulk_save_to_db(self, task_ids: list[str]) -> int:
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

    batch_buffer = []
    cache_keys_to_delete = []
    error_count = 0

    for task_id in task_ids:
        cache_key = f'book:{task_id}'
        book_json = cache.get(cache_key)

        if not book_json:
            continue

        # 1. Сначала безопасно парсим JSON
        try:
            book = json.loads(book_json)
        except json.JSONDecodeError as json_err:
            error_count += 1
            print(f'Scraper data error (Invalid JSON): {json_err}')
            # Здесь мы просто пропускаем битую книгу, rollback делать не нужно
            continue

        batch_buffer.append((
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
        cache_keys_to_delete.append(cache_key)

    if not batch_buffer:
        print(f'Saved 0 books to database ({error_count} errors)')
        return 0

    # 2. Выполняем операцию с базой данных
    try:
        execute_batch(self.db_cursor, """
                                      INSERT INTO books (title, category, price, rating, available,
                                                         image_url, description, product_info, url)
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                      ON CONFLICT (url) DO NOTHING
                                      """, batch_buffer)

        self.db_connection.commit()
        if cache_keys_to_delete:
            cache.delete(*cache_keys_to_delete)
    # Перехватываем специализированные ошибки PostgreSQL
    except psycopg2.DatabaseError as db_err:
        error_count += len(batch_buffer)
        print(f'Database write error: {db_err}')
        self.db_connection.rollback()
        return 0

    saved_count = len(batch_buffer)
    print(f'Saved {saved_count} books to database ({error_count} errors)')
    return saved_count


@app.task
def collect_and_save()-> list[str]:
    """
    Periodic task: collect parsed books from Redis and save to database in batches

    Returns:
        list[str]: IDs of database write tasks
    """
    # Get all book cache keys
    pattern = 'book:*'
    book_keys = list(cache.scan_iter(match=pattern, count=100))

    if not book_keys:
        return []

    # Extract task IDs from keys
    task_ids = [key.split(':')[1] for key in book_keys]

    # Split into batches
    batch_size = const.batch_size
    batches = [task_ids[i:i + batch_size] for i in range(0, len(task_ids), batch_size)]

    print(f'Collecting {len(task_ids)} books in {len(batches)} batches')

    # Send each batch to database writer
    batch_task_ids = []
    for batch in batches:
        result = bulk_save_to_db.delay(batch)
        batch_task_ids.append(result.id)
    return batch_task_ids


if __name__ == '__main__':
    pass
