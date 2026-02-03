#!/usr/bin/env python
"""
Retailer scraper for Running Warehouse and other shoe retailers.

Retailers provide:
- Actual prices (not just MSRP)
- Stock/size availability
- Often weight/drop/stack specs
- Coverage for brands that block direct scraping

Usage:
    python retailer_scraper.py                    # Scrape all active retailers
    python retailer_scraper.py running_warehouse  # Scrape specific retailer
    python retailer_scraper.py --list            # List available retailers
"""

import sys
import re
import json
import time
import requests
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Dict, Any
from decimal import Decimal
from dataclasses import dataclass, field
from datetime import datetime, UTC
from urllib.parse import urljoin, urlparse, parse_qs

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bs4 import BeautifulSoup
from sqlalchemy import select, text

from app.core.database import sync_session_maker
from app.models import Brand, ShoeModel, ShoeProduct, ShoeOffer, Merchant, Gender, Terrain


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class RetailerProduct:
    """A product listing from a retailer."""
    name: str
    brand: str
    url: str
    price: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    msrp: Optional[Decimal] = None
    in_stock: bool = True
    sizes_available: Dict[str, bool] = field(default_factory=dict)
    image_url: Optional[str] = None
    style_id: Optional[str] = None
    gender: Optional[str] = None
    # Specs
    weight_oz: Optional[Decimal] = None
    drop_mm: Optional[Decimal] = None
    stack_heel_mm: Optional[Decimal] = None
    stack_forefoot_mm: Optional[Decimal] = None
    # Classification
    terrain: Optional[str] = None
    category: Optional[str] = None


# ============================================================================
# BASE RETAILER SCRAPER
# ============================================================================

class BaseRetailerScraper(ABC):
    """Base class for retailer scrapers."""

    MERCHANT_SLUG: str = ''
    MERCHANT_NAME: str = ''
    BASE_URL: str = ''
    RATE_LIMIT_RPM: int = 30

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self.last_request_time = 0
        self.delay = 60.0 / self.RATE_LIMIT_RPM

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request_time = time.time()

    def fetch(self, url: str) -> Optional[str]:
        """Fetch a URL with rate limiting."""
        self._rate_limit()
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"    Error fetching {url}: {e}")
            return None

    @abstractmethod
    def get_category_urls(self) -> List[str]:
        """Return list of category/listing URLs to scrape."""
        pass

    @abstractmethod
    def parse_listing_page(self, html: str, url: str) -> List[str]:
        """Parse a listing page and return product URLs."""
        pass

    @abstractmethod
    def parse_product_page(self, html: str, url: str) -> Optional[RetailerProduct]:
        """Parse a product page and return product data."""
        pass

    def scrape_all(self) -> List[RetailerProduct]:
        """Scrape all products from this retailer."""
        print(f"\n{'='*60}")
        print(f"Scraping: {self.MERCHANT_NAME}")
        print(f"{'='*60}")

        # Get all category URLs
        category_urls = self.get_category_urls()
        print(f"Found {len(category_urls)} category pages to scrape")

        # Collect product URLs
        product_urls = set()
        for cat_url in category_urls:
            print(f"\n  Category: {cat_url}")
            html = self.fetch(cat_url)
            if html:
                urls = self.parse_listing_page(html, cat_url)
                product_urls.update(urls)
                print(f"    Found {len(urls)} products, total unique: {len(product_urls)}")

        print(f"\nTotal unique products: {len(product_urls)}")

        # Scrape product pages
        products = []
        for i, url in enumerate(product_urls):
            if i % 20 == 0:
                print(f"  Progress: {i}/{len(product_urls)}")

            html = self.fetch(url)
            if html:
                product = self.parse_product_page(html, url)
                if product:
                    products.append(product)

        print(f"\nSuccessfully scraped {len(products)} products")
        return products


# ============================================================================
# RUNNING WAREHOUSE SCRAPER
# ============================================================================

