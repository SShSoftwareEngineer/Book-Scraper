"""
The module contains setting classes and constants for a web scraping or data parsing project.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Loading settings from .env
load_dotenv()


@dataclass(frozen=True)
class ProjConst:
    """ Class for storing project system settings from environment variables """
    base_url: str = os.getenv('BASE_URL', '')
    max_page_per_category: int = int(os.getenv('MAX_PAGE_PER_CATEGORY', '1'))
    batch_size: int = int(os.getenv('BATCH_SIZE', '50'))
    collect_interval: int = int(os.getenv('COLLECT_INTERVAL', '10'))  # in seconds
    worker_count: int = int(os.getenv('WORKER_COUNT', '3'))


@dataclass(frozen=True)
class DatabaseSettings:
    """ Class for storing database settings from environment variables """
    name: str = os.getenv('DB_NAME', '')
    host: str = os.getenv('HOST', '')
    port: int = int(os.getenv('PORT', '5432'))
    user: str = os.getenv('USER', '')
    password: str = os.getenv('PASSWORD', '')


@dataclass(frozen=True)
class RedisSettings:
    """ Class for storing Redis settings """
    host: str = os.getenv('REDIS_HOST', 'localhost')
    port: int = int(os.getenv('REDIS_PORT', '6379'))
    broker_db: int = int(os.getenv('REDIS_BROKER_DB', '0'))
    backend_db: int = int(os.getenv('REDIS_BACKEND_DB', '1'))
    cache_db: int = int(os.getenv('REDIS_CACHE_DB', '2'))


@dataclass(frozen=True)
class CelerySettings:
    """ Class for storing celery settings """
    broker_url: str = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    result_backend: str = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')


@dataclass(frozen=True)
class LoggingSettings:
    """ Class for storing logging settings """
    level: str = os.getenv('LOG_LEVEL', 'INFO')


@dataclass(frozen=True)
class FlowerSettings:
    """ Class for storing flower settings """
    port: int = int(os.getenv('FLOWER_PORT', '5555'))


# pylint: disable=too-many-instance-attributes
@dataclass(frozen=True)
class Selectors:
    """ Class for storing selectors used in the data parsing from environment variables """
    url_containers: str = '.image_container a'
    next_page: str = '.next a'
    title: str = 'h1'
    price: str = '.product_main .price_color'
    rating: str = '.product_main .star-rating'
    available: str = '.product_main .availability'
    image_url: str = '.item.active img'
    description: str = '#product_description ~ p'
    info_rows: str = 'table.table-striped tr'
    category: str = '.breadcrumb li'


# Create instances of settings for use in the project
const = ProjConst()
db_settings = DatabaseSettings()
redis_settings = RedisSettings()
celery_settings = CelerySettings()
logging_settings = LoggingSettings()
flower_settings = FlowerSettings()
selectors = Selectors()

if __name__ == '__main__':
    pass
