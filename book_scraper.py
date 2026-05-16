"""
The main module contains a script for parsing book information from a website and writing it to a database using
multiprocessing. It orchestrates the entire workflow, including URL extraction, task management, and database writing.
"""

from multiprocessing import Process, JoinableQueue
from config import db_settings, const
from parsers import book_urls_parser
from process_handler import ProcessManager
from process_handler import db_writer_process


def main():
    """ Main functional execution """

    # Creating multiprocessing queues
    task_queue = JoinableQueue(maxsize=const.task_queue_maxsize)
    result_queue = JoinableQueue(maxsize=const.result_queue_maxsize)

    # Extract all book URLs
    print('Extracting book URLs...')
    book_urls = book_urls_parser()
    print(f'{len(book_urls)} book URLs extracted')

    # Fill task queue
    for url in book_urls:
        task_queue.put(url)

    # Start DB writer
    db_process = Process(
        target=db_writer_process,
        args=(result_queue, db_settings)
    )
    db_process.start()

    # Start Process Manager with workers
    manager = ProcessManager(const.process_count, task_queue, result_queue)
    manager.start()

    # Monitor workers
    manager.monitor()

    # Wait for task queue to empty
    task_queue.join()
    print('All scraping tasks completed')

    # Stop workers
    manager.stop()

    # Wait for results to be written
    result_queue.put(None)  # Stop signal for DB writer
    db_process.join()
    print('All database wright tasks completed')


if __name__ == '__main__':
    main()
