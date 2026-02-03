#!/usr/bin/env python
"""
Base class for synchronous brand scrapers.
Uses Playwright's sync API for reliable browser control.
"""

import re
import json
import time
from abc import ABC, abstractmethod
from typing import Optional, List, Set
from decimal import Decimal
from dataclasses import dataclass, field
from datetime import datetime, UTC

from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup


@dataclass
class ProductSpecs:
    brand: str
    name: str = ''
    msrp: Optional[Decimal] = None
    style_id: Optional[str] = None
    primary_image_url: Optional[str] = None
    image_urls: Optional[List[str]] = field(default_factory=list)
    weight_oz: Optional[Decimal] = None
    drop_mm: Optional[Decimal] = None
    stack_height_heel_mm: Optional[Decimal] = None
    stack_height_forefoot_mm: Optional[Decimal] = None
    terrain: Optional[str] = None
    cushion_type: Optional[str] = None
    cushion_level: Optional[str] = None
    subcategory: Optional[str] = None
    has_carbon_plate: bool = False
    has_rocker: bool = False


# Minimal stealth script
STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
"""


class SyncBrandScraper(ABC):
    """Base class for synchronous brand scrapers."""

    BRAND_NAME: str = ''
    BASE_URL: str = ''
    CATALOG_URLS: List[str] = []

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None

    def start_browser(self):
        """Start the browser."""
        print(f"Starting browser for {self.BRAND_NAME}...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.firefox.launch(headless=True)
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
        )
        self.context.add_init_script(STEALTH_SCRIPT)
        print("Browser started!")

    def stop_browser(self):
        """Stop the browser."""
        print("Stopping browser...")
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("Browser stopped.")

    def discover_all_products(self) -> List[str]:
        """Discover all product URLs from catalog pages."""
        all_urls: Set[str] = set()

        for catalog_url in self.CATALOG_URLS:
            print(f"\nCrawling: {catalog_url}")
            urls = self._fetch_catalog_products(catalog_url)
            all_urls.update(urls)
            print(f"  Found {len(urls)} products, total unique: {len(all_urls)}")

        return list(all_urls)

    def _fetch_catalog_products(self, url: str) -> Set[str]:
        """Fetch products from a single catalog page. Override for brand-specific logic."""
        product_urls: Set[str] = set()
        page = self.context.new_page()

        try:
            print(f"  Loading page...")
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            time.sleep(3)

            self._dismiss_popups(page)
            self._scroll_page(page)

            html = page.content()
            product_urls = self._extract_product_urls(html)

        except Exception as e:
            print(f"  ERROR: {e}")
        finally:
            page.close()

        return product_urls

    def _scroll_page(self, page: Page, max_scrolls: int = 15):
        """Scroll to load lazy-loaded products."""
        print(f"  Scrolling to load products...")
        last_height = 0
        scroll_count = 0

        while scroll_count < max_scrolls:
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(2)

            new_height = page.evaluate('document.body.scrollHeight')
            if new_height == last_height:
                time.sleep(1)
                new_height = page.evaluate('document.body.scrollHeight')
                if new_height == last_height:
                    break

            last_height = new_height
            scroll_count += 1

    def _dismiss_popups(self, page: Page):
        """Dismiss common popups."""
        selectors = [
            '#onetrust-accept-btn-handler',
            'button:has-text("Accept")',
            'button:has-text("Accept All")',
            'button:has-text("Accept Cookies")',
            'button:has-text("Stay")',
            'button:has-text("Continue")',
            '[data-testid="dialog-close"]',
            '[data-testid="modal-close-btn"]',
            'button[aria-label="Close"]',
            'button:has-text("Close")',
            '.modal-close',
            '.close-button',
        ]
        for selector in selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=500):
                    btn.click()
                    time.sleep(0.3)
            except Exception:
                pass

    @abstractmethod
    def _extract_product_urls(self, html: str) -> Set[str]:
        """Extract product URLs from catalog HTML. Brand-specific."""
        pass

    def scrape_product(self, product_url: str) -> Optional[ProductSpecs]:
        """Scrape a single product page."""
        page = self.context.new_page()
        try:
            page.goto(product_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(1)
            self._dismiss_popups(page)
            time.sleep(1)

            html = page.content()
            return self._parse_product_page(html, product_url)

        except Exception as e:
            print(f"  ERROR scraping {product_url}: {e}")
            return None
        finally:
            page.close()

    @abstractmethod
    def _parse_product_page(self, html: str, url: str) -> Optional[ProductSpecs]:
        """Parse product page HTML. Brand-specific."""
        pass

    # Utility methods
    def _extract_json_ld(self, html: str) -> Optional[dict]:
        """Extract JSON-LD product data."""
        pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
        for match in re.findall(pattern, html, re.DOTALL):
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

    def _parse_price(self, text: str) -> Optional[Decimal]:
        """Parse price string to Decimal."""
        if not text:
            return None
        match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', text)
        if match:
            try:
                return Decimal(match.group(1).replace(',', ''))
            except Exception:
                pass
        return None

    def _normalize_url(self, href: str) -> str:
        """Normalize a URL."""
        if href.startswith('/'):
            href = f"{self.BASE_URL}{href}"
        return href.split('?')[0]
