#!/usr/bin/env python
"""
Test Running Warehouse for reviews.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


TEST_URLS = [
    "https://www.runningwarehouse.com/Brooks_Ghost_16/descpage-BGH16M1.html",
    "https://www.runningwarehouse.com/HOKA_Clifton_9/descpage-HCLI9M2.html",
]


async def test_rw_reviews():
    print("=" * 70)
    print("RUNNING WAREHOUSE REVIEW TEST")
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
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(3)

                # Scroll to reviews
                for _ in range(5):
                    await page.evaluate('window.scrollBy(0, 600)')
                    await asyncio.sleep(0.5)

                html = await page.content()
                soup = BeautifulSoup(html, 'lxml')

                # Check for reviews
                print("\n--- Looking for review elements ---")

                selectors = [
                    ('#reviews', 'reviews id'),
                    ('.review', 'review class'),
                    ('.pr-review', 'PowerReviews'),
                    ('.bv-review', 'Bazaarvoice'),
                    ('[class*="review"]', 'class contains review'),
                    ('[id*="review"]', 'id contains review'),
                    ('[class*="Review"]', 'class contains Review'),
                ]

                for selector, name in selectors:
                    elements = soup.select(selector)
                    if elements:
                        print(f"  ✓ {name}: {len(elements)} elements")
                        if elements:
                            text = elements[0].get_text(strip=True)[:150]
                            print(f"    Sample: {text}...")

                # Look for review count
                text = soup.get_text()
                import re
                count_match = re.search(r'(\d+)\s+reviews?', text.lower())
                if count_match:
                    print(f"\n  Page mentions: {count_match.group(0)}")

                # Check for ratings/stars
                print("\n--- Rating elements ---")
                ratings = soup.select('[class*="star"], [class*="rating"], .pr-snippet')
                for r in ratings[:5]:
                    txt = r.get_text(strip=True)[:50]
                    print(f"  {r.name} class={r.get('class', [])[:2]} text={txt}")

            except Exception as e:
                print(f"  ERROR: {e}")

            finally:
                await page.close()

        await browser.close()


if __name__ == '__main__':
    asyncio.run(test_rw_reviews())
