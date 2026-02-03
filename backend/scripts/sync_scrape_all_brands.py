#!/usr/bin/env python
"""
Synchronous scraper for ALL brands - run manually when needed.
Uses Playwright's sync API for reliable browser control.

Usage:
    python sync_scrape_all_brands.py              # Scrape all brands
    python sync_scrape_all_brands.py nike         # Scrape only Nike
    python sync_scrape_all_brands.py hoka brooks  # Scrape Hoka and Brooks
"""

import sys
import re
import json
import time
from pathlib import Path
from typing import Optional, List, Set
from decimal import Decimal
from dataclasses import dataclass, field
from datetime import datetime, UTC

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.sync_api import sync_playwright, Page
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


STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
"""


class SyncBrandScraper:
    """Base class for sync scrapers."""

    BRAND_NAME: str = ''
    BRAND_SLUG: str = ''
    BASE_URL: str = ''
    CATALOG_URLS: List[str] = []

    def __init__(self, context):
        self.context = context

    def discover_all_products(self) -> List[str]:
        all_urls: Set[str] = set()
        for catalog_url in self.CATALOG_URLS:
            print(f"  Crawling: {catalog_url}")
            urls = self._fetch_catalog_products(catalog_url)
            all_urls.update(urls)
            print(f"    Found {len(urls)} products, total: {len(all_urls)}")
        return list(all_urls)

    def _fetch_catalog_products(self, url: str) -> Set[str]:
        product_urls: Set[str] = set()
        page = self.context.new_page()
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            time.sleep(3)
            self._dismiss_popups(page)
            self._scroll_page(page)
            html = page.content()
            product_urls = self._extract_product_urls(html)
        except Exception as e:
            print(f"    ERROR: {e}")
        finally:
            page.close()
        return product_urls

    def _scroll_page(self, page: Page, max_scrolls: int = 15):
        last_height = 0
        for _ in range(max_scrolls):
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(2)
            new_height = page.evaluate('document.body.scrollHeight')
            if new_height == last_height:
                break
            last_height = new_height

    def _dismiss_popups(self, page: Page):
        for selector in ['#onetrust-accept-btn-handler', 'button:has-text("Accept")',
                         'button:has-text("Stay")', 'button[aria-label="Close"]',
                         '[data-testid="dialog-close"]', 'button:has-text("Close")']:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=500):
                    btn.click()
                    time.sleep(0.3)
            except Exception:
                pass

    def _extract_product_urls(self, html: str) -> Set[str]:
        return set()

    def scrape_product(self, product_url: str) -> Optional[ProductSpecs]:
        page = self.context.new_page()
        try:
            page.goto(product_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(1)
            self._dismiss_popups(page)
            time.sleep(1)
            html = page.content()
            return self._parse_product_page(html, product_url)
        except Exception as e:
            print(f"    ERROR: {e}")
            return None
        finally:
            page.close()

    def _parse_product_page(self, html: str, url: str) -> Optional[ProductSpecs]:
        return None

    def _extract_json_ld(self, html: str) -> Optional[dict]:
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
        if href.startswith('/'):
            href = f"{self.BASE_URL}{href}"
        return href.split('?')[0]


# ============================================================================
# NIKE SCRAPER
# ============================================================================
class NikeScraper(SyncBrandScraper):
    BRAND_NAME = 'Nike'
    BRAND_SLUG = 'nike'
    BASE_URL = 'https://www.nike.com'
    CATALOG_URLS = [
        'https://www.nike.com/w/mens-running-shoes-37v7jznik1zy7ok',
        'https://www.nike.com/w/womens-running-shoes-37v7jz5e1x6zy7ok',
        'https://www.nike.com/w/mens-basketball-shoes-3glsmznik1zy7ok',
        'https://www.nike.com/w/womens-basketball-shoes-3glsmz5e1x6zy7ok',
    ]

    def _extract_product_urls(self, html: str) -> Set[str]:
        urls = set()
        soup = BeautifulSoup(html, 'lxml')
        for link in soup.select('a[href*="/t/"]'):
            href = link.get('href', '')
            if '/t/' in href and '/customize/' not in href:
                urls.add(self._normalize_url(href))
        return urls

    def _parse_product_page(self, html: str, url: str) -> Optional[ProductSpecs]:
        soup = BeautifulSoup(html, 'lxml')
        specs = ProductSpecs(brand=self.BRAND_NAME)

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

        if not specs.name:
            title = soup.select_one('h1[data-testid="product-title"], h1')
            if title:
                name = title.get_text(strip=True)
                if 'Update your location' not in name:
                    specs.name = name

        # Detect specs from text
        full_text = soup.get_text(strip=True).lower()
        name_lower = (specs.name or '').lower()

        if 'trail' in full_text:
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

        if 'zoomx' in full_text:
            specs.cushion_type = 'ZoomX'
            specs.cushion_level = 'max'
        elif 'react' in full_text:
            specs.cushion_type = 'React'
            specs.cushion_level = 'moderate'

        if any(m in name_lower for m in ['alphafly', 'vaporfly', 'streakfly']):
            specs.subcategory = 'racing'
            specs.has_carbon_plate = True
        elif 'structure' in name_lower:
            specs.subcategory = 'stability'
        elif any(m in name_lower for m in ['pegasus', 'invincible', 'vomero']):
            specs.subcategory = 'neutral'

        return specs if specs.name else None


# ============================================================================
# HOKA SCRAPER
# ============================================================================
class HokaScraper(SyncBrandScraper):
    BRAND_NAME = 'Hoka'
    BRAND_SLUG = 'hoka'
    BASE_URL = 'https://www.hoka.com'
    CATALOG_URLS = [
        'https://www.hoka.com/en/us/mens-road',
        'https://www.hoka.com/en/us/womens-road',
        'https://www.hoka.com/en/us/mens-trail',
        'https://www.hoka.com/en/us/womens-trail',
    ]

    def _extract_product_urls(self, html: str) -> Set[str]:
        urls = set()
        soup = BeautifulSoup(html, 'lxml')
        for link in soup.select('a[href*="/p/"]'):
            href = link.get('href', '')
            if '/p/' in href:
                urls.add(self._normalize_url(href))
        return urls

    def _parse_product_page(self, html: str, url: str) -> Optional[ProductSpecs]:
        soup = BeautifulSoup(html, 'lxml')
        specs = ProductSpecs(brand=self.BRAND_NAME)

        json_ld = self._extract_json_ld(html)
        if json_ld:
            specs.name = json_ld.get('name', '')
            specs.msrp = self._parse_price(str(json_ld.get('offers', {}).get('price', '')))
            image = json_ld.get('image')
            if isinstance(image, str):
                specs.primary_image_url = image

        if not specs.name:
            title = soup.select_one('h1.product-name, h1')
            if title:
                specs.name = title.get_text(strip=True)

        full_text = soup.get_text(strip=True).lower()
        name_lower = (specs.name or '').lower()

        if 'trail' in full_text or 'trail' in name_lower:
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

        if any(m in name_lower for m in ['bondi', 'clifton', 'mach']):
            specs.cushion_level = 'max'
        if any(m in name_lower for m in ['arahi', 'gaviota']):
            specs.subcategory = 'stability'
        elif any(m in name_lower for m in ['rocket', 'cielo']):
            specs.subcategory = 'racing'
            specs.has_carbon_plate = True
        else:
            specs.subcategory = 'neutral'

        return specs if specs.name else None


# ============================================================================
# BROOKS SCRAPER
# ============================================================================
class BrooksScraper(SyncBrandScraper):
    BRAND_NAME = 'Brooks'
    BRAND_SLUG = 'brooks'
    BASE_URL = 'https://www.brooksrunning.com'
    CATALOG_URLS = [
        'https://www.brooksrunning.com/en_us/mens-running-shoes/',
        'https://www.brooksrunning.com/en_us/womens-running-shoes/',
    ]

    def _extract_product_urls(self, html: str) -> Set[str]:
        urls = set()
        soup = BeautifulSoup(html, 'lxml')
        for link in soup.select('a[href*="/shoes/"]'):
            href = link.get('href', '')
            if '/shoes/' in href and href.count('/') >= 3:
                urls.add(self._normalize_url(href))
        return urls

    def _parse_product_page(self, html: str, url: str) -> Optional[ProductSpecs]:
        soup = BeautifulSoup(html, 'lxml')
        specs = ProductSpecs(brand=self.BRAND_NAME)

        json_ld = self._extract_json_ld(html)
        if json_ld:
            specs.name = json_ld.get('name', '')
            specs.msrp = self._parse_price(str(json_ld.get('offers', {}).get('price', '')))

        if not specs.name:
            title = soup.select_one('h1.product-name, h1')
            if title:
                specs.name = title.get_text(strip=True)

        full_text = soup.get_text(strip=True).lower()
        name_lower = (specs.name or '').lower()

        if 'trail' in full_text or 'cascadia' in name_lower or 'caldera' in name_lower:
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

        if any(m in name_lower for m in ['adrenaline', 'beast', 'ariel']):
            specs.subcategory = 'stability'
        elif any(m in name_lower for m in ['hyperion']):
            specs.subcategory = 'racing'
            specs.has_carbon_plate = 'elite' in name_lower
        else:
            specs.subcategory = 'neutral'

        if 'dna loft' in full_text or 'nitrogen' in full_text:
            specs.cushion_type = 'DNA LOFT'
            specs.cushion_level = 'max'
        elif 'dna' in full_text:
            specs.cushion_type = 'DNA'
            specs.cushion_level = 'moderate'

        return specs if specs.name else None


# ============================================================================
# ASICS SCRAPER
# ============================================================================
class AsicsScraper(SyncBrandScraper):
    BRAND_NAME = 'ASICS'
    BRAND_SLUG = 'asics'
    BASE_URL = 'https://www.asics.com'
    CATALOG_URLS = [
        'https://www.asics.com/us/en-us/mens-running-shoes/c/aa10201000/',
        'https://www.asics.com/us/en-us/womens-running-shoes/c/ab10201000/',
        'https://www.asics.com/us/en-us/mens-trail-running-shoes/c/aa10201080/',
        'https://www.asics.com/us/en-us/womens-trail-running-shoes/c/ab10201080/',
    ]

    def _extract_product_urls(self, html: str) -> Set[str]:
        urls = set()
        soup = BeautifulSoup(html, 'lxml')
        for link in soup.select('a[href*="/p/"]'):
            href = link.get('href', '')
            if '/p/' in href:
                urls.add(self._normalize_url(href))
        return urls

    def _parse_product_page(self, html: str, url: str) -> Optional[ProductSpecs]:
        soup = BeautifulSoup(html, 'lxml')
        specs = ProductSpecs(brand=self.BRAND_NAME)

        json_ld = self._extract_json_ld(html)
        if json_ld:
            specs.name = json_ld.get('name', '')
            specs.msrp = self._parse_price(str(json_ld.get('offers', {}).get('price', '')))

        if not specs.name:
            title = soup.select_one('h1.product-name, h1')
            if title:
                specs.name = title.get_text(strip=True)

        full_text = soup.get_text(strip=True).lower()
        name_lower = (specs.name or '').lower()

        if 'trail' in name_lower or 'trabuco' in name_lower or 'fuji' in name_lower:
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

        if any(m in name_lower for m in ['kayano', 'gt-2000', 'gt-1000']):
            specs.subcategory = 'stability'
        elif any(m in name_lower for m in ['metaspeed', 'magic speed', 'superblast']):
            specs.subcategory = 'racing'
            specs.has_carbon_plate = True
        else:
            specs.subcategory = 'neutral'

        if 'gel' in full_text:
            specs.cushion_type = 'GEL'
        if 'ff blast' in full_text or 'flytefoam' in full_text:
            specs.cushion_type = 'FlyteFoam Blast'
            specs.cushion_level = 'max'

        return specs if specs.name else None


# ============================================================================
# SAUCONY SCRAPER
# ============================================================================
class SauconyScraper(SyncBrandScraper):
    BRAND_NAME = 'Saucony'
    BRAND_SLUG = 'saucony'
    BASE_URL = 'https://www.saucony.com'
    CATALOG_URLS = [
        'https://www.saucony.com/en/mens-running-shoes/',
        'https://www.saucony.com/en/womens-running-shoes/',
        'https://www.saucony.com/en/mens-trail-running-shoes/',
        'https://www.saucony.com/en/womens-trail-running-shoes/',
    ]

    def _extract_product_urls(self, html: str) -> Set[str]:
        urls = set()
        soup = BeautifulSoup(html, 'lxml')
        for link in soup.select('a[href*="/shoes/"]'):
            href = link.get('href', '')
            if '/shoes/' in href:
                urls.add(self._normalize_url(href))
        return urls

    def _parse_product_page(self, html: str, url: str) -> Optional[ProductSpecs]:
        soup = BeautifulSoup(html, 'lxml')
        specs = ProductSpecs(brand=self.BRAND_NAME)

        json_ld = self._extract_json_ld(html)
        if json_ld:
            specs.name = json_ld.get('name', '')
            specs.msrp = self._parse_price(str(json_ld.get('offers', {}).get('price', '')))

        if not specs.name:
            title = soup.select_one('h1.product-name, h1')
            if title:
                specs.name = title.get_text(strip=True)

        full_text = soup.get_text(strip=True).lower()
        name_lower = (specs.name or '').lower()

        if 'trail' in name_lower or 'peregrine' in name_lower or 'xodus' in name_lower:
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

        if any(m in name_lower for m in ['guide', 'hurricane', 'omni']):
            specs.subcategory = 'stability'
        elif any(m in name_lower for m in ['endorphin pro', 'endorphin elite']):
            specs.subcategory = 'racing'
            specs.has_carbon_plate = True
        else:
            specs.subcategory = 'neutral'

        if 'pwrrun+' in full_text or 'pwrrun pb' in full_text:
            specs.cushion_type = 'PWRRUN+'
            specs.cushion_level = 'max'
        elif 'pwrrun' in full_text:
            specs.cushion_type = 'PWRRUN'
            specs.cushion_level = 'moderate'

        return specs if specs.name else None


# ============================================================================
# ADIDAS SCRAPER
# ============================================================================
class AdidasScraper(SyncBrandScraper):
    BRAND_NAME = 'Adidas'
    BRAND_SLUG = 'adidas'
    BASE_URL = 'https://www.adidas.com'
    CATALOG_URLS = [
        'https://www.adidas.com/us/men-running-shoes',
        'https://www.adidas.com/us/women-running-shoes',
        'https://www.adidas.com/us/men-basketball-shoes',
        'https://www.adidas.com/us/women-basketball-shoes',
    ]

    def _extract_product_urls(self, html: str) -> Set[str]:
        urls = set()
        soup = BeautifulSoup(html, 'lxml')
        for link in soup.select('a[href*="/products/"]'):
            href = link.get('href', '')
            if '/products/' in href:
                urls.add(self._normalize_url(href))
        return urls

    def _parse_product_page(self, html: str, url: str) -> Optional[ProductSpecs]:
        soup = BeautifulSoup(html, 'lxml')
        specs = ProductSpecs(brand=self.BRAND_NAME)

        json_ld = self._extract_json_ld(html)
        if json_ld:
            specs.name = json_ld.get('name', '')
            specs.msrp = self._parse_price(str(json_ld.get('offers', {}).get('price', '')))

        if not specs.name:
            title = soup.select_one('h1[data-testid="product-title"], h1')
            if title:
                specs.name = title.get_text(strip=True)

        full_text = soup.get_text(strip=True).lower()
        name_lower = (specs.name or '').lower()

        if 'trail' in name_lower or 'terrex' in name_lower:
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

        if 'adizero' in name_lower:
            specs.subcategory = 'racing'
        elif 'supernova' in name_lower or 'solar' in name_lower:
            specs.subcategory = 'neutral'

        if 'boost' in full_text:
            specs.cushion_type = 'Boost'
            specs.cushion_level = 'max'
        elif 'lightstrike' in full_text:
            specs.cushion_type = 'Lightstrike'
            specs.cushion_level = 'moderate'

        return specs if specs.name else None


# ============================================================================
# NEW BALANCE SCRAPER
# ============================================================================
class NewBalanceScraper(SyncBrandScraper):
    BRAND_NAME = 'New Balance'
    BRAND_SLUG = 'new-balance'
    BASE_URL = 'https://www.newbalance.com'
    CATALOG_URLS = [
        'https://www.newbalance.com/en_us/men/shoes/running/',
        'https://www.newbalance.com/en_us/women/shoes/running/',
        'https://www.newbalance.com/en_us/men/shoes/basketball/',
        'https://www.newbalance.com/en_us/women/shoes/basketball/',
    ]

    def _extract_product_urls(self, html: str) -> Set[str]:
        urls = set()
        soup = BeautifulSoup(html, 'lxml')
        for link in soup.select('a[href*="/pd/"], a[href*="/product/"]'):
            href = link.get('href', '')
            if '/pd/' in href or '/product/' in href:
                urls.add(self._normalize_url(href))
        return urls

    def _parse_product_page(self, html: str, url: str) -> Optional[ProductSpecs]:
        soup = BeautifulSoup(html, 'lxml')
        specs = ProductSpecs(brand=self.BRAND_NAME)

        json_ld = self._extract_json_ld(html)
        if json_ld:
            specs.name = json_ld.get('name', '')
            specs.msrp = self._parse_price(str(json_ld.get('offers', {}).get('price', '')))

        if not specs.name:
            title = soup.select_one('h1.product-name, h1')
            if title:
                specs.name = title.get_text(strip=True)

        full_text = soup.get_text(strip=True).lower()
        name_lower = (specs.name or '').lower()

        if 'trail' in name_lower or 'hierro' in name_lower:
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

        if any(m in name_lower for m in ['860', 'vongo', '1540']):
            specs.subcategory = 'stability'
        elif any(m in name_lower for m in ['fuelcell rc', 'supercomp', 'sc elite']):
            specs.subcategory = 'racing'
            specs.has_carbon_plate = True
        else:
            specs.subcategory = 'neutral'

        if 'fuelcell' in full_text:
            specs.cushion_type = 'FuelCell'
            specs.cushion_level = 'max'
        elif 'fresh foam' in full_text:
            specs.cushion_type = 'Fresh Foam'
            specs.cushion_level = 'max'

        return specs if specs.name else None


# ============================================================================
# ON RUNNING SCRAPER
# ============================================================================
class OnRunningScraper(SyncBrandScraper):
    BRAND_NAME = 'On'
    BRAND_SLUG = 'on'
    BASE_URL = 'https://www.on-running.com'
    CATALOG_URLS = [
        'https://www.on-running.com/en-us/collection/road-running-shoes',
        'https://www.on-running.com/en-us/collection/trail-running-shoes',
    ]

    def _extract_product_urls(self, html: str) -> Set[str]:
        urls = set()
        soup = BeautifulSoup(html, 'lxml')
        for link in soup.select('a[href*="/products/"]'):
            href = link.get('href', '')
            if '/products/' in href:
                urls.add(self._normalize_url(href))
        return urls

    def _parse_product_page(self, html: str, url: str) -> Optional[ProductSpecs]:
        soup = BeautifulSoup(html, 'lxml')
        specs = ProductSpecs(brand=self.BRAND_NAME)

        json_ld = self._extract_json_ld(html)
        if json_ld:
            specs.name = json_ld.get('name', '')
            specs.msrp = self._parse_price(str(json_ld.get('offers', {}).get('price', '')))

        if not specs.name:
            title = soup.select_one('h1.product-name, h1')
            if title:
                specs.name = title.get_text(strip=True)

        full_text = soup.get_text(strip=True).lower()
        name_lower = (specs.name or '').lower()

        if 'trail' in name_lower or 'cloudventure' in name_lower or 'cloudultra' in name_lower:
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

        if any(m in name_lower for m in ['cloudboom', 'cloudflash']):
            specs.subcategory = 'racing'
            specs.has_carbon_plate = True
        else:
            specs.subcategory = 'neutral'

        specs.cushion_type = 'CloudTec'
        specs.cushion_level = 'moderate'

        return specs if specs.name else None


# ============================================================================
# ALTRA SCRAPER
# ============================================================================
class AltraScraper(SyncBrandScraper):
    BRAND_NAME = 'Altra'
    BRAND_SLUG = 'altra'
    BASE_URL = 'https://www.altrarunning.com'
    CATALOG_URLS = [
        'https://www.altrarunning.com/shop/mens/road-running/',
        'https://www.altrarunning.com/shop/womens/road-running/',
        'https://www.altrarunning.com/shop/mens/trail-running/',
        'https://www.altrarunning.com/shop/womens/trail-running/',
    ]

    def _extract_product_urls(self, html: str) -> Set[str]:
        urls = set()
        soup = BeautifulSoup(html, 'lxml')
        for link in soup.select('a[href*="/product/"], a[href*="/shop/"]'):
            href = link.get('href', '')
            if '/product/' in href or (href.count('/') >= 4 and 'shop' in href):
                urls.add(self._normalize_url(href))
        return urls

    def _parse_product_page(self, html: str, url: str) -> Optional[ProductSpecs]:
        soup = BeautifulSoup(html, 'lxml')
        specs = ProductSpecs(brand=self.BRAND_NAME)

        json_ld = self._extract_json_ld(html)
        if json_ld:
            specs.name = json_ld.get('name', '')
            specs.msrp = self._parse_price(str(json_ld.get('offers', {}).get('price', '')))

        if not specs.name:
            title = soup.select_one('h1.product-name, h1')
            if title:
                specs.name = title.get_text(strip=True)

        full_text = soup.get_text(strip=True).lower()
        name_lower = (specs.name or '').lower()

        if any(m in name_lower for m in ['lone peak', 'timp', 'olympus', 'superior', 'mont blanc']):
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

        # All Altra shoes are zero drop
        specs.drop_mm = Decimal('0')
        specs.subcategory = 'neutral'  # All Altra are neutral

        if 'ego max' in full_text:
            specs.cushion_type = 'Altra EGO MAX'
            specs.cushion_level = 'max'
        elif 'ego' in full_text:
            specs.cushion_type = 'Altra EGO'
            specs.cushion_level = 'moderate'

        return specs if specs.name else None


# ============================================================================
# MIZUNO SCRAPER
# ============================================================================
class MizunoScraper(SyncBrandScraper):
    BRAND_NAME = 'Mizuno'
    BRAND_SLUG = 'mizuno'
    BASE_URL = 'https://www.mizunousa.com'
    CATALOG_URLS = [
        'https://www.mizunousa.com/category/running+mens+running+shoes.do',
        'https://www.mizunousa.com/category/running+womens+running+shoes.do',
    ]

    def _extract_product_urls(self, html: str) -> Set[str]:
        urls = set()
        soup = BeautifulSoup(html, 'lxml')
        for link in soup.select('a[href*="/product/"], a[href$=".do"]'):
            href = link.get('href', '')
            if '/product/' in href or (href.endswith('.do') and 'category' not in href):
                urls.add(self._normalize_url(href))
        return urls

    def _parse_product_page(self, html: str, url: str) -> Optional[ProductSpecs]:
        soup = BeautifulSoup(html, 'lxml')
        specs = ProductSpecs(brand=self.BRAND_NAME)

        json_ld = self._extract_json_ld(html)
        if json_ld:
            specs.name = json_ld.get('name', '')
            specs.msrp = self._parse_price(str(json_ld.get('offers', {}).get('price', '')))

        if not specs.name:
            title = soup.select_one('h1.product-name, h1')
            if title:
                specs.name = title.get_text(strip=True)

        full_text = soup.get_text(strip=True).lower()
        name_lower = (specs.name or '').lower()

        if any(m in name_lower for m in ['wave mujin', 'wave daichi']):
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

        if any(m in name_lower for m in ['wave inspire', 'wave horizon', 'wave paradox']):
            specs.subcategory = 'stability'
        elif any(m in name_lower for m in ['wave rebellion', 'wave duel']):
            specs.subcategory = 'racing'
        else:
            specs.subcategory = 'neutral'

        if 'enerzy' in full_text:
            specs.cushion_type = 'Mizuno Enerzy'
            specs.cushion_level = 'max'
        elif 'wave plate' in full_text or 'mizuno wave' in full_text:
            specs.cushion_type = 'Mizuno Wave'

        return specs if specs.name else None


# ============================================================================
# MAIN SCRAPER RUNNER
# ============================================================================
SCRAPER_CLASSES = {
    'nike': NikeScraper,
    'hoka': HokaScraper,
    'brooks': BrooksScraper,
    'asics': AsicsScraper,
    'saucony': SauconyScraper,
    'adidas': AdidasScraper,
    'new-balance': NewBalanceScraper,
    'on': OnRunningScraper,
    'altra': AltraScraper,
    'mizuno': MizunoScraper,
}


def run_scraper(scraper_class, context, session):
    """Run a single brand scraper."""
    scraper = scraper_class(context)
    brand_slug = scraper.BRAND_SLUG

    print(f"\n{'='*60}")
    print(f"SCRAPING: {scraper.BRAND_NAME}")
    print(f"{'='*60}")

    # Get brand from DB
    result = session.execute(select(Brand).where(Brand.slug == brand_slug))
    brand = result.scalar_one_or_none()
    if not brand:
        print(f"ERROR: Brand '{brand_slug}' not found in database!")
        return 0

    # Get running category
    result = session.execute(select(Category).where(Category.slug == 'running'))
    running_cat = result.scalar_one_or_none()
    if not running_cat:
        print("ERROR: Running category not found!")
        return 0

    # Discover products
    print("\nPhase 1: Discovering products...")
    product_urls = scraper.discover_all_products()
    print(f"  Total discovered: {len(product_urls)}")

    if not product_urls:
        print("  No products found - site may be blocking requests")
        return 0

    # Scrape products
    print(f"\nPhase 2: Scraping {len(product_urls)} products...")
    added = 0
    skipped = 0
    errors = 0

    for i, url in enumerate(product_urls):
        print(f"  [{i+1}/{len(product_urls)}] {url[:60]}...", end=" ")

        try:
            specs = scraper.scrape_product(url)
            if not specs or not specs.name:
                print("No specs")
                errors += 1
                continue

            # Create slug
            slug = specs.name.lower().replace(' ', '-').replace("'", "").replace('"', '')

            # Check if exists
            existing = session.execute(
                select(Shoe).where(Shoe.brand_id == brand.id, Shoe.slug == slug)
            )
            if existing.scalar_one_or_none():
                print("Exists")
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
                last_scraped_at=datetime.now(UTC),
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

            print(f"ADDED: {specs.name[:30]}")
            added += 1

            # Commit every 10 shoes
            if added % 10 == 0:
                session.commit()

        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1
            continue

    session.commit()

    print(f"\n  Summary for {scraper.BRAND_NAME}:")
    print(f"    Added: {added}")
    print(f"    Skipped: {skipped}")
    print(f"    Errors: {errors}")

    return added


def main():
    # Determine which brands to scrape
    brands_to_scrape = sys.argv[1:] if len(sys.argv) > 1 else list(SCRAPER_CLASSES.keys())

    print("=" * 70)
    print("MULTI-BRAND SYNCHRONOUS SCRAPER")
    print("=" * 70)
    print(f"Brands to scrape: {', '.join(brands_to_scrape)}")

    # Start browser
    print("\nStarting browser...")
    playwright = sync_playwright().start()
    browser = playwright.firefox.launch(headless=True)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        locale='en-US',
        timezone_id='America/New_York',
    )
    context.add_init_script(STEALTH_SCRIPT)
    print("Browser started!")

    total_added = 0
    results = {}

    try:
        with sync_session_maker() as session:
            for brand_slug in brands_to_scrape:
                if brand_slug not in SCRAPER_CLASSES:
                    print(f"\nUnknown brand: {brand_slug}")
                    continue

                scraper_class = SCRAPER_CLASSES[brand_slug]
                added = run_scraper(scraper_class, context, session)
                results[brand_slug] = added
                total_added += added

    finally:
        print("\nStopping browser...")
        context.close()
        browser.close()
        playwright.stop()
        print("Browser stopped.")

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    for brand, count in results.items():
        print(f"  {brand}: {count} shoes added")
    print(f"\nTOTAL ADDED: {total_added}")


if __name__ == '__main__':
    main()
