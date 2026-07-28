import socket


def port_is_open(host: str, port: int, timeout: int = 2) -> bool:
    """ Check if port is open """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex((host, port))
        return result == 0
    finally:
        sock.close()


# # Sync wrapper for main script (non-Celery usage)
# def book_urls_parser() -> list[str]:
#     """Sync wrapper for book_urls_parser_async"""
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     try:
#         return loop.run_until_complete(book_urls_parser_async())
#     finally:
#         loop.close()


# url = (f'redis://{redis_settings.host}:{redis_settings.port}?'
#        f'socket_timeout=2&socket_connect_timeout=2&decode_responses=True')
# client = Redis.from_url(url)

# redis_url = f"redis://{redis_settings.host}:{redis_settings.port}/{redis_settings.cache_db}?decode_responses=True"
# cache = redis.Redis.from_url(redis_url)


# Sync wrapper for main script (non-Celery usage)
# pylint: disable=too-many-locals
def book_parser(page, url: str, worker_id: int) -> dict | None:
    """
    Parsing single book details using Playwright (non-Celery usage)
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
