#!/usr/bin/env python
"""
Test Believe in the Run for review content.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


async def test_bitr():
    print("=" * 70)
    print("BELIEVE IN THE RUN TEST")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        )

        # First, find actual review URLs from their review index
        page = await context.new_page()

        try:
            print("\n--- Finding reviews on BITR ---")
            await page.goto("https://www.believeintherun.com/shoe-reviews/", wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(3)

            html = await page.content()
            soup = BeautifulSoup(html, 'lxml')

            # Find review links
            links = soup.select('a[href*="review"]')
            review_urls = []
            base = "https://www.believeintherun.com"
            for link in links:
                href = link.get('href', '')
                if href.startswith('/'):
                    href = base + href
                if '/shoe-reviews/' in href and '-review' in href.lower() and href not in review_urls:
                    review_urls.append(href)

            print(f"Found {len(review_urls)} review links")
            for url in review_urls[:5]:
                print(f"  {url}")

            # Test first review
            if review_urls:
                print(f"\n--- Testing: {review_urls[0]} ---")
                await page.goto(review_urls[0], wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(2)

                html = await page.content()
                soup = BeautifulSoup(html, 'lxml')

                # Save for inspection
                with open('/tmp/bitr_review.html', 'w') as f:
                    f.write(html)
                print("  Saved to /tmp/bitr_review.html")

                # Get content
                article = soup.select_one('article, .entry-content, .post-content, main')
                if article:
                    text = article.get_text()
                    print(f"  Content: {len(text)} chars")
                    print(f"  First 500 chars: {text[:500]}...")

                    # Look for structured scores
                    import re
                    scores = re.findall(r'(?:form|fit|function|overall)[:\s]*(\d+(?:\.\d+)?)', text.lower())
                    if scores:
                        print(f"  Scores found: {scores}")

                else:
                    print("  No article found")
                    # Check what's in the page
                    print(f"  Body content preview: {soup.body.get_text()[:300] if soup.body else 'No body'}...")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await page.close()

        await browser.close()


if __name__ == '__main__':
    asyncio.run(test_bitr())
