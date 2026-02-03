"""
Base class for browser-automated scraping using Playwright.

Use this for sites that require JavaScript rendering or have anti-bot measures.
"""

import asyncio
import logging
from abc import abstractmethod
from typing import List, Optional
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from .base import BaseScraper, RawReview
from .utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class PlaywrightBaseScraper(BaseScraper):
    """Base class for scrapers requiring browser automation."""

    def __init__(self, config: dict):
        # Don't call super().__init__ since we don't need httpx client
        self.config = config
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.rate_limiter: Optional[RateLimiter] = None

    @asynccontextmanager
    async def get_browser(self):
        """Context manager for browser lifecycle."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
        )

        # Add stealth scripts
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """)

        try:
            yield context
        finally:
            await context.close()
            await browser.close()
            await playwright.stop()

    async def get_page_content(self, url: str, wait_selector: Optional[str] = None) -> str:
        """Fetch page content with JavaScript rendering."""
        if self.rate_limiter:
            await self.rate_limiter.wait()

        async with self.get_browser() as context:
            page = await context.new_page()

            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)

                if wait_selector:
                    await page.wait_for_selector(wait_selector, timeout=10000)

                # Give dynamic content time to load
                await asyncio.sleep(2)

                return await page.content()

            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                return ''

            finally:
                await page.close()

    async def get_page_with_scroll(self, url: str, scroll_count: int = 3) -> str:
        """Fetch page content with scrolling to load lazy content."""
        if self.rate_limiter:
            await self.rate_limiter.wait()

        async with self.get_browser() as context:
            page = await context.new_page()

            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)

                # Scroll to load lazy content
                for _ in range(scroll_count):
                    await page.evaluate('window.scrollBy(0, window.innerHeight)')
                    await asyncio.sleep(1)

                # Scroll back to top
                await page.evaluate('window.scrollTo(0, 0)')
                await asyncio.sleep(1)

                return await page.content()

            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                return ''

            finally:
                await page.close()

    def get_product_url(self, shoe) -> Optional[str]:
        """Find the product page URL for a given shoe (async wrapper)."""
        return asyncio.get_event_loop().run_until_complete(
            self.get_product_url_async(shoe)
        )

    def scrape_reviews(self, product_url: str) -> List[RawReview]:
        """Scrape reviews from a product page (async wrapper)."""
        return asyncio.get_event_loop().run_until_complete(
            self.scrape_reviews_async(product_url)
        )

    @abstractmethod
    async def get_product_url_async(self, shoe) -> Optional[str]:
        """Find the product page URL for a given shoe (async)."""
        pass

    @abstractmethod
    async def scrape_reviews_async(self, product_url: str) -> List[RawReview]:
        """Scrape reviews from a product page (async)."""
        pass
