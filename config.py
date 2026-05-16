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
    process_count: int = int(os.getenv('PROCESS_COUNT', '3'))
    task_queue_maxsize: int = int(os.getenv('TASK_QUEUE_MAXSIZE', '300'))
    result_queue_maxsize: int = int(os.getenv('RESULT_QUEUE_MAXSIZE', '300'))
    max_page_per_category: int = int(os.getenv('MAX_PAGE_PER_CATEGORY', '1'))


@dataclass(frozen=True)
class DBSettings:
    """ Class for storing database settings from environment variables """
    name: str = os.getenv('DB_NAME', '')
    host: str = os.getenv('HOST', '')
    port: int = int(os.getenv('PORT', '5432'))
    user: str = os.getenv('USER', '')
    password: str = os.getenv('PASSWORD', '')
    # batch_size: int = int(os.getenv('BATCH_SIZE', '100'))


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

    category_title: str = 'strong'


# Create instances of settings for use in the project
const = ProjConst()
db_settings = DBSettings()
selectors = Selectors()

if __name__ == '__main__':
    pass
