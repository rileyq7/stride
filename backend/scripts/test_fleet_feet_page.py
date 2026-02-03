#!/usr/bin/env python
"""
Inspect Fleet Feet page structure to find reviews.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


async def inspect_page():
    url = "https://www.fleetfeet.com/products/brooks-ghost-16-mens"

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        )

        page = await context.new_page()

        print(f"Loading: {url}")
        await page.goto(url, wait_until='networkidle', timeout=60000)

        # Accept cookies
        try:
            btn = page.locator('#onetrust-accept-btn-handler')
            if await btn.is_visible(timeout=3000):
                await btn.click()
                await asyncio.sleep(1)
        except:
            pass

        # Scroll all the way down
        for _ in range(10):
            await page.evaluate('window.scrollBy(0, 600)')
            await asyncio.sleep(0.5)

        await asyncio.sleep(3)

        html = await page.content()
        soup = BeautifulSoup(html, 'lxml')

        # Save HTML for inspection
        with open('/tmp/fleet_feet_page.html', 'w') as f:
            f.write(html)
        print("Saved HTML to /tmp/fleet_feet_page.html")

        # Look for anything related to reviews
        print("\n--- All elements with 'review' in class or id ---")
        all_elements = soup.find_all(True)
        for elem in all_elements:
            classes = ' '.join(elem.get('class', []))
            elem_id = elem.get('id', '')
            if 'review' in classes.lower() or 'review' in elem_id.lower():
                text = elem.get_text(strip=True)[:100]
                print(f"  {elem.name} class={classes[:50]} id={elem_id} text={text[:30]}...")

        # Look for iframes
        print("\n--- Iframes ---")
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            print(f"  src={iframe.get('src', 'N/A')[:80]}")

        # Look for scripts that might load reviews
        print("\n--- Scripts with 'review' in src ---")
        scripts = soup.find_all('script', src=True)
        for script in scripts:
            src = script.get('src', '')
            if 'review' in src.lower() or 'power' in src.lower() or 'yotpo' in src.lower():
                print(f"  {src}")

        # Check for rating/stars
        print("\n--- Star/rating elements ---")
        stars = soup.select('[class*="star"], [class*="rating"], [class*="Star"], [class*="Rating"]')
        for star in stars[:10]:
            print(f"  {star.name} class={star.get('class', [])} text={star.get_text(strip=True)[:30]}")

        await browser.close()


if __name__ == '__main__':
    asyncio.run(inspect_page())
