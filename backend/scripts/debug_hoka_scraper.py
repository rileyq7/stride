#!/usr/bin/env python
"""
Debug script to test Hoka scraper with detailed logging.
"""

import asyncio
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Enable logging
logging.basicConfig(level=logging.INFO)

from app.scrapers.brand_scrapers.hoka import HokaScraper


async def debug_hoka():
    print("=" * 70)
    print("DEBUGGING HOKA SCRAPER")
    print("=" * 70)

    scraper = HokaScraper()

    # Test fetching a single catalog page
    test_url = scraper.CATALOG_URLS[0]
    print(f"\nTesting catalog URL: {test_url}")
    print("-" * 70)

    html = await scraper._fetch_catalog_with_scroll(test_url)

    if not html:
        print("ERROR: Got no HTML back from catalog fetch!")
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

    # Look for product links
    print("\n\nLooking for product links...")

    selectors_to_try = [
        ('a[href*="/p/"]', 'Links with /p/'),
        ('a[href*="/products/"]', 'Links with /products/'),
        ('.product-tile a', 'Product tile links'),
        ('[data-testid*="product"] a', 'Product testid links'),
        ('a[href*="hoka.com"]', 'Hoka links'),
    ]

    for selector, name in selectors_to_try:
        elements = soup.select(selector)
        print(f"  {name}: {len(elements)} found")
        if elements:
            print(f"    First: {elements[0].get('href', 'no href')[:80]}")

    # Save HTML for inspection
    debug_file = Path(__file__).parent / 'debug_hoka_catalog.html'
    with open(debug_file, 'w') as f:
        f.write(html)
    print(f"\n\nSaved full HTML to: {debug_file}")


if __name__ == '__main__':
    asyncio.run(debug_hoka())
