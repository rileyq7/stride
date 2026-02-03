#!/usr/bin/env python
"""
Test expert review sites for content.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


# Expert review sources
SOURCES = {
    "doctors_of_running": [
        "https://www.doctorsofrunning.com/2024/04/brooks-ghost-16-review.html",
        "https://www.doctorsofrunning.com/2024/05/hoka-clifton-9-review.html",
    ],
    "believe_in_the_run": [
        "https://www.believeintherun.com/shoe-reviews/brooks-ghost-16-review/",
        "https://www.believeintherun.com/shoe-reviews/hoka-clifton-9-review/",
    ],
}


async def test_expert_reviews():
    print("=" * 70)
    print("EXPERT REVIEW SITES TEST")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        )

        for source, urls in SOURCES.items():
            print(f"\n{'=' * 70}")
            print(f"SOURCE: {source}")
            print("=" * 70)

            for url in urls:
                print(f"\n--- {url.split('/')[-1]} ---")

                page = await context.new_page()

                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    await asyncio.sleep(2)

                    html = await page.content()
                    soup = BeautifulSoup(html, 'lxml')

                    # Get article content
                    article = soup.select_one('article, .post-content, .entry-content, main')
                    if article:
                        text = article.get_text(strip=True)

                        # Look for key specs
                        import re

                        weight = re.search(r'(\d+\.?\d*)\s*(oz|ounces)', text.lower())
                        drop = re.search(r'(\d+)\s*mm\s*(?:drop|offset)', text.lower())
                        stack = re.search(r'(\d+)\s*mm\s*(?:stack|heel)', text.lower())

                        print(f"  Content length: {len(text)} chars")

                        if weight:
                            print(f"  Weight: {weight.group(0)}")
                        if drop:
                            print(f"  Drop: {drop.group(0)}")
                        if stack:
                            print(f"  Stack: {stack.group(0)}")

                        # Look for fit info
                        fit_words = ['true to size', 'size up', 'size down', 'runs small', 'runs large', 'narrow', 'wide']
                        found_fit = []
                        for fw in fit_words:
                            if fw in text.lower():
                                found_fit.append(fw)
                        if found_fit:
                            print(f"  Fit mentions: {', '.join(found_fit)}")

                        # Check for rating/score
                        score = re.search(r'(?:overall|score|rating)[:\s]*(\d+(?:\.\d+)?)\s*(?:/\s*\d+|out of)', text.lower())
                        if score:
                            print(f"  Score: {score.group(0)}")

                        # Believe in the Run has structured scores
                        if source == "believe_in_the_run":
                            scores = soup.select('.score, [class*="Score"], .rating-value')
                            if scores:
                                print(f"  Structured scores found: {len(scores)}")

                    else:
                        print("  No article content found")

                except Exception as e:
                    print(f"  ERROR: {e}")

                finally:
                    await page.close()

        await browser.close()


if __name__ == '__main__':
    asyncio.run(test_expert_reviews())
