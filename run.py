"""
Unified launcher for Book Scraper with Celery + Redis + Flower
Optimized for Windows + async Playwright
Uses environment variables from config.py
"""

import socket
import sys
import time
import subprocess
import signal
from pathlib import Path
from redis.exceptions import ConnectionError as RedisConnectionError  # pylint: disable=import-error
from redis import Redis  # pylint: disable=import-error
from config import redis_settings, logging_settings, flower_settings, const

# Create logs directory
Path('logs').mkdir(exist_ok=True)

# Track all started processes
processes = []


def port_is_open(host: str, port: int, timeout: int = 2) -> bool:
    """ Check if port is open """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex((host, port))
        return result == 0
    finally:
        sock.close()


def check_redis() -> bool | None:
    """
    Check if Redis is running (in Docker or locally)
    Returns True if Redis is available, False otherwise
    """
    print('Checking Redis...')
    result = None
    try:
        # Подключаемся к Redis на localhost (порт проброшен из Docker)
        client = Redis(
            host=redis_settings.host,
            port=redis_settings.port,
            socket_timeout=2,
            socket_connect_timeout=2 # type: ignore
        )
        if client.ping():
            print('Redis is running and responding\n')
            result = True
    except (RedisConnectionError, OSError) as e:
        print(f'Redis connection failed: {e}\n')
        result = False
    return result


def start_celery_worker(concurrency: int = 4) -> subprocess.Popen | None:
    """
    Start Celery worker with async support

    Args:
        concurrency: Number of worker threads (4-8 recommended for Playwright)
    Returns:
        Process object or None if failed
    """
    loglevel = logging_settings.worker
    print(f'Starting Celery Worker (concurrency={concurrency}, loglevel={loglevel})...')

    cmd = [
        'celery', '-A', 'celery_app', 'worker',
        f'--loglevel={loglevel}',
        f'--concurrency={concurrency}',
        '--pool=threads',  # Explicitly use threads for Windows compatibility
        '--logfile=logs/worker.log',
        '--time-limit=300',  # Kill task if it takes >10 minutes
        '--soft-time-limit=240',  # Warn task at 4:00 minutes
    ]

    try:
        proc = subprocess.Popen(cmd)  # pylint: disable=consider-using-with
        time.sleep(2)  # Give worker time to start

        if proc.poll() is None:  # Process still running
            print(f'Celery Worker started (PID: {proc.pid})\n')
            return proc
        print('Celery Worker failed to start\n')
        return None
    except FileNotFoundError:
        print('Celery not found. Install with: pip install celery\n')
        return None
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f'Error starting worker: {e}\n')
        return None


def start_celery_beat() -> subprocess.Popen | None:
    """
    Start Celery Beat (periodic tasks' scheduler)

    Returns:
        Process object or None if failed
    """
    loglevel = logging_settings.beat
    print(f'Starting Celery Beat (loglevel={loglevel})...')

    cmd = [
        'celery', '-A', 'celery_app', 'beat',
        f'--loglevel={loglevel}',
        '--logfile=logs/beat.log',
        '--scheduler=celery.beat:PersistentScheduler',  # Persistent scheduler
    ]

    try:
        proc = subprocess.Popen(cmd)  # pylint: disable=consider-using-with
        time.sleep(1)

        if proc.poll() is None:
            print(f'Celery Beat started (PID: {proc.pid})\n')
            return proc
        print('Celery Beat failed to start\n')
        return None
    except FileNotFoundError:
        print('Celery not found\n')
        return None
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f'Error starting beat: {e}\n')
        return None


def start_flower() -> subprocess.Popen | None:
    """
    Start Flower (web UI for task monitoring)

    Returns:
        Process object or None if failed
    """
    port = flower_settings.port
    loglevel = logging_settings.flower
    print(f'Starting Flower (http://localhost:{port}, loglevel={loglevel})...')

    cmd = [
        'celery', '-A', 'celery_app', 'flower',
        f'--port={port}',
        f'--loglevel={loglevel}',
    ]

    try:
        proc = subprocess.Popen(cmd)  # pylint: disable=consider-using-with
        time.sleep(2)

        if proc.poll() is None:
            print(f'Flower started (PID: {proc.pid})\n')
            return proc
        print('Flower failed to start\n')
        return None
    except FileNotFoundError:
        print('Flower not found. Install with: pip install flower\n')
        return None
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f'Error starting flower: {e}\n')
        return None


