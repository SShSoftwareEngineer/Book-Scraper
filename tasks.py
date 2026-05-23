"""
Celery tasks for book scraping and database writing
"""

import json
from celery import Task
from celery.signals import worker_process_init, worker_process_shutdown
from playwright.sync_api import (
    sync_playwright,
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    Playwright,
    Browser,
    Page
)
import psycopg2
from psycopg2.extras import Json

from celery_app import app, cache
from config import const, db_settings
from parsers import book_parser

# Global Playwright instances (per worker process)
playwright: Playwright | None = None
browser: Browser | None = None
page: Page | None = None


@worker_process_init.connect
def setup_browser(**_kwargs):
    """Initialize Playwright browser when worker process starts"""
    global playwright, browser, page

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    print('Browser initialized')


@worker_process_shutdown.connect
def teardown_browser(**_kwargs):
    """Close Playwright browser when worker process shuts down"""
    global browser, playwright

    if browser is not None:
        browser.close()
    if playwright is not None:
        playwright.stop()

    print('Browser closed')


class DatabaseTask(Task):
    """Base task with database connection"""
    _db_connection = None
    _db_cursor = None

    @property
    def db_connection(self):
        if self._db_connection is None:
            connection_string = (
                f'dbname={db_settings.name} host={db_settings.host} '
                f'port={db_settings.port} user={db_settings.user} password={db_settings.password}'
            )
            self._db_connection = psycopg2.connect(connection_string)
        return self._db_connection

    @property
    def db_cursor(self):
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


@app.task(bind=True, max_retries=const.max_retries, default_retry_delay=5)
def parse_book(self, url: str):
    """
    Parse single book and store result in Redis cache

    Args:
        self: Celery task instance (auto-injected by bind=True)
        url: Book URL to parse

    Returns:
        str: Task ID (used as cache key)
    """
    global page

    worker_id = 'unknown'

    try:
        # Get worker index for logging
        worker_id = self.request.hostname.split('@')[0] if self.request.hostname else 'unknown'

        # Parse book
        book = book_parser(page, url, worker_id)

        if book:
            # Store in Redis cache with task_id as key
            cache_key = f'book:{self.request.id}'
            cache.set(cache_key, json.dumps(book), ex=3600)  # Expire after 1 hour
            return self.request.id

        raise ValueError(f'Failed to parse book: {url}')

    except (PlaywrightError, PlaywrightTimeoutError) as exc:
        print(f'Worker {worker_id} Playwright error: {exc}')
        raise self.retry(exc=exc)

    except Exception as exc:
        print(f'Worker {worker_id} error: {exc}')
        raise self.retry(exc=exc)


@app.task(base=DatabaseTask, bind=True)
def bulk_save_to_db(self, task_ids: list):
    """
    Save batch of books from Redis cache to PostgreSQL

    Args:
        self: Celery task instance with database connection (auto-injected)
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
            book = json.loads(book_json)

            self.db_cursor.execute("""
                                   INSERT INTO books (title, category, price, rating, available, image_url,
                                                      description, product_info, url)
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

            # Delete from cache after successful save
            cache.delete(cache_key)

        except Exception as err:
            print(f'Database write error: {err}')
            self.db_connection.rollback()
            error_count += 1

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
