"""
The module contains HTML parsing functions - both sync and async versions

book_urls_parser() -> list[str]: function for extracting all book URLs using Playwright.
book_parser(page, url: str, worker_id: int) -> dict | None: function for parsing single book details using Playwright,
   given a page object, book URL, and worker ID for logging purposes.
"""

import http
import asyncio
from playwright.async_api import async_playwright
from config import const, selectors


async def book_parser_async(page, url: str, worker_id: str) -> dict | None:
    """
    Parse book data from already loaded page (async version for Celery)

    Args:
        page: Playwright page object (already loaded)
        url: Book URL
        worker_id: Worker identifier for logging

    Returns:
        dict: Book data or None if parsing failed
    """
    try:
        # Extract book data from page
        # Adapt these selectors to your actual website structure

        title = await page.locator(selectors.get('title', 'h1')).first.text_content()
        price = await page.locator(selectors.get('price', '.price')).first.text_content()
        rating = await page.locator(selectors.get('rating', '.rating')).first.text_content()

        book = {
            'title': title.strip() if title else None,
            'category': selectors.get('category', 'unknown'),
            'price': price.strip() if price else None,
            'rating': rating.strip() if rating else None,
            'available': 'In stock',  # Adjust as needed
            'image_url': await page.locator(selectors.get('image', 'img')).first.get_attribute('src'),
            'description': await page.locator(selectors.get('description', '.description')).first.text_content(),
            'product_info': {},
            'url': url
        }

        return book if book.get('title') else None

    except Exception as exc:
        print(f'Worker {worker_id} Parser error: {exc}')
        return None


async def book_urls_parser_async() -> list[str]:
    """
    Extract all book URLs using async Playwright

    Returns:
        list[str]: List of book URLs
    """
    book_urls = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(const.base_url)

        current_page = 1
        while True:
            print(f'Extracting book URLs from page {current_page}')

            # Get all book links on current page
            page_urls = await page.locator(selectors.get('url_containers', 'a.book-link')).evaluate_all(
                'elements => elements.map(el => el.href)'
            )
            book_urls.extend(page_urls)

            # Check for next page
            next_button = page.locator(selectors.get('next_page', '.next'))
            if current_page == const.max_page_per_category or await next_button.count() == 0:
                break

            # Go to next page
            await next_button.click()
            await page.wait_for_load_state(state='networkidle')
            current_page += 1

        await browser.close()

    return book_urls


# Sync wrapper for main script (non-Celery usage)
def book_urls_parser() -> list[str]:
    """Sync wrapper for book_urls_parser_async"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(book_urls_parser_async())
    finally:
        loop.close()


# def book_urls_parser() -> list[str]:
#     """
#     Extract all book URLs using Playwright
#     Returns:
#         list[str]: list of book URLs
#     """
#
#     book_urls = []
#     with sync_playwright() as pw:
#         browser = pw.chromium.launch(headless=True)
#         page = browser.new_page()
#         page.goto(const.base_url)
#
#         current_page = 1
#         while True:
#             print(f'Extracting book URLs from page {current_page}')
#             # Get all book links on current page
#             page_urls = page.locator(selectors.url_containers).evaluate_all('elements => elements.map(el => el.href)')
#             book_urls.extend(page_urls)
#             # Check for next page
#             next_button = page.locator(selectors.next_page)
#             if current_page == const.max_pages or next_button.count() == 0:
#                 break
#             # Goto next page
#             next_button.click()
#             page.wait_for_load_state(state='networkidle')
#             current_page += 1
#         browser.close()
#     return book_urls


# async def book_urls_parser() -> list[str]:
#     """
#     Extract all book URLs using Playwright (async)
#     Returns:
#         list[str]: list of book URLs
#     """
#
#     book_urls = []
#     async with async_playwright() as pw:
#         browser = await pw.chromium.launch(headless=True)
#         page = await browser.new_page()
#         await page.goto(const.base_url)
#
#         current_page = 1
#         while True:
#             print(f'Extracting book URLs from page {current_page}')
#             page_urls = await page.locator(selectors.url_containers).evaluate_all(
#                 'elements => elements.map(el => el.href)'
#             )
#             book_urls.extend(page_urls)
#
#             next_button = page.locator(selectors.next_page)
#             if current_page == const.max_pages or next_button.count() == 0:
#                 break
#
#             await next_button.click()
#             await page.wait_for_load_state(state='networkidle')
#             current_page += 1
#
#         await browser.close()
#     return book_urls


# pylint: disable=too-many-locals
def book_parser(page, url: str, worker_id: int) -> dict | None:
    """
    Parsing single book details using Playwright
    Attributes:
        page (str): HTML string
        url (str): Book URL to parse
        worker_id (int): ID of the worker parsing the book
    Returns:
        dict | None: Parsed book details or None if parsing fails
    """

    result = {}
    report = ''
    # Get book page
    response = page.goto(url, timeout=10000)
    match response:
        case None:
            report = f'Worker {worker_id} failed to scrape {url}: No response'
        case response if response.status == http.HTTPStatus.NOT_FOUND:
            report = f'Worker {worker_id}: Page not found: {url}'
        case response if response.status in range(http.HTTPStatus.INTERNAL_SERVER_ERROR, 600):
            report = f'Worker {worker_id}: Server error: {response.status}'
        case response if response.status == http.HTTPStatus.OK:
            # Extract book data using Playwright selectors.
            # Title
            title = page.locator(selectors.title).inner_text()
            # Price
            price = page.locator(selectors.price).inner_text()
            # Rating
            rating_elem = page.locator(selectors.rating)
            rating = rating_elem.get_attribute('class').split()[-1]
            # Availability
            available = page.locator(selectors.available).inner_text().strip()
            # Image URL
            image_url = page.locator(selectors.image_url).get_attribute('src')
            if image_url:
                image_url = f'{const.base_url}{image_url.lstrip('../')}'
            # Description
            description_elem = page.locator(selectors.description)
            description = description_elem.inner_text() if description_elem.count() > 0 else ""
            # Product information card
            product_info = {}
            rows = page.locator(selectors.info_rows).all()
            for row in rows:
                th = row.locator('th').inner_text()
                td = row.locator('td').inner_text()
                product_info[th] = td
            # Category
            breadcrumbs = page.locator(selectors.category).all()
            category = breadcrumbs[-2].inner_text() if len(breadcrumbs) > 2 else ''
            report = f'Worker {worker_id} parsed: {title}'
            result = {
                'title': title,
                'category': category.strip(),
                'price': price,
                'rating': rating,
                'available': available,
                'image_url': image_url,
                'description': description,
                'product_info': product_info,
                'url': url
            }
    print(report)
    return result


if __name__ == '__main__':
    pass
