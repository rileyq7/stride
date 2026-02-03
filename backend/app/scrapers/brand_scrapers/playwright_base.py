"""
Playwright-based brand scraper for sites with bot protection.
Enhanced stealth mode and human-like behavior.
"""

import asyncio
import random
import re
import json
import logging
from abc import abstractmethod
from typing import Optional, List
from decimal import Decimal
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, BrowserContext, Page

from .base import ProductSpecs
from ..utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


# Comprehensive stealth script
STEALTH_SCRIPT = """
// Webdriver detection
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: true
});
delete navigator.__proto__.webdriver;

// Chrome runtime
window.chrome = {
    runtime: {
        onConnect: { addListener: function() {} },
        onMessage: { addListener: function() {} },
        sendMessage: function() {},
        connect: function() { return { onMessage: { addListener: function() {} } }; }
    },
    loadTimes: function() { return {}; },
    csi: function() { return {}; },
    app: { isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' } }
};

// Plugins - make it look real
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
        ];
        plugins.length = 3;
        plugins.item = function(i) { return this[i] || null; };
        plugins.namedItem = function(name) { return this.find(p => p.name === name) || null; };
        plugins.refresh = function() {};
        return plugins;
    }
});

// Languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en']
});

Object.defineProperty(navigator, 'language', {
    get: () => 'en-US'
});

// Hardware concurrency
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8
});

// Device memory
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8
});

// Platform
Object.defineProperty(navigator, 'platform', {
    get: () => 'MacIntel'
});

// Vendor
Object.defineProperty(navigator, 'vendor', {
    get: () => 'Google Inc.'
});

// Max touch points
Object.defineProperty(navigator, 'maxTouchPoints', {
    get: () => 0
});

// Permissions
const originalQuery = window.navigator.permissions?.query;
if (originalQuery) {
    window.navigator.permissions.query = (parameters) => {
        if (parameters.name === 'notifications') {
            return Promise.resolve({ state: 'default', onchange: null });
        }
        return originalQuery.call(window.navigator.permissions, parameters);
    };
}

// WebGL vendor/renderer
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) return 'Intel Inc.';
    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
    return getParameter.call(this, parameter);
};

// Canvas fingerprint randomization
const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function(type) {
    if (type === 'image/png' && this.width === 16 && this.height === 16) {
        return 'data:image/png;base64,random' + Math.random().toString(36).substring(7);
    }
    return originalToDataURL.apply(this, arguments);
};

// Disable automation-related properties
Object.defineProperty(window, 'outerWidth', { get: () => window.innerWidth });
Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight + 85 });

// Connection type
Object.defineProperty(navigator, 'connection', {
    get: () => ({
        effectiveType: '4g',
        rtt: 50,
        downlink: 10,
        saveData: false
    })
});

// Battery API
navigator.getBattery = () => Promise.resolve({
    charging: true,
    chargingTime: 0,
    dischargingTime: Infinity,
    level: 1.0
});

// Notification permission
Object.defineProperty(Notification, 'permission', {
    get: () => 'default'
});

// Console log suppression for automation detection
const originalError = console.error;
console.error = function(...args) {
    if (args[0]?.includes?.('automation')) return;
    return originalError.apply(console, args);
};
"""