class RunningWarehouseScraper(BaseRetailerScraper):
    """Scraper for Running Warehouse."""

    MERCHANT_SLUG = 'running_warehouse'
    MERCHANT_NAME = 'Running Warehouse'
    BASE_URL = 'https://www.runningwarehouse.com'
    RATE_LIMIT_RPM = 20

    # Brand mapping (RW name -> our slug)
    BRAND_MAP = {
        'nike': 'nike',
        'hoka': 'hoka',
        'brooks': 'brooks',
        'asics': 'asics',
        'saucony': 'saucony',
        'new balance': 'new-balance',
        'adidas': 'adidas',
        'on': 'on',
        'altra': 'altra',
        'mizuno': 'mizuno',
    }

    def get_category_urls(self) -> List[str]:
        """Get Running Warehouse category URLs for running shoes."""
        return [
            # Men's road
            f'{self.BASE_URL}/mensrunningshoes.html',
            # Men's trail
            f'{self.BASE_URL}/menstrailrunningshoes.html',
            # Women's road
            f'{self.BASE_URL}/womensrunningshoes.html',
            # Women's trail
            f'{self.BASE_URL}/womenstrailrunningshoes.html',
        ]

    def parse_listing_page(self, html: str, url: str) -> List[str]:
        """Parse listing page and return product URLs."""
        soup = BeautifulSoup(html, 'lxml')
        product_urls = []

        # Find product links - RW uses specific class patterns
        for link in soup.select('a.product-link, a[href*="/search/"]'):
            href = link.get('href', '')
            if href and '/search/' in href and href.endswith('.html'):
                full_url = urljoin(self.BASE_URL, href)
                if full_url not in product_urls:
                    product_urls.append(full_url)

        # Also try JSON-LD data
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'ItemList':
                    for item in data.get('itemListElement', []):
                        item_url = item.get('url')
                        if item_url:
                            product_urls.append(item_url)
            except json.JSONDecodeError:
                continue

        return list(set(product_urls))

    def parse_product_page(self, html: str, url: str) -> Optional[RetailerProduct]:
        """Parse product page and extract data."""
        soup = BeautifulSoup(html, 'lxml')

        # Try JSON-LD first
        product = None
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    product = self._parse_json_ld(data, url)
                    break
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Product':
                            product = self._parse_json_ld(item, url)
                            break
            except json.JSONDecodeError:
                continue

        if not product:
            # Fallback to HTML parsing
            product = self._parse_html(soup, url)

        if product:
            # Extract specs from page
            self._extract_specs(soup, product)

        return product

    def _parse_json_ld(self, data: dict, url: str) -> RetailerProduct:
        """Parse JSON-LD product data."""
        name = data.get('name', '')
        brand = data.get('brand', {})
        if isinstance(brand, dict):
            brand = brand.get('name', '')

        offers = data.get('offers', {})
        if isinstance(offers, list) and offers:
            offers = offers[0]

        price = None
        if isinstance(offers, dict):
            price_str = offers.get('price')
            if price_str:
                try:
                    price = Decimal(str(price_str))
                except:
                    pass

        image = data.get('image')
        if isinstance(image, list) and image:
            image = image[0]

        return RetailerProduct(
            name=name,
            brand=brand.lower() if brand else '',
            url=url,
            price=price,
            image_url=image,
            style_id=data.get('sku'),
            in_stock=offers.get('availability', '').lower() != 'outofstock' if isinstance(offers, dict) else True,
        )

    def _parse_html(self, soup: BeautifulSoup, url: str) -> Optional[RetailerProduct]:
        """Fallback HTML parsing."""
        name_elem = soup.select_one('h1.product-name, h1[itemprop="name"], h1')
        if not name_elem:
            return None

        name = name_elem.get_text(strip=True)

        # Try to extract brand from name or breadcrumbs
        brand = ''
        breadcrumbs = soup.select('nav.breadcrumb a, .breadcrumb a')
        for bc in breadcrumbs:
            bc_text = bc.get_text(strip=True).lower()
            if bc_text in self.BRAND_MAP:
                brand = bc_text
                break

        # Price
        price = None
        price_elem = soup.select_one('.product-price, [itemprop="price"], .price')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', price_text)
            if match:
                try:
                    price = Decimal(match.group(1).replace(',', ''))
                except:
                    pass

        return RetailerProduct(
            name=name,
            brand=brand,
            url=url,
            price=price,
        )

    def _extract_specs(self, soup: BeautifulSoup, product: RetailerProduct):
        """Extract shoe specs from page."""
        # Look for specs table or list
        specs_text = soup.get_text().lower()

        # Weight
        weight_match = re.search(r'weight[:\s]*(\d+(?:\.\d+)?)\s*(?:oz|ounces)', specs_text)
        if weight_match:
            try:
                product.weight_oz = Decimal(weight_match.group(1))
            except:
                pass

        # Drop
        drop_match = re.search(r'(?:heel[- ]?toe\s*)?drop[:\s]*(\d+(?:\.\d+)?)\s*mm', specs_text)
        if drop_match:
            try:
                product.drop_mm = Decimal(drop_match.group(1))
            except:
                pass

        # Stack height
        stack_match = re.search(r'(?:heel\s*)?stack[:\s]*(\d+(?:\.\d+)?)\s*mm', specs_text)
        if stack_match:
            try:
                product.stack_heel_mm = Decimal(stack_match.group(1))
            except:
                pass

        # Gender from URL or name
        url_lower = product.url.lower()
        name_lower = product.name.lower()
        if 'mens' in url_lower or "men's" in name_lower or 'men' in url_lower:
            product.gender = 'mens'
        elif 'womens' in url_lower or "women's" in name_lower or 'women' in url_lower:
            product.gender = 'womens'

        # Terrain
        if 'trail' in name_lower or 'trail' in url_lower:
            product.terrain = 'trail'
        else:
            product.terrain = 'road'

        # Size availability
        size_elems = soup.select('[data-size], .size-option, .size-selector option')
        for elem in size_elems:
            size = elem.get('data-size') or elem.get_text(strip=True)
            if size:
                is_available = 'out-of-stock' not in elem.get('class', [])
                product.sizes_available[size] = is_available


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def normalize_model_name(name: str, brand: str) -> str:
    """Normalize a product name to a model name."""
    # Remove brand prefix
    name = name.lower().strip()
    brand_lower = brand.lower()
    if name.startswith(brand_lower):
        name = name[len(brand_lower):].strip()

    # Remove common suffixes
    name = re.sub(r'\s*(men\'?s?|women\'?s?|unisex)\s*', ' ', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*(road|trail)\s*running\s*shoe[s]?\s*', ' ', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*running\s*shoe[s]?\s*', ' ', name, flags=re.IGNORECASE)

    # Remove colorway (usually after a slash or dash at the end)
    name = re.sub(r'[-/]\s*[\w\s]+$', '', name)

    # Clean up
    name = ' '.join(name.split())
    return name.title()


