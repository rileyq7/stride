#!/usr/bin/env python
"""
Debug script to test multiple brand scrapers.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.scrapers.brand_scrapers import (
    HokaScraper,
    BrooksScraper,
    AsicsScraper,
)


async def test_scraper(scraper_class, name):
    print(f"\n{'='*60}")
    print(f"Testing {name}")
    print('='*60)

    scraper = scraper_class()

    try:
        urls = await scraper.discover_all_products()
        print(f"Discovered {len(urls)} products")

        if urls:
            print("\nFirst 5 product URLs:")
            for url in urls[:5]:
                print(f"  - {url}")

        return len(urls)
    except Exception as e:
        print(f"ERROR: {e}")
        return 0


async def main():
    print("TESTING MULTIPLE BRAND SCRAPERS")
    print("="*60)

    scrapers = [
        (HokaScraper, "Hoka"),
        (BrooksScraper, "Brooks"),
        (AsicsScraper, "ASICS"),
    ]

    results = {}

    for scraper_class, name in scrapers:
        count = await test_scraper(scraper_class, name)
        results[name] = count

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, count in results.items():
        print(f"  {name}: {count} products")


if __name__ == '__main__':
    asyncio.run(main())
