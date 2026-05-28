"""
Unified launcher for book scraper with Celery
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path

from redis import Redis

from config import redis_settings

# Создаём директорию для логов
Path('logs').mkdir(exist_ok=True)

# Список процессов для отслеживания
processes = []


def start_redis():
    """Start Redis if not running"""
    print('Checking Redis...')
    try:
        # Подключаемся к Redis на localhost (порт проброшен из Docker)
        client = Redis(host=redis_settings.host, port=redis_settings.port, socket_timeout=2)
        # Метод ping() отправит PONG и вернет True, если всё ок
        if client.ping():
            print('✓ Redis already running')
            return True
    except ConnectionError as err:
        print(f'Error: Redis is not responding. {err}')


    # try:
    #     result = subprocess.run(['redis-cli', 'ping'],
    #                             capture_output=True,
    #                             text=True,
    #                             timeout=2)
    #     if 'PONG' in result.stdout:
    #         print('✓ Redis already running')
    #         return None
    # except (subprocess.TimeoutExpired, FileNotFoundError) as err:
    #     print(f'Error: {err}')
    #     pass

    # print('Starting Redis...')
    # if sys.platform == 'win32':
    #     proc = subprocess.Popen(['redis-server'])
    # else:
    #     proc = subprocess.Popen(['redis-server', '--daemonize', 'yes'])
    #
    # time.sleep(2)
    # return proc
    return None

def start_celery_worker():
    """Start Celery worker"""
    print('Starting Celery Workers...')
    proc = subprocess.Popen([
        'celery', '-A', 'celery_app', 'worker',
        '--loglevel=DEBUG',
        # '--loglevel=info',
        '--concurrency=3',
        '--logfile=logs/worker.log'
    ])
    return proc


def start_celery_beat():
    """Start Celery beat"""
    print('Starting Celery Beat...')
    proc = subprocess.Popen([
        'celery', '-A', 'celery_app', 'beat',
        '--loglevel=info',
        '--logfile=logs/beat.log'
    ])
    return proc


def start_flower():
    """Start Flower monitoring"""
    print('Starting Flower (http://localhost:5555)...')
    proc = subprocess.Popen([
        'celery', '-A', 'celery_app', 'flower',
        '--port=5555'
    ])
    return proc


def run_scraper():
    """Run main scraper script"""
    print('\n' + '=' * 50)
    print('Starting book scraper...')
    print('=' * 50 + '\n')

    result = subprocess.run([sys.executable, 'book_scraper.py'])
    return result.returncode


def cleanup(signum=None, frame=None):
    """Stop all processes"""
    print('\nStopping all services...')

    for proc in processes:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    print('All services stopped')
    sys.exit(0)


def main():
    """Main execution"""
    # Регистрируем обработчик сигналов
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print('=' * 50)
    print('Book Scraper with Celery')
    print('=' * 50 + '\n')

    try:
        # Запуск сервисов
        redis_proc = start_redis()
        # if redis_proc:
        #     processes.append(redis_proc)

        processes.append(start_celery_worker())
        time.sleep(2)

        processes.append(start_celery_beat())
        time.sleep(1)

        processes.append(start_flower())
        time.sleep(3)

        # Запуск скрипта
        exit_code = run_scraper()

        print('\n' + '=' * 50)
        print(f'Scraping completed with exit code: {exit_code}')
        print('=' * 50)

        # Даём время на финальный flush
        print('\nWaiting for final database writes...')
        time.sleep(15)

    except Exception as e:
        print(f'Error: {e}')
    finally:
        cleanup()


if __name__ == '__main__':
    main()