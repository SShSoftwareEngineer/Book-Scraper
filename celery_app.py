"""
Celery application configuration optimized for Windows + async Playwright
Uses Pydantic BaseSettings for environment variables
"""

import os
import asyncio
import platform

# CRITICAL: Set event loop policy BEFORE any Playwright imports
if platform.system() in ['Windows', 'win32']:
    # TODO: Windows async subprocess support - deprecated since Python 3.14; will be removed in Python 3.16.
    # Remove when Playwright supports Windows without ProactorEventLoopPolicy
    import warnings

    with warnings.catch_warnings():  # type: ignore
        warnings.simplefilter("ignore", category=DeprecationWarning)
        # pylint: disable=deprecated-class
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())  # type: ignore[attr-defined]

from celery import Celery  # pylint: disable=wrong-import-position, disable=import-error
import redis  # pylint: disable=wrong-import-position, disable=import-error
from config import redis_settings, scraper_settings  # pylint: disable=wrong-import-position

# Initialize Celery app
app = Celery('book_scraper')

# Windows-specific configuration
if platform.system() in ['Windows', 'win32']:
    os.environ['FORKED_BY_MULTIPROCESSING'] = '1'

# Main Celery configuration
app.conf.update(
    # Broker and backend from environment
    broker_url=f'redis://{redis_settings.host}:{redis_settings.port}/{redis_settings.broker_db}',
    result_backend=f'redis://{redis_settings.host}:{redis_settings.port}/{redis_settings.backend_db}',
    include=['tasks'],

    # Serialization
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],

    # Timezone
    timezone='UTC',
    enable_utc=True,

    # Task configuration
    result_expires=3600,  # Results expire after 1 hour
    worker_prefetch_multiplier=1,  # Take one task at a time
    task_acks_late=True,  # Acknowledge task after completion
    task_reject_on_worker_lost=True,  # Requeue if worker dies

    # Task timeout settings
    task_time_limit=600,  # Kill task if it takes >10 minutes
    task_soft_time_limit=550,  # Warn task at 9:10 minutes

    # Worker pool - use 'threads' for Windows + async compatibility
    worker_pool='threads' if platform.system() in ['Windows', 'win32'] else 'prefork',
    worker_max_tasks_per_child=100,

    # Periodic tasks schedule
    beat_schedule={
        'collect-and-save-books': {
            'task': 'tasks.collect_and_save',
            'schedule': scraper_settings.collect_interval,
        },
    },
)

# Redis cache client (for storing parsed books)
cache = redis.Redis(
    host=redis_settings.host,
    port=redis_settings.port,
    db=redis_settings.cache_db,
    decode_responses=True  # type: ignore   # Auto decode bytes to strings
)

# redis_url = f"redis://{redis_settings.host}:{redis_settings.port}/{redis_settings.cache_db}?decode_responses=True"
# cache = redis.Redis.from_url(redis_url)


if __name__ == '__main__':
    pass
