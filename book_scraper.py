from config import db_settings, const
from multiprocessing import Process, JoinableQueue

from parsers import book_urls_parser
from process_handler import ProcessManager
from process_handler import db_writer_process


# def init_database():
#     """
#     Database initialization
#     Returns:
#         Database connection
#     """
#     connection_string = (f'dbname={db_settings.name} host={db_settings.host} port={db_settings.port}'
#                          f' user={db_settings.user} password={db_settings.password}')
#     connect = psycopg2.connect(connection_string)
#     cursor = connect.cursor()
#     # Create table if not exist
#     cursor.execute("""CREATE TABLE IF NOT EXISTS books
#                       (
#                           id           SERIAL PRIMARY KEY,
#                           title        VARCHAR(255),
#                           category     VARCHAR(255),
#                           price        VARCHAR(255),
#                           rating       VARCHAR(255),
#                           available    VARCHAR(255),
#                           image_url    VARCHAR(255),
#                           description  TEXT,
#                           product_info JSONB,
#                           url          VARCHAR(255)
#                       )
#                    """)
#     connect.commit()
#     return connect, cursor


def main():
    """
    Main execution
    """

    # db_connect, db_cursor = init_database()

    # Multiprocessing queues
    task_queue = JoinableQueue(maxsize=const.task_queue_maxsize)
    result_queue = JoinableQueue(maxsize=const.result_queue_maxsize)

    # Step 1: Extract all book URLs
    print('Extracting book URLs...')
    book_urls = book_urls_parser()
    print(f'{len(book_urls)} book URLs extracted')

    # Step 2: Fill task queue
    for url in book_urls:
        task_queue.put(url)

    # Step 3: Start DB writer
    db_process = Process(
        target=db_writer_process,
        args=(result_queue, db_settings)
    )
    db_process.start()

    # Step 4: Start Process Manager with workers
    manager = ProcessManager(const.process_count, task_queue, result_queue)
    manager.start()

    # Step 5: Monitor workers
    manager.monitor()

    # Step 6: Wait for task queue to empty
    task_queue.join()
    print('All scraping tasks completed')

    # Step 7: Stop workers
    manager.stop()

    # Step 8: Wait for results to be written
    result_queue.put(None)  # Poison pill for DB writer
    db_process.join()
    print('All database wright tasks completed')


if __name__ == '__main__':
    main()