def save_retailer_products(merchant_slug: str, products: List[RetailerProduct]):
    """Save retailer products to the 3-layer model."""
    print(f"\n{'='*60}")
    print(f"Saving to database: {merchant_slug}")
    print(f"{'='*60}")

    with sync_session_maker() as session:
        # Get merchant
        merchant = session.execute(
            select(Merchant).where(Merchant.slug == merchant_slug)
        ).scalar_one_or_none()

        if not merchant:
            print(f"  ERROR: Merchant '{merchant_slug}' not found!")
            return

        # Build brand cache
        brands = {}
        for brand in session.execute(select(Brand)).scalars():
            brands[brand.slug] = brand
            brands[brand.name.lower()] = brand

        stats = {
            'models_created': 0,
            'products_created': 0,
            'offers_created': 0,
            'offers_updated': 0,
            'skipped': 0,
        }

        for product in products:
            # Find brand
            brand_key = product.brand.lower()
            brand = brands.get(brand_key)
            if not brand:
                # Try mapping
                for alias, slug in RunningWarehouseScraper.BRAND_MAP.items():
                    if alias in brand_key:
                        brand = brands.get(slug)
                        break

            if not brand:
                stats['skipped'] += 1
                continue

            # Normalize model name
            model_name = normalize_model_name(product.name, brand.name)
            model_slug = model_name.lower().replace(' ', '-').replace("'", "")

            # Determine gender
            gender = Gender.MENS
            if product.gender == 'womens':
                gender = Gender.WOMENS
            elif product.gender == 'unisex':
                gender = Gender.UNISEX

            # Find or create model
            model = session.execute(
                select(ShoeModel).where(
                    ShoeModel.brand_id == brand.id,
                    ShoeModel.slug == model_slug,
                    ShoeModel.gender == gender,
                )
            ).scalar_one_or_none()

            if not model:
                terrain = Terrain.TRAIL if product.terrain == 'trail' else Terrain.ROAD
                model = ShoeModel(
                    brand_id=brand.id,
                    name=model_name,
                    slug=model_slug,
                    gender=gender,
                    terrain=terrain,
                    typical_weight_oz=product.weight_oz,
                    typical_drop_mm=product.drop_mm,
                    typical_stack_heel_mm=product.stack_heel_mm,
                )
                session.add(model)
                session.flush()
                stats['models_created'] += 1

            # Find or create product
            product_slug = product.name.lower().replace(' ', '-').replace("'", "")[:200]
            shoe_product = session.execute(
                select(ShoeProduct).where(
                    ShoeProduct.model_id == model.id,
                    ShoeProduct.slug == product_slug,
                )
            ).scalar_one_or_none()

            if not shoe_product:
                shoe_product = ShoeProduct(
                    model_id=model.id,
                    name=product.name,
                    slug=product_slug,
                    msrp_usd=product.msrp or product.price,
                    primary_image_url=product.image_url,
                    weight_oz=product.weight_oz,
                    drop_mm=product.drop_mm,
                    stack_height_heel_mm=product.stack_heel_mm,
                    discovered_from=f"retailer:{merchant_slug}",
                    discovered_at=datetime.now(UTC),
                )
                session.add(shoe_product)
                session.flush()
                stats['products_created'] += 1

            # Find or update offer
            offer = session.execute(
                select(ShoeOffer).where(
                    ShoeOffer.product_id == shoe_product.id,
                    ShoeOffer.merchant == merchant_slug,
                )
            ).scalar_one_or_none()

            if offer:
                # Update existing offer
                offer.price = product.price
                offer.sale_price = product.sale_price
                offer.in_stock = product.in_stock
                offer.sizes_available = product.sizes_available or None
                offer.last_seen_at = datetime.now(UTC)
                if product.price != offer.price:
                    offer.price_updated_at = datetime.now(UTC)
                stats['offers_updated'] += 1
            else:
                # Create new offer
                offer = ShoeOffer(
                    product_id=shoe_product.id,
                    merchant=merchant_slug,
                    url=product.url,
                    price=product.price,
                    sale_price=product.sale_price,
                    in_stock=product.in_stock,
                    sizes_available=product.sizes_available or None,
                )
                session.add(offer)
                stats['offers_created'] += 1

            # Commit periodically
            if (stats['models_created'] + stats['products_created'] + stats['offers_created']) % 50 == 0:
                session.commit()
                print(f"  Progress: {stats}")

        session.commit()

        # Update merchant last scrape time
        merchant.last_scrape_at = datetime.now(UTC)
        merchant.last_scrape_status = 'success'
        session.commit()

        print(f"\n  Summary:")
        print(f"    Models created: {stats['models_created']}")
        print(f"    Products created: {stats['products_created']}")
        print(f"    Offers created: {stats['offers_created']}")
        print(f"    Offers updated: {stats['offers_updated']}")
        print(f"    Skipped (unknown brand): {stats['skipped']}")


