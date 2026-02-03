#!/usr/bin/env python
"""
Debug script to test Nike scraper catalog discovery.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.scrapers.brand_scrapers.nike import NikeScraper


async def debug_nike():
    print("=" * 70)
    print("DEBUGGING NIKE SCRAPER")
    print("=" * 70)

    scraper = NikeScraper()

    # Test fetching a single catalog page
    test_url = 'https://www.nike.com/w/mens-running-shoes-37v7jznik1zy7ok'
    print(f"\nTesting catalog URL: {test_url}")
    print("-" * 70)

    html = await scraper._fetch_catalog_with_scroll(test_url)

    if not html:
        print("ERROR: Got no HTML back from catalog fetch!")
        print("This likely means:")
        print("  1. Nike is blocking the request (bot detection)")
        print("  2. The page failed to load")
        print("  3. Playwright had an issue")
        return

    print(f"Got HTML response: {len(html)} characters")

    # Check what's in the HTML
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'lxml')

    # Check for common block indicators
    page_text = soup.get_text().lower()
    if 'access denied' in page_text:
        print("\nWARNING: Page contains 'access denied' - likely blocked!")
    if 'captcha' in page_text:
        print("\nWARNING: Page contains 'captcha' - bot detection triggered!")
    if 'verify you are human' in page_text:
        print("\nWARNING: Page wants human verification!")

    # Look for product links
    print("\n\nLooking for product links with '/t/' in href...")
    product_links = soup.select('a[href*="/t/"]')
    print(f"Found {len(product_links)} links with /t/ in href")

    if product_links:
        print("\nFirst 5 product links:")
        for link in product_links[:5]:
            href = link.get('href', '')
            print(f"  - {href}")

    # Try alternative selectors
    print("\n\nTrying alternative selectors...")

    selectors_to_try = [
        ('a[href*="/t/"]', 'Links with /t/'),
        ('[data-testid="product-card"] a', 'Product card links'),
        ('.product-card a', 'Product card class links'),
        ('a[href*="/product/"]', 'Links with /product/'),
        ('[class*="ProductCard"] a', 'ProductCard class links'),
        ('a[href*="nike.com/t/"]', 'Full Nike product URLs'),
    ]

    for selector, name in selectors_to_try:
        elements = soup.select(selector)
        print(f"  {name}: {len(elements)} found")

    # Save HTML for inspection
    debug_file = Path(__file__).parent / 'debug_nike_catalog.html'
    with open(debug_file, 'w') as f:
        f.write(html)
    print(f"\n\nSaved full HTML to: {debug_file}")
    print("You can open this in a browser to inspect what the scraper received.")

    # Now try the full discovery
    print("\n\n" + "=" * 70)
    print("RUNNING FULL PRODUCT DISCOVERY")
    print("=" * 70)

    urls = await scraper.discover_all_products()
    print(f"\nTotal products discovered: {len(urls)}")

    if urls:
        print("\nFirst 10 product URLs:")
        for url in urls[:10]:
            print(f"  - {url}")


if __name__ == '__main__':
    asyncio.run(debug_nike())
