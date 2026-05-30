"""
The main module contains a script for parsing book information from a website with Celery + Redis and writing it
to a database. It orchestrates the entire workflow, including URL extraction, task management, and database writing.
"""

import asyncio
import platform

# CRITICAL: Set event loop policy BEFORE any async code
if platform.system() == 'Windows':
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


from parsers import book_urls_parser
from tasks import parse_book, collect_and_save


def main():
    """Main execution flow"""

    # Extract all book URLs (uses async internally)
    print('Extracting book URLs...')

    try:
        book_urls: list[str] = book_urls_parser()
        print(f'✓ {len(book_urls)} book URLs extracted\n')
    except Exception as exc:
        print(f'✗ Failed to extract URLs: {exc}')
        return

    if not book_urls:
        print('No URLs found. Exiting.')
        return

    # Send parsing tasks to Celery workers
    print(f'Sending {len(book_urls)} parsing tasks to Celery workers...')
    tasks = []
    for i, url in enumerate(book_urls, 1):
        # task = parse_book(url)
        task = parse_book.delay(url)
        tasks.append(task)
        if i % 10 == 0:
            print(f'  Submitted {i}/{len(book_urls)} tasks')

    print(f'✓ All {len(tasks)} parsing tasks submitted to queue\n')

    # Wait for all parsing tasks to complete
    print(f'Waiting for all parsing tasks to complete...\n')

    completed = 0
    failed = 0

    for i, task in enumerate(tasks, 1):
        try:
            result = task.get(timeout=30)
            completed += 1

            if i % 10 == 0 or i == len(tasks):
                print(f'  Progress: {i}/{len(tasks)} tasks processed ({completed} successful)')

        except Exception as exc:
            failed += 1
            # traceback.print_exc()  # ← полный стек ошибки
            print(f'  ✗ Task {i} failed: {str(exc)[:100]}')

    print(f'\n✓ Parsing phase complete: {completed} successful, {failed} failed\n')

    # Final flush - save any remaining books in cache
    print('Flushing remaining books to database...')
    try:
        collect_and_save.delay()
        print('✓ Database write task submitted\n')
    except Exception as exc:
        print(f'✗ Failed to submit database write task: {exc}\n')

    print('Monitoring tasks via Flower:')
    print('  URL: http://localhost:5555')


if __name__ == '__main__':
    main()
