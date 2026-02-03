#!/usr/bin/env python
"""
Test Road Runner Sports scraper for reviews.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


# Test URLs
TEST_URLS = [
    "https://www.roadrunnersports.com/rrs/products/GHT01M/brooks-ghost-16/",
    "https://www.roadrunnersports.com/rrs/products/HCL09M/hoka-clifton-9/",
]


async def test_road_runner():
    print("=" * 70)
    print("ROAD RUNNER SPORTS REVIEW TEST")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        )

        for url in TEST_URLS:
            print(f"\n{'=' * 70}")
            print(f"Testing: {url}")
            print("=" * 70)

            page = await context.new_page()

            try:
                await page.goto(url, wait_until='networkidle', timeout=60000)

                # Dismiss popups
                try:
                    close_btn = page.locator('button[aria-label="Close"], .close-modal, [class*="close"]')
                    if await close_btn.first.is_visible(timeout=3000):
                        await close_btn.first.click()
                        await asyncio.sleep(1)
                except:
                    pass

                # Scroll down
                print("Scrolling...")
                for _ in range(8):
                    await page.evaluate('window.scrollBy(0, 500)')
                    await asyncio.sleep(0.5)

                await asyncio.sleep(2)

                html = await page.content()
                soup = BeautifulSoup(html, 'lxml')

                # Check for reviews
                print("\n--- Looking for review elements ---")

                selectors = [
                    ('.pr-review', 'PowerReviews'),
                    ('.pr-rd-review-wrapper', 'PowerReviews wrapper'),
                    ('.bv-content-item', 'Bazaarvoice'),
                    ('[id*="reviews"]', 'ID with reviews'),
                    ('[class*="review"]', 'Class with review'),
                    ('[data-testid*="review"]', 'data-testid review'),
                ]

                for selector, name in selectors:
                    elements = soup.select(selector)
                    if elements:
                        print(f"  ✓ {name}: {len(elements)} elements")

                        # Sample first one
                        elem = elements[0]
                        text = elem.get_text(strip=True)[:200]
                        print(f"    Sample text: {text[:100]}...")

                # Look for review count in page
                text = soup.get_text()
                import re
                count_match = re.search(r'(\d+)\s+reviews?', text.lower())
                if count_match:
                    print(f"\n  Page mentions: {count_match.group(0)}")

                # Check for rating stars
                print("\n--- Rating elements ---")
                ratings = soup.select('[class*="star"], [class*="rating"], [class*="Star"]')
                for r in ratings[:5]:
                    print(f"  {r.name} class={r.get('class', [])[:3]}")

            except Exception as e:
                print(f"  ERROR: {e}")

            finally:
                await page.close()

        await browser.close()

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    asyncio.run(test_road_runner())