def print_retailer_report():
    """Print a report of retailer data in the database."""
    print("\n" + "=" * 70)
    print("RETAILER DATA REPORT")
    print("=" * 70)

    with sync_session_maker() as session:
        # Models by brand
        result = session.execute(text('''
            SELECT b.name, COUNT(DISTINCT sm.id) as models, COUNT(DISTINCT sp.id) as products
            FROM shoe_models sm
            JOIN brands b ON sm.brand_id = b.id
            LEFT JOIN shoe_products sp ON sp.model_id = sm.id
            GROUP BY b.name
            ORDER BY models DESC
        '''))

        print("\nModels/Products by Brand:")
        print("-" * 50)
        for row in result:
            print(f"  {row[0]:15} {row[1]:4} models, {row[2]:4} products")

        # Offers by merchant
        result = session.execute(text('''
            SELECT merchant, COUNT(*) as offers,
                   SUM(CASE WHEN in_stock THEN 1 ELSE 0 END) as in_stock,
                   AVG(price) as avg_price
            FROM shoe_offers
            GROUP BY merchant
            ORDER BY offers DESC
        '''))

        print("\nOffers by Merchant:")
        print("-" * 50)
        for row in result:
            avg = f"${row[3]:.2f}" if row[3] else "N/A"
            print(f"  {row[0]:20} {row[1]:5} offers ({row[2]} in stock, avg {avg})")


# ============================================================================
# MAIN
# ============================================================================

SCRAPERS = {
    'running_warehouse': RunningWarehouseScraper,
}


def main():
    args = sys.argv[1:]

    if '--list' in args:
        print("Available retailer scrapers:")
        for slug, cls in SCRAPERS.items():
            print(f"  {slug}: {cls.MERCHANT_NAME}")
        return

    if '--report' in args:
        print_retailer_report()
        return

    # Determine which scrapers to run
    if args:
        scraper_slugs = [a for a in args if not a.startswith('--')]
    else:
        scraper_slugs = list(SCRAPERS.keys())

    print("=" * 70)
    print("RETAILER SCRAPER")
    print("=" * 70)
    print(f"Retailers: {', '.join(scraper_slugs)}")

    for slug in scraper_slugs:
        if slug not in SCRAPERS:
            print(f"\nUnknown retailer: {slug}")
            continue

        scraper_cls = SCRAPERS[slug]
        scraper = scraper_cls()

        try:
            products = scraper.scrape_all()
            if products:
                save_retailer_products(slug, products)
        except Exception as e:
            print(f"\nError scraping {slug}: {e}")
            import traceback
            traceback.print_exc()

    # Print final report
    print_retailer_report()


if __name__ == '__main__':
    main()
