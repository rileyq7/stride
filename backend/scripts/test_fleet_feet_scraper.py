#!/usr/bin/env python
"""
Test Fleet Feet scraper against live site.
Verifies CSS selectors and review extraction.
"""

import sys
import time
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


# Test product URLs (popular running shoes)
TEST_URLS = [
    "https://www.fleetfeet.com/products/brooks-ghost-16-mens",
    "https://www.fleetfeet.com/products/hoka-clifton-9-mens",
    "https://www.fleetfeet.com/products/asics-gel-nimbus-26-mens",
]


async def test_fleet_feet():
    print("=" * 70)
    print("FLEET FEET SCRAPER TEST")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
        )

        # Stealth
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        for url in TEST_URLS:
            print(f"\n{'=' * 70}")
            print(f"Testing: {url}")
            print("=" * 70)

            page = await context.new_page()

            try:
                await page.goto(url, wait_until='networkidle', timeout=60000)

                # Dismiss cookie banner if present
                try:
                    accept_btn = page.locator('button:has-text("Accept"), #onetrust-accept-btn-handler')
                    if await accept_btn.first.is_visible(timeout=2000):
                        await accept_btn.first.click()
                        await asyncio.sleep(1)
                except:
                    pass

                # Scroll to load reviews
                print("Scrolling to load content...")
                for i in range(5):
                    await page.evaluate('window.scrollBy(0, 800)')
                    await asyncio.sleep(0.5)

                # Look for reviews section
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(2)

                html = await page.content()
                soup = BeautifulSoup(html, 'lxml')

                # Check for review elements
                print("\n--- Looking for review elements ---")

                selectors_to_try = [
                    # PowerReviews (common)
                    ('.pr-review', 'PowerReviews .pr-review'),
                    ('.pr-review-display', 'PowerReviews display'),
                    ('[data-pr-review]', 'PowerReviews data attr'),

                    # Bazaarvoice
                    ('.bv-content-item', 'Bazaarvoice content item'),
                    ('.bv-review', 'Bazaarvoice review'),

                    # Generic
                    ('[data-testid="review"]', 'data-testid review'),
                    ('.review-item', 'review-item class'),
                    ('.review-card', 'review-card class'),
                    ('[class*="ReviewCard"]', 'ReviewCard pattern'),
                    ('[class*="review"]', 'Any review class'),

                    # Yotpo
                    ('.yotpo-review', 'Yotpo review'),

                    # Custom
                    ('[itemtype*="Review"]', 'Schema.org Review'),
                ]

                found_reviews = False
                for selector, name in selectors_to_try:
                    elements = soup.select(selector)
                    if elements:
                        print(f"  ✓ Found {len(elements)} elements with {name}")
                        found_reviews = True

                        # Sample first review
                        if elements:
                            elem = elements[0]
                            print(f"\n    Sample review element:")
                            print(f"    Tag: {elem.name}")
                            print(f"    Classes: {elem.get('class', [])[:5]}")

                            # Try to extract body
                            body_selectors = [
                                '.pr-rd-description-text',
                                '.review-text',
                                '.review-body',
                                '.bv-content-summary-body',
                                '[class*="ReviewText"]',
                                'p',
                            ]
                            for bs in body_selectors:
                                body = elem.select_one(bs)
                                if body:
                                    text = body.get_text(strip=True)[:200]
                                    if len(text) > 20:
                                        print(f"    Body ({bs}): {text}...")
                                        break

                            # Try to extract rating
                            rating_selectors = [
                                '.pr-rating-stars',
                                '.pr-rd-star-rating',
                                '[class*="rating"]',
                                '[aria-label*="star"]',
                            ]
                            for rs in rating_selectors:
                                rating = elem.select_one(rs)
                                if rating:
                                    print(f"    Rating element: {rating.get('class', [])} aria={rating.get('aria-label', '')}")
                                    break
                        break

                if not found_reviews:
                    print("  ✗ No review elements found")

                    # Check for reviews tab/section
                    print("\n--- Looking for reviews section/tab ---")
                    tabs = soup.select('[data-tab*="review"], [id*="review"], .reviews-tab, a[href*="review"]')
                    if tabs:
                        print(f"  Found potential review tabs/links: {len(tabs)}")
                        for tab in tabs[:3]:
                            print(f"    - {tab.name}: {tab.get_text(strip=True)[:50]}")

                    # Check iframe
                    iframes = soup.select('iframe[src*="review"], iframe[id*="review"]')
                    if iframes:
                        print(f"  Found review iframes: {len(iframes)}")
                        for iframe in iframes:
                            print(f"    - src: {iframe.get('src', 'N/A')[:80]}")

                # Look for any rating display
                print("\n--- Looking for product rating ---")
                rating_elements = soup.select('.pr-snippet-stars, .pr-rating, [class*="ProductRating"], [class*="starRating"]')
                if rating_elements:
                    for re_elem in rating_elements[:3]:
                        print(f"  Rating element: {re_elem.get('class', [])} - {re_elem.get_text(strip=True)[:50]}")

                # Check page for review count
                text = soup.get_text().lower()
                if 'review' in text:
                    import re
                    count_match = re.search(r'(\d+)\s+reviews?', text)
                    if count_match:
                        print(f"\n  Page mentions: {count_match.group(0)}")

            except Exception as e:
                print(f"  ERROR: {e}")

            finally:
                await page.close()

        await browser.close()

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    asyncio.run(test_fleet_feet())
