#!/usr/bin/env python
"""
Synchronous Nike scraper - run manually when needed.
Uses Playwright's sync API for more reliable browser control.
"""

import sys
import time
import re
import json
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from sqlalchemy import select

from app.core.database import sync_session_maker
from app.models import Brand, Category, Shoe, RunningShoeAttributes, ShoeFitProfile


@dataclass
class ProductSpecs:
    brand: str
    name: str = ''
    msrp: Optional[Decimal] = None
    style_id: Optional[str] = None
    primary_image_url: Optional[str] = None
    image_urls: Optional[List[str]] = None
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


# Stealth script to avoid bot detection
STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
"""


class SyncNikeScraper:
    """Synchronous Nike scraper using Playwright sync API."""

    BRAND_NAME = 'Nike'
    BASE_URL = 'https://www.nike.com'

    CATALOG_URLS = [
        'https://www.nike.com/w/mens-running-shoes-37v7jznik1zy7ok',
        'https://www.nike.com/w/womens-running-shoes-37v7jz5e1x6zy7ok',
        'https://www.nike.com/w/mens-basketball-shoes-3glsmznik1zy7ok',
        'https://www.nike.com/w/womens-basketball-shoes-3glsmz5e1x6zy7ok',
    ]

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None

    def start_browser(self):
        """Start the browser - call once at the beginning."""
        print("Starting Playwright browser (Firefox)...")
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
        """Stop the browser - call when done."""
        print("Stopping browser...")
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("Browser stopped.")

    def discover_all_products(self) -> List[str]:
        """Discover all product URLs from Nike catalog pages."""
        all_urls = set()

        for catalog_url in self.CATALOG_URLS:
            print(f"\nCrawling: {catalog_url}")
            urls = self._fetch_catalog_products(catalog_url)
            all_urls.update(urls)
            print(f"  Found {len(urls)} products, total unique: {len(all_urls)}")

        return list(all_urls)

    def _fetch_catalog_products(self, url: str) -> set:
        """Fetch products from a single catalog page."""
        product_urls = set()

        page = self.context.new_page()
        try:
            print(f"  Loading page...")
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            time.sleep(3)

            # Dismiss popups
            self._dismiss_popups(page)

            # Scroll to load all products
            print(f"  Scrolling to load products...")
            last_height = 0
            scroll_count = 0
            max_scrolls = 20

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

            # Extract product links
            html = page.content()
            soup = BeautifulSoup(html, 'lxml')

            for link in soup.select('a[href*="/t/"]'):
                href = link.get('href', '')
                if '/t/' in href and '/customize/' not in href:
                    if href.startswith('/'):
                        href = f"{self.BASE_URL}{href}"
                    href = href.split('?')[0]
                    product_urls.add(href)

        except Exception as e:
            print(f"  ERROR: {e}")
        finally:
            page.close()

        return product_urls

    def _dismiss_popups(self, page):
        """Try to dismiss common popups including geo-location."""
        selectors = [
            # Cookie consent
            '#onetrust-accept-btn-handler',
            'button:has-text("Accept")',
            # Geo-location popup - stay on current site
            'button:has-text("Stay")',
            '[data-testid="dialog-close"]',
            '[data-testid="modal-close-btn"]',
            'button[aria-label="Close"]',
            'button:has-text("Close")',
        ]
        for selector in selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=500):
                    btn.click()
                    time.sleep(0.3)
            except Exception:
                pass

    def scrape_product(self, product_url: str) -> Optional[ProductSpecs]:
        """Scrape a single product page."""
        page = self.context.new_page()
        try:
            page.goto(product_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(1)

            # Important: dismiss popups before scraping
            self._dismiss_popups(page)
            time.sleep(1)

            html = page.content()
            soup = BeautifulSoup(html, 'lxml')

            specs = ProductSpecs(brand=self.BRAND_NAME)

            # Extract from JSON-LD
            json_ld = self._extract_json_ld(html)
            if json_ld:
                specs.name = json_ld.get('name', '')
                specs.style_id = json_ld.get('sku')
                offers = json_ld.get('offers', {})
                if isinstance(offers, dict):
                    specs.msrp = self._parse_price(str(offers.get('price', '')))
                elif isinstance(offers, list) and offers:
                    specs.msrp = self._parse_price(str(offers[0].get('price', '')))

                image = json_ld.get('image')
                if isinstance(image, str):
                    specs.primary_image_url = image
                elif isinstance(image, list) and image:
                    specs.primary_image_url = image[0]
                    specs.image_urls = image[:10]

            # Fallback to page elements - use more specific selector
            if not specs.name:
                # Try Nike's specific product title selector
                title = soup.select_one('h1[data-testid="product-title"], h1[id="pdp_product_title"], h1.headline-2')
                if not title:
                    title = soup.select_one('h1')
                if title:
                    name = title.get_text(strip=True)
                    # Skip if it's the geo popup text
                    if 'Update your location' not in name and 'United Kingdom' not in name:
                        specs.name = name

            if not specs.msrp:
                price = soup.select_one('[data-testid="product-price"], .product-price')
                if price:
                    specs.msrp = self._parse_price(price.get_text())

            # Extract details
            self._extract_details(soup, specs)

            # Validate name - skip geo-popup garbage
            if specs.name and ('Update your location' in specs.name or 'United Kingdom' in specs.name):
                return None

            return specs if specs.name else None

        except Exception as e:
            print(f"  ERROR scraping {product_url}: {e}")
            return None
        finally:
            page.close()

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

    def _extract_details(self, soup, specs: ProductSpecs):
        """Extract product details."""
        full_text = soup.get_text(strip=True).lower()
        name_lower = (specs.name or '').lower()

        # Terrain
        if 'trail' in full_text:
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

        # Cushion type
        if 'zoomx' in full_text:
            specs.cushion_type = 'ZoomX'
            specs.cushion_level = 'max'
        elif 'react' in full_text:
            specs.cushion_type = 'React'
            specs.cushion_level = 'moderate'

        # Carbon plate
        if 'carbon' in full_text and 'plate' in full_text:
            specs.has_carbon_plate = True

        # Category from name
        if any(m in name_lower for m in ['alphafly', 'vaporfly', 'streakfly']):
            specs.subcategory = 'racing'
            specs.has_carbon_plate = True
        elif any(m in name_lower for m in ['structure']):
            specs.subcategory = 'stability'
        elif any(m in name_lower for m in ['pegasus', 'invincible', 'vomero']):
            specs.subcategory = 'neutral'


def main():
    print("=" * 70)
    print("NIKE SYNCHRONOUS SCRAPER")
    print("=" * 70)

    scraper = SyncNikeScraper()

    try:
        scraper.start_browser()

        # Discover products
        print("\n" + "=" * 70)
        print("PHASE 1: DISCOVERING PRODUCTS")
        print("=" * 70)

        product_urls = scraper.discover_all_products()
        print(f"\nTotal products discovered: {len(product_urls)}")

        if not product_urls:
            print("No products found!")
            return

        # Scrape products and save to DB
        print("\n" + "=" * 70)
        print("PHASE 2: SCRAPING & SAVING TO DATABASE")
        print("=" * 70)

        with sync_session_maker() as session:
            # Get Nike brand
            result = session.execute(select(Brand).where(Brand.slug == 'nike'))
            brand = result.scalar_one_or_none()
            if not brand:
                print("ERROR: Nike brand not found in database!")
                return

            # Get running category
            result = session.execute(select(Category).where(Category.slug == 'running'))
            running_cat = result.scalar_one_or_none()
            if not running_cat:
                print("ERROR: Running category not found!")
                return

            added = 0
            skipped = 0
            errors = 0

            for i, url in enumerate(product_urls):
                print(f"\n[{i+1}/{len(product_urls)}] {url}")

                try:
                    specs = scraper.scrape_product(url)
                    if not specs or not specs.name:
                        print("  -> No specs found")
                        errors += 1
                        continue

                    # Create slug
                    slug = specs.name.lower().replace(' ', '-').replace("'", "")

                    # Check if exists
                    existing = session.execute(
                        select(Shoe).where(Shoe.brand_id == brand.id, Shoe.slug == slug)
                    )
                    if existing.scalar_one_or_none():
                        print(f"  -> Already exists: {specs.name}")
                        skipped += 1
                        continue

                    # Create shoe
                    shoe = Shoe(
                        brand_id=brand.id,
                        category_id=running_cat.id,
                        name=specs.name,
                        slug=slug,
                        msrp_usd=specs.msrp,
                        primary_image_url=specs.primary_image_url,
                        image_urls=specs.image_urls,
                        is_active=True,
                        last_scraped_at=datetime.utcnow(),
                    )
                    session.add(shoe)
                    session.flush()

                    # Create running attributes
                    attrs = RunningShoeAttributes(
                        shoe_id=shoe.id,
                        terrain=specs.terrain or 'road',
                        subcategory=specs.subcategory,
                        weight_oz=specs.weight_oz,
                        stack_height_heel_mm=specs.stack_height_heel_mm,
                        stack_height_forefoot_mm=specs.stack_height_forefoot_mm,
                        drop_mm=specs.drop_mm,
                        cushion_type=specs.cushion_type,
                        cushion_level=specs.cushion_level,
                        has_carbon_plate=specs.has_carbon_plate,
                        has_rocker=specs.has_rocker,
                    )
                    session.add(attrs)

                    # Create fit profile placeholder
                    fit = ShoeFitProfile(
                        shoe_id=shoe.id,
                        size_runs='true_to_size',
                        needs_review=True,
                    )
                    session.add(fit)

                    print(f"  -> ADDED: {specs.name} - ${specs.msrp or '?'}")
                    added += 1

                    # Commit every 10 shoes
                    if added % 10 == 0:
                        session.commit()
                        print(f"  [Committed {added} shoes so far]")

                except Exception as e:
                    print(f"  -> ERROR: {e}")
                    errors += 1
                    continue

            # Final commit
            session.commit()

            print("\n" + "=" * 70)
            print("SUMMARY")
            print("=" * 70)
            print(f"Total discovered: {len(product_urls)}")
            print(f"Added: {added}")
            print(f"Skipped (already exist): {skipped}")
            print(f"Errors: {errors}")

    finally:
        scraper.stop_browser()


if __name__ == '__main__':
    main()
