"""
The module contains model classes for representing subcategories and products in the context
of web scraping or data parsing.
"""

from dataclasses import dataclass


# pylint: disable=too-many-instance-attributes
@dataclass
class Book:
    """
    Class for representing a book object.
    """
    title: str
    category: str | None
    price: str | None
    rating: str | None
    available: str | None
    image_url: str | None
    description: str | None
    product_info: dict | None
    url: str | None


if __name__ == '__main__':
    pass
