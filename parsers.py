import http

from playwright.sync_api import sync_playwright

from config import const


def book_urls_parser() -> list[str]:
    """
    Extract all book URLs using Playwright
    """

    book_urls = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto('https://books.toscrape.com/')

        current_page = 1
        while True:
            print(f'Extracting book URLs from page {current_page}')

            # Get all book links on current page
            page_urls = page.locator('.image_container a').evaluate_all('elements => elements.map(el => el.href)')
            book_urls.extend(page_urls)
            # Check for next page
            next_button = page.locator('.next a')
            if current_page == const.max_page_per_category or next_button.count() == 0:
                break
            # Goto next page
            next_button.click()
            page.wait_for_load_state(state='networkidle')
            current_page += 1
        browser.close()
    return book_urls


def book_parser(page, url: str, worker_id: int) -> dict | None:
    """
    Parsing single book details using Playwright
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
            title = page.locator('h1').inner_text()
            # Price
            price = page.locator('.product_main .price_color').inner_text()
            # Rating
            rating_elem = page.locator('.product_main .star-rating')
            rating = rating_elem.get_attribute('class').split()[-1]
            # Availability
            available = page.locator('.product_main .availability').inner_text().strip()
            # Image URL
            image_url = page.locator('.item.active img').get_attribute('src')
            if image_url:
                image_url = f'https://books.toscrape.com/{image_url.lstrip('../')}'
            # Description
            description_elem = page.locator('#product_description ~ p')
            description = description_elem.inner_text() if description_elem.count() > 0 else ""
            # Product information card
            product_info = {}
            rows = page.locator('table.table-striped tr').all()
            for row in rows:
                th = row.locator('th').inner_text()
                td = row.locator('td').inner_text()
                product_info[th] = td
            # Category
            breadcrumbs = page.locator('.breadcrumb li').all()
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
