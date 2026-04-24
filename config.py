"""
The module contains setting classes and constants for a web scraping or data parsing project.

class Base(DeclarativeBase): a declarative class for creating tables in the database
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Loading settings from .env
load_dotenv()


@dataclass(frozen=True)
class ProjConst:
    """
    Class for storing project system settings from environment variables.
    """
    base_url: str = os.getenv('BASE_URL', '')
    process_count: int = int(os.getenv('PROCESS_COUNT', '3'))
    task_queue_maxsize: int = int(os.getenv('HTML_QUEUE_MAXSIZE', '300'))
    result_queue_maxsize: int = int(os.getenv('RESULT_QUEUE_MAXSIZE', '300'))
    max_page_per_category: int = int(os.getenv('MAX_PAGE_PER_CATEGORY', '1'))


@dataclass(frozen=True)
class DBSettings:
    """
    Class for storing database settings from environment variables.
    """
    name: str = os.getenv('DB_NAME', '')
    host: str = os.getenv('HOST', '')
    port: int = int(os.getenv('PORT', '5432'))
    user: str = os.getenv('USER', '')
    password: str = os.getenv('PASSWORD', '')
    batch_size: int = int(os.getenv('BATCH_SIZE', '100'))


# # pylint: disable=too-many-instance-attributes
# @dataclass(frozen=True)
# class ParsingSettings:
    """
    Class for storing settings used in the web scraping and data parsing.
    """
    # min_delay: float = float(os.getenv('MIN_DELAY', '0.2'))
    # max_delay: float = float(os.getenv('MAX_DELAY', '0.7'))
    # page_delay: float = float(os.getenv('PAGE_DELAY', '0.2'))
    # timeout_total: int = int(os.getenv('TIMEOUT_TOTAL', '30'))
    # timeout_connect: int = int(os.getenv('TIMEOUT_CONNECT', '15'))
    # timeout_sock_read: int = int(os.getenv('TIMEOUT_SOCK_READ', '20'))
    # max_concurrent_requests: int = int(os.getenv('MAX_CONCURRENT_REQUESTS', '5'))
    # max_page_per_category: int = int(os.getenv('MAX_PAGE_PER_CATEGORY', '1'))
    #
    # # Convert the category string for parsing from .env into a tuple
    # categories: tuple[str, ...] = field(default_factory=lambda: tuple(
    #     cat.strip() for cat in os.getenv('TARGET_CATEGORIES', 'DevOps').split(',') if cat.strip()
    # ))


@dataclass(frozen=True)
class Selectors:
    """
    Class for storing selectors used in the data parsing from environment variables.
    """
    category_card: str = 'div.rt-BaseCard'
    category_title: str = 'h2.rt-Heading'
    subcategory_url: str = 'a[href*="?page="]'
    product_url: str = 'a[data-discover="true"][href^="/marketplace/"]'


# Create instances of settings for use in the project
const = ProjConst()
db_settings = DBSettings()
# parsing = ParsingSettings()
selectors = Selectors()

if __name__ == '__main__':
    pass
