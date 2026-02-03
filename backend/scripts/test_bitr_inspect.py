#!/usr/bin/env python
"""
Inspect BITR page structure.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


async def inspect():
    url = "https://www.believeintherun.com/brooks-ghost-max-2-review/"

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        )

        page = await context.new_page()
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(3)

        # Scroll down
        for _ in range(5):
            await page.evaluate('window.scrollBy(0, 600)')
            await asyncio.sleep(0.5)

        html = await page.content()
        soup = BeautifulSoup(html, 'lxml')

        # Save HTML
        with open('/tmp/bitr_review.html', 'w') as f:
            f.write(html)
        print("Saved to /tmp/bitr_review.html")

        # Find article
        article = soup.find('article')
        if article:
            print(f"\nArticle tag found!")
            print(f"  Classes: {article.get('class', [])}")

            # Look at direct children
            print("\n  Direct children:")
            for child in list(article.children)[:10]:
                if hasattr(child, 'name') and child.name:
                    text = child.get_text(strip=True)[:50] if child.get_text(strip=True) else ''
                    print(f"    {child.name} class={child.get('class', [])} text={text}...")

            # Find content
            content_divs = article.select('div[class*="content"], .entry-content, .post-body, .article-body')
            print(f"\n  Content divs: {len(content_divs)}")
            for div in content_divs[:3]:
                print(f"    {div.get('class', [])} - {len(div.get_text())} chars")

            # Try paragraphs
            paragraphs = article.select('p')
            print(f"\n  Paragraphs: {len(paragraphs)}")
            for p in paragraphs[:5]:
                print(f"    {p.get_text(strip=True)[:80]}...")

        else:
            print("No article tag found!")

            # Check main content areas
            main = soup.select_one('main, #main, .content')
            if main:
                print(f"Found main: {len(main.get_text())} chars")
                paras = main.select('p')
                print(f"Paragraphs in main: {len(paras)}")

        await browser.close()


if __name__ == '__main__':
    asyncio.run(inspect())
