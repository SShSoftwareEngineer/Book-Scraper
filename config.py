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
    # Celery settings
    worker_count: int = int(os.getenv('WORKER_COUNT', '3'))
    max_retries: int = int(os.getenv('MAX_RETRIES', '3'))
    batch_size: int = int(os.getenv('BATCH_SIZE', '50'))
    collect_interval: int = int(os.getenv('COLLECT_INTERVAL', '10'))  # seconds


@dataclass(frozen=True)
class DBSettings:
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
db_settings = DBSettings()
redis_settings = RedisSettings()
selectors = Selectors()

if __name__ == '__main__':
    pass