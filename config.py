"""
The module contains setting classes and constants for a web scraping or data parsing
Application configuration using Pydantic v2 BaseSettings
Reads from .env file and environment variables
"""
from dataclasses import dataclass

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScraperSettings(BaseSettings):
    """ Class for storing project system settings from environment variables """
    base_url: str = Field(default='', description='Base URL for scraping')
    max_pages: int = Field(default=1, validation_alias='MAX_PAGE_PER_CATEGORY',
                           description='Maximum pages to scrape per category')
    batch_size: int = Field(default=50, description='Batch size for database writes')
    collect_interval: float = Field(default=60.0, description='Interval in seconds between automatic database writes')
    max_retries: int = Field(default=3, description='Maximum task retries')
    worker_count: int = Field(default=3, description='Worker count')

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', )


class DatabaseSettings(BaseSettings):
    """ Class for storing database settings from environment variables """
    name: str = Field(default='', description='Database name')
    host: str = Field(default='localhost', description='Database host')
    port: int = Field(default=5432, description='Database port')
    user: str = Field(default='', description='Database user')
    password: str = Field(default='', description='Database password')

    model_config = SettingsConfigDict(env_file='.env', env_prefix='DB_', env_file_encoding='utf-8', )


class RedisSettings(BaseSettings):
    """ Class for storing Redis settings """
    host: str = Field(default='localhost', description='Redis host')
    port: int = Field(default=6379, description='Redis port')
    broker_db: int = Field(default=0, description='Redis DB for task broker')
    backend_db: int = Field(default=1, description='Redis DB for task results')
    cache_db: int = Field(default=2, description='Redis DB for parsed books cache')

    model_config = SettingsConfigDict(env_file='.env', env_prefix='REDIS_', env_file_encoding='utf-8', )


class CelerySettings(BaseSettings):
    """ Class for storing celery settings """
    broker_url: str = Field(default='redis://localhost:6379/0', description='Celery broker URL')
    result_backend: str = Field(default='redis://localhost:6379/1', description='Celery result backend URL')

    model_config = SettingsConfigDict(env_file='.env', env_prefix='CELERY_', env_file_encoding='utf-8', )


class LoggingSettings(BaseSettings):
    """ Class for storing logging settings """
    level: str = Field(default='INFO', validation_alias='LOG_LEVEL',
                       description='Log level (DEBUG, INFO, WARNING, ERROR)')

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', )


class FlowerSettings(BaseSettings):
    """ Class for storing flower settings """
    port: int = Field(default=5555, validation_alias='FLOWER_PORT', description='Flower web UI port')

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', )


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
scraper_settings = ScraperSettings()
db_settings = DatabaseSettings()
redis_settings = RedisSettings()
celery_settings = CelerySettings()
logging_settings = LoggingSettings()
flower_settings = FlowerSettings()
selectors = Selectors()

# Alias for backward compatibility
const = scraper_settings

if __name__ == '__main__':
    pass
