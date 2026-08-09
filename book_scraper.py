"""
The main module contains a script for parsing book information from a website with Celery + Redis and writing it
to a database. It orchestrates the entire workflow, including URL extraction, task management, and database writing.
"""

import argparse
import asyncio
import logging
import platform
import subprocess
import sys
import time
from pathlib import Path
from config import const

from celery import current_app
from celery.exceptions import TimeLimitExceeded, SoftTimeLimitExceeded

# CRITICAL: Set event loop policy BEFORE any async code
if platform.system() in ['Windows', 'win32']:
    # TODO: Windows async subprocess support - deprecated since Python 3.14; will be removed in Python 3.16.
    # Remove when Playwright supports Windows without ProactorEventLoopPolicy
    import warnings

    with warnings.catch_warnings():  # type: ignore
        warnings.simplefilter("ignore", category=DeprecationWarning)
        # pylint: disable=deprecated-class
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())  # type: ignore[attr-defined]

from celery.result import AsyncResult  # pylint: disable=wrong-import-position, disable=import-error
from config import logging_settings  # pylint: disable=wrong-import-position
from parsers import book_urls_parser  # pylint: disable=wrong-import-position
from tasks import parse_book, collect_and_save  # pylint: disable=wrong-import-position
from celery_app import app  # pylint: disable=wrong-import-position

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for scraper logging."""
    parser = argparse.ArgumentParser(description='Run book scraper and wait for Celery tasks.')
    parser.add_argument(
        '--loglevel',
        default=logging_settings.scraper,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level for the scraper process.',
    )
    parser.add_argument(
        '--logfile',
        default=None,
        help='Optional file path for scraper logs.',
    )
    return parser.parse_args()


def configure_logging(loglevel: str, logfile: str | None = None) -> None:
    """Configure console and optional file logging for this process."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if logfile:
        log_path = Path(logfile)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding='utf-8'))

    logging.basicConfig(
        level=getattr(logging, loglevel.upper(), logging.INFO),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=handlers,
        force=True,
    )


def wait_for_queue_empty(timeout=120, check_interval=10):
    """ Wait until task queue is empty """
    start_time = time.time()

    while time.time() - start_time < timeout:
        # Проверь количество задач в очереди
        inspect = current_app.control.inspect()
        active = inspect.active()

        if not active or all(not tasks for tasks in active.values()):
            return True

        time.sleep(check_interval)

    print(f'Timeout after {timeout}s')
    return False


def main():
    """Main execution flow"""
    args = parse_args()
    configure_logging(args.loglevel, args.logfile)

    # Extract all book URLs (uses async internally)
    logger.info('Extracting book URLs...')

    try:
        book_urls: list[str] = book_urls_parser()  # type: ignore[annotation-unchecked]
        logger.info('%s book URLs extracted', len(book_urls))
    except (asyncio.TimeoutError, asyncio.CancelledError) as err:
        logger.error('Failed to extract URLs: %s', err)
        return
    except Exception as err:  # pylint: disable=broad-exception-caught
        logger.exception('Failed to extract URLs: %s', err)
        return

    if not book_urls:
        logger.warning('No URLs found. Exiting.')
        return

    # Send parsing tasks to Celery workers
    logger.info('Sending %s parsing tasks to Celery workers...', len(book_urls))
    tasks = []
    for i, url in enumerate(book_urls, 1):
        # task = parse_book(url)
        task = parse_book.delay(url)
        tasks.append(task)
        if i % 10 == 0:
            logger.info('Submitted %s/%s tasks', i, len(book_urls))

    logger.info('All %s parsing tasks submitted to queue', len(tasks))

    # Wait for all parsing tasks to complete
    logger.info('Waiting for all %s parsing tasks to complete...', len(book_urls))

    completed = 0
    failed = 0

    for i, task in enumerate(tasks, 1):
        try:
            task.get(timeout=30)
            completed += 1

            if i % 10 == 0 or i == len(tasks):
                logger.info('Progress: %s/%s tasks processed (%s successful)', i, len(tasks), completed)

        except Exception as exc:  # pylint: disable=broad-exception-caught
            failed += 1
            # traceback.print_exc() # полный стек ошибки
            logger.error('Task %s failed: %s', i, str(exc)[:100])

    logger.info('Parsing phase complete: %s successful, %s failed', completed, failed)

    # Final flush - save any remaining books in cache
    logger.info('Flushing remaining books to database...')
    try:
        flush_task = collect_and_save.delay()
        batch_task_ids = flush_task.get(timeout=60)

        for task_id in batch_task_ids:
            AsyncResult(task_id, app=app).get(timeout=60)

        logger.info('Database write completed')
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception('Database write failed or timed out: %s', exc)

    logger.info('Monitoring tasks via Flower: http://localhost:5555')

    print('Flushing remaining books to database...')
    flush_task = collect_and_save.delay()

    # Дождись завершения flush_task (не полагаясь на beat)
    try:
        flush_task.get(timeout=const.services_stop_timeout)
        print('Final flush completed')
    except (TimeLimitExceeded, SoftTimeLimitExceeded) as e:
        print(f'⚠️ Task timeout: {e}')

    # Ждем завершения всех задач
    if wait_for_queue_empty(timeout=const.services_stop_timeout, check_interval=const.task_check_timeout):
        if Path('/.dockerenv').exists():
            print('\n' + '=' * 70)
            print('✅ SCRAPING DEMONSTRATION COMPLETE')
            print('=' * 70)
            print('\nTo stop all services, run from your host:')
            print('  docker-compose down')
        logger.info('All tasks completed.')


if __name__ == '__main__':
    main()
