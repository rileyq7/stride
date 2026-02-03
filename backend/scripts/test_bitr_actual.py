#!/usr/bin/env python
"""
Test Believe in the Run actual review pages.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


async def test_bitr():
    print("=" * 70)
    print("BELIEVE IN THE RUN - ACTUAL REVIEWS")
    print("=" * 70)

    # Known working review URLs (from their site)
    test_urls = [
        "https://www.believeintherun.com/brooks-ghost-max-2-review/",
        "https://www.believeintherun.com/hoka-mach-6-review/",
        "https://www.believeintherun.com/asics-novablast-5-review/",
    ]

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        )

        for url in test_urls:
            print(f"\n--- {url.split('/')[-2]} ---")

            page = await context.new_page()

            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(2)

                html = await page.content()
                soup = BeautifulSoup(html, 'lxml')

                # Get title
                title = soup.select_one('h1, .entry-title')
                if title:
                    print(f"  Title: {title.get_text(strip=True)}")

                # Get article content
                article = soup.select_one('article .entry-content, .post-content, article')
                if article:
                    text = article.get_text()
                    print(f"  Content: {len(text)} chars")

                    # Look for specs
                    import re

                    weight = re.search(r'(\d+\.?\d*)\s*(oz|ounces)', text.lower())
                    drop = re.search(r'(\d+)\s*mm\s*(?:drop|offset|heel.to.toe)', text.lower())

                    if weight:
                        print(f"  Weight: {weight.group(0)}")
                    if drop:
                        print(f"  Drop: {drop.group(0)}")

                    # Look for BITR scores
                    # They use Form, Fit, Function, Overall format
                    form = re.search(r'form[:\s]+(\d+(?:\.\d+)?)', text.lower())
                    fit = re.search(r'fit[:\s]+(\d+(?:\.\d+)?)', text.lower())
                    function = re.search(r'function[:\s]+(\d+(?:\.\d+)?)', text.lower())
                    overall = re.search(r'overall[:\s]+(\d+(?:\.\d+)?)', text.lower())

                    if any([form, fit, function, overall]):
                        print("  BITR Scores:")
                        if form: print(f"    Form: {form.group(1)}")
                        if fit: print(f"    Fit: {fit.group(1)}")
                        if function: print(f"    Function: {function.group(1)}")
                        if overall: print(f"    Overall: {overall.group(1)}")

                    # Check for fit recommendations
                    fit_words = ['true to size', 'size up', 'size down', 'half size', 'narrow', 'wide']
                    found = []
                    for fw in fit_words:
                        if fw in text.lower():
                            # Get surrounding context
                            idx = text.lower().find(fw)
                            context_text = text[max(0, idx-30):min(len(text), idx+50)]
                            found.append((fw, context_text.strip()))
                    if found:
                        print("  Fit mentions:")
                        for fw, ctx in found[:3]:
                            print(f"    '{fw}': ...{ctx}...")

                else:
                    # Try broader selectors
                    main = soup.select_one('main, #main, .main-content')
                    if main:
                        print(f"  Found main content: {len(main.get_text())} chars")
                    else:
                        print("  No article content found")

            except Exception as e:
                print(f"  ERROR: {e}")

            finally:
                await page.close()

        await browser.close()


if __name__ == '__main__':
    asyncio.run(test_bitr())
