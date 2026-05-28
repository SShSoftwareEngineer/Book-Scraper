"""
Celery application configuration and setup
"""
import asyncio
import platform

if platform.system() == 'Windows':
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import os
from celery import Celery
import redis
from config import redis_settings, const

# Celery app
app = Celery('book_scraper')

if platform.system() == 'Windows':
    os.environ['FORKED_BY_MULTIPROCESSING'] = '1'

# Celery configuration
if platform.system() == 'Windows':
    app.conf.update(
        worker_pool='solo',
        # asyncio_mode='strict',
    )
app.conf.update(
    broker_url=f'redis://{redis_settings.host}:{redis_settings.port}/{redis_settings.broker_db}',
    result_backend=f'redis://{redis_settings.host}:{redis_settings.port}/{redis_settings.backend_db}',
    include=['tasks'],
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,

    result_expires=3600,  # Results expire after 1 hour
    worker_prefetch_multiplier=1,  # Take one task at a time
    task_acks_late=True,  # Acknowledge task after completion
    task_reject_on_worker_lost=True,  # Requeue if worker dies

    # Periodic tasks schedule
    beat_schedule={
        'collect-and-save-books': {
            'task': 'tasks.collect_and_save',
            'schedule': float(const.collect_interval),
        },
    },
)

# Redis cache client (for storing parsed books)
cache = redis.Redis(
    host=redis_settings.host,
    port=redis_settings.port,
    db=redis_settings.cache_db,
    decode_responses=True  # Auto decode bytes to strings
)

if __name__ == '__main__':
    pass