class PlaywrightBrandScraper:
    """Base class for brand scrapers requiring browser automation."""

    BRAND_NAME: str = ''
    BASE_URL: str = ''

    # User agents pool for rotation
    USER_AGENTS = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    ]

    def __init__(self):
        self.rate_limiter = RateLimiter(self.BRAND_NAME.lower().replace(' ', '_'))

    def _get_random_user_agent(self) -> str:
        return random.choice(self.USER_AGENTS)

    async def _human_delay(self, min_ms: int = 500, max_ms: int = 2000):
        """Random delay to simulate human behavior."""
        delay = random.randint(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)

    async def _human_mouse_move(self, page: Page):
        """Simulate human-like mouse movement."""
        try:
            # Random movements across the page
            for _ in range(random.randint(2, 4)):
                x = random.randint(100, 1200)
                y = random.randint(100, 600)
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.3))
        except Exception:
            pass

    async def _human_scroll(self, page: Page):
        """Simulate human-like scrolling."""
        try:
            # Scroll down in chunks
            scroll_amount = random.randint(200, 400)
            await page.evaluate(f'window.scrollBy(0, {scroll_amount})')
            await asyncio.sleep(random.uniform(0.3, 0.7))

            scroll_amount = random.randint(200, 400)
            await page.evaluate(f'window.scrollBy(0, {scroll_amount})')
            await asyncio.sleep(random.uniform(0.3, 0.7))
        except Exception:
            pass

    async def _dismiss_popups(self, page: Page):
        """Try to dismiss common popups."""
        popup_selectors = [
            # Cookie consent
            '#onetrust-accept-btn-handler',
            'button[data-testid="accept-cookies"]',
            'button:has-text("Accept All")',
            'button:has-text("Accept Cookies")',
            'button:has-text("I Accept")',
            '.cookie-consent button',
            # Close buttons
            'button[aria-label="Close"]',
            'button[aria-label="close"]',
            '[data-testid="dialog-close"]',
            '[data-testid="modal-close"]',
            '.modal-close',
            '.close-button',
            # Geo selectors
            'button:has-text("Stay")',
            'button:has-text("United States")',
            'button:has-text("Continue")',
            # Newsletter popups
            'button:has-text("No Thanks")',
            '.email-popup button[type="button"]',
        ]

        for selector in popup_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.is_visible(timeout=300):
                    await btn.click()
                    await asyncio.sleep(0.5)
            except Exception:
                pass

    async def fetch_page(self, url: str, wait_selector: Optional[str] = None) -> Optional[str]:
        """Fetch page content using Playwright with enhanced stealth."""
        await self.rate_limiter.wait()

        playwright = None
        browser = None
        context = None
        page = None

        try:
            playwright = await async_playwright().start()

            # Use Firefox - more reliable on macOS
            browser = await playwright.firefox.launch(headless=True)

            # Create context with realistic settings
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=self._get_random_user_agent(),
                locale='en-US',
                timezone_id='America/New_York',
                java_script_enabled=True,
                bypass_csp=True,
                ignore_https_errors=True,
                color_scheme='light',
                reduced_motion='no-preference',
                has_touch=False,
                is_mobile=False,
                device_scale_factor=1,
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
                    'Sec-Ch-Ua-Mobile': '?0',
                    'Sec-Ch-Ua-Platform': '"macOS"',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                }
            )

            # Add stealth scripts before any page loads
            await context.add_init_script(STEALTH_SCRIPT)

            page = await context.new_page()

            # More human-like navigation
            logger.info(f"Fetching: {url}")

            # Navigate with realistic behavior
            response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)

            if response and response.status >= 400:
                logger.warning(f"Got status {response.status} for {url}")
                return None

            # Wait for network to settle
            await asyncio.sleep(2)

            # Human-like behavior
            await self._human_mouse_move(page)
            await self._human_delay(1000, 2000)

            # Try to dismiss popups
            await self._dismiss_popups(page)
            await asyncio.sleep(1)

            # Wait for specific content if requested
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=15000)
                except Exception:
                    logger.debug(f"Selector {wait_selector} not found, continuing...")

            # Scroll to trigger lazy loading
            await self._human_scroll(page)
            await asyncio.sleep(1)

            # Get final content
            content = await page.content()
            logger.info(f"Got {len(content)} bytes from {url}")
            return content

        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            if playwright:
                try:
                    await playwright.stop()
                except Exception:
                    pass

    async def search_and_find_product(self, shoe_name: str, search_url_template: str) -> Optional[str]:
        """Search for a product and return its URL."""
        await self.rate_limiter.wait()

        playwright = None
        browser = None
        context = None
        page = None

        try:
            playwright = await async_playwright().start()
            browser = await playwright.firefox.launch(headless=True)

            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=self._get_random_user_agent(),
                locale='en-US',
                timezone_id='America/New_York',
            )
            await context.add_init_script(STEALTH_SCRIPT)

            page = await context.new_page()

            # Navigate to search page
            search_query = shoe_name.replace(' ', '+')
            search_url = search_url_template.format(query=search_query)

            logger.info(f"Searching: {search_url}")
            await page.goto(search_url, wait_until='domcontentloaded', timeout=60000)

            await asyncio.sleep(3)
            await self._dismiss_popups(page)
            await self._human_scroll(page)
            await asyncio.sleep(2)

            # Look for product links
            content = await page.content()

            # Return the content for parsing by subclass
            return content

        except Exception as e:
            logger.error(f"Error searching for {shoe_name}: {e}")
            return None

        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            if playwright:
                try:
                    await playwright.stop()
                except Exception:
                    pass

    def get_product_url(self, shoe_name: str) -> Optional[str]:
        """Sync wrapper for async get_product_url."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.get_product_url_async(shoe_name))

    def scrape_product_specs(self, product_url: str) -> Optional[ProductSpecs]:
        """Sync wrapper for async scrape_product_specs."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.scrape_product_specs_async(product_url))

    def scrape_shoe(self, shoe_name: str) -> Optional[ProductSpecs]:
        """Main entry point: find product and scrape specs."""
        url = self.get_product_url(shoe_name)
        if not url:
            logger.warning(f"Could not find {shoe_name} on {self.BRAND_NAME}")
            return None
        return self.scrape_product_specs(url)

    @abstractmethod
    async def get_product_url_async(self, shoe_name: str) -> Optional[str]:
        """Find the product page URL for a shoe."""
        pass

    @abstractmethod
    async def scrape_product_specs_async(self, product_url: str) -> Optional[ProductSpecs]:
        """Scrape specifications from a product page."""
        pass

    def _parse_price(self, text: str) -> Optional[Decimal]:
        """Parse a price string to Decimal."""
        if not text:
            return None
        match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', text)
        if match:
            price_str = match.group(1).replace(',', '')
            try:
                return Decimal(price_str)
            except Exception:
                pass
        return None

    def _parse_weight(self, text: str) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """Parse weight text, return (oz, grams)."""
        if not text:
            return None, None

        oz_match = re.search(r'([\d.]+)\s*(?:oz|ounces?)', text, re.IGNORECASE)
        g_match = re.search(r'([\d.]+)\s*(?:g|grams?)', text, re.IGNORECASE)

        weight_oz = Decimal(oz_match.group(1)) if oz_match else None
        weight_g = Decimal(g_match.group(1)) if g_match else None

        if weight_g and not weight_oz:
            weight_oz = round(weight_g / Decimal('28.35'), 1)
        elif weight_oz and not weight_g:
            weight_g = round(weight_oz * Decimal('28.35'), 0)

        return weight_oz, weight_g

    def _extract_json_ld(self, html: str) -> Optional[dict]:
        """Extract JSON-LD product data from HTML."""
        pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
        matches = re.findall(pattern, html, re.DOTALL)

        for match in matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    return data
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Product':
                            return item
            except json.JSONDecodeError:
                continue

        return None

    async def discover_all_products(self) -> List[str]:
        """
        Discover all product URLs from the brand's website.
        Each brand scraper should override this with brand-specific catalog crawling.
        Returns a list of product URLs.
        """
        raise NotImplementedError("Subclasses must implement discover_all_products()")

    async def scrape_all_products(self) -> List[ProductSpecs]:
        """
        Scrape all products from the brand website.
        Discovers all product URLs and scrapes each one.
        """
        product_urls = await self.discover_all_products()
        logger.info(f"Discovered {len(product_urls)} products for {self.BRAND_NAME}")

        all_specs = []
        for url in product_urls:
            try:
                specs = await self.scrape_product_specs_async(url)
                if specs and specs.name:
                    all_specs.append(specs)
                    logger.info(f"Scraped: {specs.name}")
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                continue

        logger.info(f"Successfully scraped {len(all_specs)} products for {self.BRAND_NAME}")
        return all_specs
