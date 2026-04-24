import time
from multiprocessing import JoinableQueue, Process
import psycopg2
from psycopg2.extras import Json
from playwright.sync_api import sync_playwright
from parsers import book_parser


def worker_process(task_queue: JoinableQueue, result_queue: JoinableQueue, worker_id: int):
    """
    Worker process: launches browser, scrapes book details
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        while True:
            try:
                url = task_queue.get(timeout=5)
                if url is None:  # Poison pill
                    task_queue.task_done()
                    break
                # Scrape book details
                book = book_parser(page, url, worker_id)
                if book:
                    result_queue.put(book)
                task_queue.task_done()
            except Exception as e:
                print(f'Worker {worker_id} error: {e}')
                # Simulate crash for testing process manager
                if 'CRASH' in str(e):
                    raise
        browser.close()
    print(f'Worker {worker_id} finished')


def db_writer_process(result_queue: JoinableQueue, db_settings):
    """
    Dedicated process for writing to PostgreSQL
    """
    # Database initialization
    connection_string = (f'dbname={db_settings.name} host={db_settings.host} port={db_settings.port}'
                         f' user={db_settings.user} password={db_settings.password}')
    connect = psycopg2.connect(connection_string)
    cursor = connect.cursor()
    # Create table if not exist
    # @formatter:off
    cursor.execute("""CREATE TABLE IF NOT EXISTS books
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
    # @formatter:on
    connect.commit()

    print('Database Writer started')

    while True:
        book = result_queue.get()
        if book is None:  # Poison pill
            break

        try:
            cursor.execute("""
                           INSERT INTO books (title, category, price, rating, available, image_url, description,
                                              product_info, url)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (url) DO NOTHING
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
            connect.commit()

        except Exception as e:
            print(f'Database write Error: {e}')
            connect.rollback()

    cursor.close()
    connect.close()
    print('Database Writer finished')


class ProcessManager:
    def __init__(self, num_processes: int, task_queue: JoinableQueue, result_queue: JoinableQueue):
        self.num_processes = num_processes
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.processes = []

    def start(self):
        """Start all worker processes"""
        for i in range(self.num_processes):
            self._start_worker(i)

    def _start_worker(self, worker_id: int):
        """Start single worker process"""
        p = Process(
            target=worker_process,
            args=(self.task_queue, self.result_queue, worker_id),
            name=f'Worker-{worker_id}'
        )
        p.start()
        self.processes.append({'id': worker_id, 'process': p})
        print(f"Started Worker {worker_id} (PID: {p.pid})")

    def monitor(self):
        """Monitor workers and restart if crashed"""
        print("Process Manager monitoring started")

        while any(p['process'].is_alive() for p in self.processes):
            for worker in self.processes:
                proc = worker['process']
                worker_id = worker['id']

                if not proc.is_alive() and proc.exitcode != 0:
                    # Worker crashed
                    print(f"Worker {worker_id} crashed (exitcode: {proc.exitcode}). Restarting...")

                    # Remove old process
                    self.processes.remove(worker)

                    # Start new worker with same ID
                    self._start_worker(worker_id)

            time.sleep(1)
            if self.task_queue.empty():
                self.stop()

    def stop(self):
        """Send poison pills and wait for workers to finish"""
        for _ in range(self.num_processes):
            self.task_queue.put(None)

        # Wait for all to finish
        for worker in self.processes:
            worker['process'].join()


if __name__ == '__main__':
    pass