def run_scraper() -> int:
    """
    Run main book scraper script

    Returns:
        Exit code from book_scraper.py
    """
    print('\n' + '=' * 70)
    print('Starting book scraper...')
    print('=' * 70 + '\n')

    try:
        result = subprocess.run(
            [sys.executable, 'book_scraper.py'],
            check=False
        )
        return result.returncode
    except FileNotFoundError as e:
        print(f"Error: Скрипт 'book_scraper.py' не найден по указанному пути. [{e}]")
        return 1
    except PermissionError as err:
        print(f"Error: Нет прав на исполнение процесса. [{err}]")
        return 1
    except subprocess.SubprocessError as err:
        print(f"Error running scraper (internal subprocess error): {err}")
        return 1
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f'Error running scraper: {e}')
        return 1


def print_status() -> None:
    """Print current services status"""
    print('\n' + '=' * 70)
    print('SERVICES STATUS')
    print('=' * 70)
    print(f'Redis:          {"Running" if check_redis() else "Not running"}')
    print(f'Celery Worker: '
          f' {"Running" if len(processes) > 0 and processes[0] and processes[0].poll() is None else "Not running"}')
    print(f'Celery Beat:   '
          f' {"Running" if len(processes) > 1 and processes[1] and processes[1].poll() is None else "Not running"}')
    print(f'Flower:        '
          f' {"Running" if len(processes) > 2 and processes[2] and processes[2].poll() is None else "Not running"}')
    print('=' * 70 + '\n')

    print('Access URLs:')
    print(f'   - Flower UI:  http://localhost:{flower_settings.port}')
    print(f'   - Redis:      localhost:{redis_settings.port}')
    print('   - Logs:       ./logs/\n')


def cleanup(_signum=None, _frame=None) -> None:
    """
    Gracefully shutdown all processes
    Called on SIGINT (Ctrl+C) or SIGTERM
    """
    print('\n' + '=' * 70)
    print('SHUTTING DOWN')
    print('=' * 70)

    print('\nStopping all services...')

    # Terminate each process with timeout
    for i, proc in enumerate(processes):
        if proc and proc.poll() is None:  # Process still running
            try:
                print(f'  Stopping process {i + 1} (PID: {proc.pid})...')
                proc.terminate()

                # Wait up to 5 seconds for graceful shutdown
                try:
                    proc.wait(timeout=5)
                    print(f'Process {i + 1} stopped gracefully')
                except subprocess.TimeoutExpired:
                    print(f'Process {i + 1} did not stop, killing...')
                    proc.kill()
                    proc.wait()
                    print(f'Process {i + 1} killed')

            except OSError as err:
                print(f'Error stopping process {i + 1}: {err}')

    print('\nAll services stopped')
    print('=' * 70)
    sys.exit(0)


# pylint: disable=too-many-statements
def main():
    """ Main execution flow """

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print('\n' + '=' * 70)
    print('BOOK SCRAPER WITH CELERY + REDIS')
    print('=' * 70 + '\n')

    try:
        # Запуск сервисов
        # Step 1: Check Redis
        if not check_redis():
            print('️   Redis is not available!')
            print('   Make sure Redis is running in Docker:')
            print('   docker run -d --name redis-book-scraper -p 6379:6379 redis:8-alpine')
            print('   Or check: docker ps\n')
            sys.exit(1)

        # Step 2: Start Celery services
        worker_proc = start_celery_worker(concurrency=const.worker_count)
        if not worker_proc:
            sys.exit(1)
        processes.append(worker_proc)

        beat_proc = start_celery_beat()
        if beat_proc:
            processes.append(beat_proc)
        else:
            print('️  Beat disabled (optional)\n')

        flower_proc = start_flower()
        if flower_proc:
            processes.append(flower_proc)
        else:
            print('️  Flower disabled (optional)\n')

        # Step 3: Print status
        print_status()

        # Step 4: Run scraper
        exit_code = run_scraper()

        # Step 5: Wait for background tasks
        print('\n' + '=' * 70)
        print('WAITING FOR BACKGROUND TASKS')
        print('=' * 70)
        print('Allowing time for database writes to complete...')
        print('(This may take a few seconds)\n')

        for remaining in range(15, 0, -1):
            print(f'{remaining}s remaining...', end='\r')
            time.sleep(1)

        print('\nDone!\n')

        print('=' * 70)
        print('SCRAPING COMPLETED')
        print('=' * 70)
        print(f'Exit code: {exit_code}')
        print('\nServices still running:')
        print(f'   - Worker:  http://localhost:{flower_settings.port} (Flower UI)')
        print('   - Beat:    Running periodic tasks')
        print('   - Redis:   Running in Docker')
        print('\nPress Ctrl+C to stop all services\n')
        print('=' * 70 + '\n')

        # Keep services running until user interrupts
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass  # cleanup()
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f'\nFatal error: {e}')
    finally:
        cleanup()


if __name__ == '__main__':
    main()
