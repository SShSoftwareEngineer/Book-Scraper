"""
The main module contains a script for parsing book information from a website and writing it to a database using
Celery. It orchestrates the entire workflow, including URL extraction, task management, and database writing.
"""

from parsers import book_urls_parser
from tasks import parse_book, collect_and_save


def main():
    """Main execution flow"""

    # Extract all book URLs
    print('Extracting book URLs...')
    book_urls = book_urls_parser()
    print(f'{len(book_urls)} book URLs extracted')

    # Send parsing tasks to Celery parsing workers
    print('Sending tasks to parsing workers...')
    tasks = []
    for url in book_urls:
        task = parse_book.delay(url)
        tasks.append(task)

    print(f'{len(tasks)} parsing tasks sent to Celery')

    # Wait for all parsing tasks to complete
    print('Waiting for all parsing tasks to complete...')
    completed = 0
    for task in tasks:
        try:
            task.get(timeout=300)  # Wait max 5 minutes per task
            completed += 1
            if completed % 10 == 0:
                print(f'{completed}/{len(tasks)} tasks completed')
        except Exception as exc:
            print(f'Task failed: {exc}')

    print(f'All parsing tasks completed: {completed}/{len(tasks)}')

    # Final flush - save any remaining books in cache
    print('Flushing remaining books to database...')
    collect_and_save.delay()

    print('Done! Check Flower dashboard for details.')


if __name__ == '__main__':
    main()
