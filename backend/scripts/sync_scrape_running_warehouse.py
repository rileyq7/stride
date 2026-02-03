#!/usr/bin/env python
"""
Synchronous Running Warehouse scraper - scrape retailer for shoe offers.
Uses Playwright's sync API for JS-rendered pages.

This scraper creates ShoeOffer records linked to existing ShoeProducts,
or creates new ShoeModel + ShoeProduct if not found.
"""

import sys
import time
import re
import json
from pathlib import Path
from decimal import Decimal
from datetime import datetime, UTC
from typing import Optional, List, Set, Dict
from dataclasses import dataclass, field

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
from sqlalchemy import select, func

from app.core.database import sync_session_maker
from app.models import Brand
from app.models.catalog import (
    ShoeModel, ShoeProduct, ShoeOffer, Merchant,
    Gender, Terrain, ShoeCategory
)

from sync_scraper_base import SyncBrandScraper, ProductSpecs


@dataclass
class RetailerProduct:
    """Product data from a retailer."""
    brand_name: str
    product_name: str
    url: str
    price: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    in_stock: bool = True
    sizes_available: Optional[Dict[str, bool]] = None
    primary_image_url: Optional[str] = None
    image_urls: List[str] = field(default_factory=list)
    style_id: Optional[str] = None
    gender: Optional[str] = None
    terrain: Optional[str] = None
    weight_oz: Optional[Decimal] = None
    drop_mm: Optional[Decimal] = None
    stack_height_heel_mm: Optional[Decimal] = None
    stack_height_forefoot_mm: Optional[Decimal] = None


class SyncRunningWarehouseScraper(SyncBrandScraper):
    """Synchronous Running Warehouse scraper using Playwright."""

    BRAND_NAME = 'Running Warehouse'
    BASE_URL = 'https://www.runningwarehouse.com'
    MERCHANT_SLUG = 'running_warehouse'

    # Category pages to scrape
    CATALOG_URLS = [
        # Men's road running
        'https://www.runningwarehouse.com/catpage-MBESTUSE.html',
        # Women's road running
        'https://www.runningwarehouse.com/catpage-WBESTUSE.html',
        # Men's trail
        'https://www.runningwarehouse.com/trailshoesmen.html',
        # Women's trail
        'https://www.runningwarehouse.com/trailshoeswomen.html',
    ]

    # Map brands from RW to our DB slugs
    BRAND_MAP = {
        'adidas': 'adidas',
        'asics': 'asics',
        'brooks': 'brooks',
        'hoka': 'hoka',
        'new balance': 'new-balance',
        'nike': 'nike',
        'on': 'on',
        'saucony': 'saucony',
        'altra': 'altra',
        'mizuno': 'mizuno',
        'salomon': 'salomon',
        'la sportiva': 'la-sportiva',
    }

    def _extract_product_urls(self, html: str) -> Set[str]:
        """Extract product URLs from catalog page."""
        product_urls = set()
        soup = BeautifulSoup(html, 'lxml')

        # Running Warehouse product pages use /descpage-*.html pattern
        for link in soup.select('a[href*="descpage-"]'):
            href = link.get('href', '')
            if not href or 'descpage-' not in href:
                continue

            # Clean up href - may contain newlines and multiple URLs
            href = href.strip()

            # If there are newlines, take the part with descpage
            if '\n' in href:
                for part in href.split('\n'):
                    part = part.strip()
                    if 'descpage-' in part and '.html' in part:
                        href = part
                        break

            if 'descpage-' not in href or '.html' not in href:
                continue

            # Normalize URL
            if href.startswith('/'):
                href = f"{self.BASE_URL}{href}"
            elif not href.startswith('http'):
                href = f"{self.BASE_URL}/{href}"

            # Remove query params and fragments
            href = href.split('?')[0].split('#')[0]
            product_urls.add(href)

        return product_urls

    def _parse_product_page(self, html: str, url: str) -> Optional[ProductSpecs]:
        """Parse Running Warehouse product page."""
        soup = BeautifulSoup(html, 'lxml')
        specs = ProductSpecs(brand='')

        # Extract from JSON-LD first
        json_ld = self._extract_json_ld(html)
        if json_ld:
            specs.name = json_ld.get('name', '')
            specs.brand = json_ld.get('brand', {}).get('name', '') if isinstance(json_ld.get('brand'), dict) else json_ld.get('brand', '')
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

        # Fallback to page elements
        if not specs.name:
            title = soup.select_one('h1.product-title, h1.pdp-title, h1')
            if title:
                specs.name = title.get_text(strip=True)

        if not specs.brand:
            brand_el = soup.select_one('.brand-name, .pdp-brand')
            if brand_el:
                specs.brand = brand_el.get_text(strip=True)

        if not specs.msrp:
            price = soup.select_one('.product-price, .pdp-price, .price')
            if price:
                specs.msrp = self._parse_price(price.get_text())

        # Try to extract specs from product details
        self._extract_rw_specs(soup, specs)

        return specs if specs.name else None

    def _extract_rw_specs(self, soup: BeautifulSoup, specs: ProductSpecs):
        """Extract Running Warehouse specific specs."""
        # Look for specs table or list
        specs_text = ''
        for el in soup.select('.product-specs, .pdp-specs, .specs-table, dl, table'):
            specs_text += el.get_text(' ', strip=True).lower()

        # Weight
        weight_match = re.search(r'weight[:\s]*(\d+(?:\.\d+)?)\s*(?:oz|ounces)', specs_text)
        if weight_match:
            specs.weight_oz = Decimal(weight_match.group(1))

        # Drop
        drop_match = re.search(r'(?:drop|offset)[:\s]*(\d+(?:\.\d+)?)\s*mm', specs_text)
        if drop_match:
            specs.drop_mm = Decimal(drop_match.group(1))

        # Stack height
        stack_match = re.search(r'stack[:\s]*(\d+(?:\.\d+)?)\s*mm', specs_text)
        if stack_match:
            specs.stack_height_heel_mm = Decimal(stack_match.group(1))

        # Terrain from name or specs
        name_lower = (specs.name or '').lower()
        if 'trail' in name_lower or 'trail' in specs_text:
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

    def scrape_product_full(self, product_url: str) -> Optional[RetailerProduct]:
        """Scrape a product page and return full retailer product data."""
        page = self.context.new_page()
        try:
            page.goto(product_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(1)
            self._dismiss_popups(page)
            time.sleep(1)

            html = page.content()
            soup = BeautifulSoup(html, 'lxml')

            product = RetailerProduct(
                brand_name='',
                product_name='',
                url=product_url,
            )

            # Extract from JSON-LD first
            json_ld = self._extract_json_ld(html)
            if json_ld:
                product.product_name = json_ld.get('name', '')
                brand_data = json_ld.get('brand')
                if isinstance(brand_data, dict):
                    product.brand_name = brand_data.get('name', '')
                elif isinstance(brand_data, str):
                    product.brand_name = brand_data
                product.style_id = json_ld.get('sku')

                offers = json_ld.get('offers', {})
                if isinstance(offers, dict):
                    product.price = self._parse_price(str(offers.get('price', '')))
                    availability = offers.get('availability', '')
                    product.in_stock = 'InStock' in availability
                elif isinstance(offers, list) and offers:
                    product.price = self._parse_price(str(offers[0].get('price', '')))

                image = json_ld.get('image')
                if isinstance(image, str):
                    product.primary_image_url = image
                elif isinstance(image, list) and image:
                    product.primary_image_url = image[0]
                    product.image_urls = image[:10]

            # FALLBACKS - Running Warehouse doesn't use JSON-LD consistently

            # Product name from H1
            if not product.product_name:
                title = soup.select_one('h1')
                if title:
                    product.product_name = title.get_text(strip=True)

            # Brand from product name (first word is usually the brand)
            if not product.brand_name:
                product.brand_name = self._extract_brand_from_name(product.product_name)

            # Price from .price element
            if not product.price:
                price_el = soup.select_one('.price')
                if price_el:
                    product.price = self._parse_price(price_el.get_text())

            # Sale price
            sale_el = soup.select_one('.sale-price, .discount-price, .was-price')
            if sale_el:
                sale_price = self._parse_price(sale_el.get_text())
                if sale_price and product.price and sale_price < product.price:
                    product.sale_price = sale_price

            # Image from meta or img tags
            if not product.primary_image_url:
                meta_img = soup.select_one('meta[property="og:image"]')
                if meta_img:
                    product.primary_image_url = meta_img.get('content')
                else:
                    # Look for product image
                    img = soup.select_one('.product-image img, .pdp-image img, img[data-product]')
                    if img:
                        product.primary_image_url = img.get('src')

            # Extract sizes
            product.sizes_available = self._extract_sizes(soup)

            # Extract sale price if different
            sale_el = soup.select_one('.sale-price, .discount-price')
            if sale_el:
                sale_price = self._parse_price(sale_el.get_text())
                if sale_price and product.price and sale_price < product.price:
                    product.sale_price = sale_price

            # Gender from URL or name
            url_lower = product_url.lower()
            name_lower = product.product_name.lower()
            if 'women' in url_lower or 'women' in name_lower:
                product.gender = 'womens'
            elif 'men' in url_lower or 'men' in name_lower:
                product.gender = 'mens'

            # Terrain
            if 'trail' in url_lower or 'trail' in name_lower:
                product.terrain = 'trail'
            else:
                product.terrain = 'road'

            # Extract specs
            self._extract_full_specs(soup, product)

            return product if product.product_name else None

        except Exception as e:
            print(f"  ERROR scraping {product_url}: {e}")
            return None
        finally:
            page.close()

    def _extract_brand_from_name(self, name: str) -> str:
        """Try to extract brand from product name."""
        if not name:
            return ''
        name_lower = name.lower()
        for brand in self.BRAND_MAP.keys():
            if name_lower.startswith(brand):
                return brand.title()
        return ''

    def _extract_sizes(self, soup: BeautifulSoup) -> Optional[Dict[str, bool]]:
        """Extract available sizes."""
        sizes = {}
        for size_el in soup.select('.size-option, .size-selector option, [data-size]'):
            size = size_el.get('data-size') or size_el.get_text(strip=True)
            if size:
                # Check if out of stock
                is_available = 'out-of-stock' not in size_el.get('class', [])
                sizes[size] = is_available
        return sizes if sizes else None

    def _extract_full_specs(self, soup: BeautifulSoup, product: RetailerProduct):
        """Extract full specs from page."""
        specs_text = ''
        for el in soup.select('.product-specs, .pdp-specs, .specs-table, dl, table'):
            specs_text += el.get_text(' ', strip=True).lower()

        # Weight
        weight_match = re.search(r'weight[:\s]*(\d+(?:\.\d+)?)\s*(?:oz|ounces)', specs_text)
        if weight_match:
            product.weight_oz = Decimal(weight_match.group(1))

        # Drop
        drop_match = re.search(r'(?:drop|offset)[:\s]*(\d+(?:\.\d+)?)\s*mm', specs_text)
        if drop_match:
            product.drop_mm = Decimal(drop_match.group(1))

        # Stack height
        heel_match = re.search(r'heel[:\s]*(\d+(?:\.\d+)?)\s*mm', specs_text)
        if heel_match:
            product.stack_height_heel_mm = Decimal(heel_match.group(1))

        forefoot_match = re.search(r'forefoot[:\s]*(\d+(?:\.\d+)?)\s*mm', specs_text)
        if forefoot_match:
            product.stack_height_forefoot_mm = Decimal(forefoot_match.group(1))


def normalize_model_name(name: str, brand_name: str) -> str:
    """Normalize product name to model name."""
    # Remove brand prefix
    name_lower = name.lower()
    brand_lower = brand_name.lower()

    if name_lower.startswith(brand_lower):
        name = name[len(brand_lower):].strip()

    # Remove common suffixes
    patterns_to_remove = [
        r"\s+men'?s?\s*$",
        r"\s+women'?s?\s*$",
        r"\s+unisex\s*$",
        r"\s+v\d+\s*$",  # version numbers at end
    ]
    for pattern in patterns_to_remove:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    # Remove colorway (after hyphen or parentheses)
    name = re.sub(r'\s*[-/]\s*[\w\s/]+$', '', name)
    name = re.sub(r'\s*\([^)]+\)\s*$', '', name)

    return name.strip()


def find_or_create_model(
    session,
    brand_id,
    model_name: str,
    gender: Gender,
    terrain: Terrain,
    specs: RetailerProduct
) -> ShoeModel:
    """Find existing model or create new one."""
    model_slug = model_name.lower().replace(' ', '-').replace("'", "")[:200]

    # Check if model exists
    existing = session.execute(
        select(ShoeModel).where(
            ShoeModel.brand_id == brand_id,
            ShoeModel.slug == model_slug,
            ShoeModel.gender == gender.value,
        )
    ).scalar_one_or_none()

    if existing:
        return existing

    # Create new model
    new_model = ShoeModel(
        brand_id=brand_id,
        name=model_name,
        slug=model_slug,
        gender=gender.value,
        terrain=terrain.value,
        typical_weight_oz=specs.weight_oz,
        typical_drop_mm=specs.drop_mm,
        typical_stack_heel_mm=specs.stack_height_heel_mm,
        typical_stack_forefoot_mm=specs.stack_height_forefoot_mm,
    )
    session.add(new_model)
    session.flush()
    return new_model


def find_or_create_product(
    session,
    model: ShoeModel,
    product_name: str,
    specs: RetailerProduct
) -> ShoeProduct:
    """Find existing product or create new one."""
    product_slug = product_name.lower().replace(' ', '-').replace("'", "")[:300]

    # Check if product exists
    existing = session.execute(
        select(ShoeProduct).where(
            ShoeProduct.model_id == model.id,
            ShoeProduct.slug == product_slug,
        )
    ).scalar_one_or_none()

    if existing:
        return existing

    # Create new product
    new_product = ShoeProduct(
        model_id=model.id,
        name=product_name,
        slug=product_slug,
        msrp_usd=specs.price,
        primary_image_url=specs.primary_image_url,
        image_urls=specs.image_urls if specs.image_urls else None,
        weight_oz=specs.weight_oz,
        drop_mm=specs.drop_mm,
        stack_height_heel_mm=specs.stack_height_heel_mm,
        stack_height_forefoot_mm=specs.stack_height_forefoot_mm,
        discovered_from='running_warehouse',
        discovered_at=datetime.now(UTC),
        needs_review=True,
    )
    session.add(new_product)
    session.flush()
    return new_product


def create_or_update_offer(
    session,
    product: ShoeProduct,
    specs: RetailerProduct,
    merchant_slug: str = 'running_warehouse'
) -> ShoeOffer:
    """Create or update offer for this product from merchant."""
    # Check if offer exists
    existing = session.execute(
        select(ShoeOffer).where(
            ShoeOffer.product_id == product.id,
            ShoeOffer.merchant == merchant_slug,
            ShoeOffer.url == specs.url,
        )
    ).scalar_one_or_none()

    now = datetime.now(UTC)

    if existing:
        # Update existing offer
        existing.price = specs.price
        existing.sale_price = specs.sale_price
        existing.in_stock = specs.in_stock
        existing.sizes_available = specs.sizes_available
        existing.last_seen_at = now
        existing.price_updated_at = now
        return existing

    # Create new offer
    new_offer = ShoeOffer(
        product_id=product.id,
        merchant=merchant_slug,
        url=specs.url,
        price=specs.price,
        sale_price=specs.sale_price,
        in_stock=specs.in_stock,
        sizes_available=specs.sizes_available,
        first_seen_at=now,
        last_seen_at=now,
        price_updated_at=now,
    )
    session.add(new_offer)
    return new_offer


def main():
    print("=" * 70)
    print("RUNNING WAREHOUSE SYNCHRONOUS SCRAPER")
    print("=" * 70)

    scraper = SyncRunningWarehouseScraper()

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

        # Limit for testing
        if '--limit' in sys.argv:
            limit_idx = sys.argv.index('--limit')
            if limit_idx + 1 < len(sys.argv):
                limit = int(sys.argv[limit_idx + 1])
                product_urls = product_urls[:limit]
                print(f"Limiting to {limit} products for testing")

        # Scrape products and save to DB
        print("\n" + "=" * 70)
        print("PHASE 2: SCRAPING & SAVING TO DATABASE")
        print("=" * 70)

        with sync_session_maker() as session:
            # Get brand map from DB
            brands = session.execute(select(Brand)).scalars().all()
            brand_by_slug = {b.slug: b for b in brands}

            stats = {
                'models_created': 0,
                'products_created': 0,
                'offers_created': 0,
                'offers_updated': 0,
                'skipped_unknown_brand': 0,
                'errors': 0,
            }

            for i, url in enumerate(product_urls):
                print(f"\n[{i+1}/{len(product_urls)}] {url}")

                try:
                    product_data = scraper.scrape_product_full(url)
                    if not product_data or not product_data.product_name:
                        print("  -> No data found")
                        stats['errors'] += 1
                        continue

                    # Find brand
                    brand_name_lower = product_data.brand_name.lower()
                    brand_slug = SyncRunningWarehouseScraper.BRAND_MAP.get(brand_name_lower)
                    if not brand_slug or brand_slug not in brand_by_slug:
                        print(f"  -> Unknown brand: {product_data.brand_name}")
                        stats['skipped_unknown_brand'] += 1
                        continue

                    brand = brand_by_slug[brand_slug]

                    # Determine gender and terrain
                    gender = Gender.UNISEX
                    if product_data.gender == 'mens':
                        gender = Gender.MENS
                    elif product_data.gender == 'womens':
                        gender = Gender.WOMENS

                    terrain = Terrain.ROAD
                    if product_data.terrain == 'trail':
                        terrain = Terrain.TRAIL

                    # Normalize model name
                    model_name = normalize_model_name(product_data.product_name, product_data.brand_name)
                    if not model_name or len(model_name) < 2:
                        model_name = product_data.product_name

                    # Find or create model
                    model = find_or_create_model(
                        session, brand.id, model_name, gender, terrain, product_data
                    )
                    if not hasattr(model, '_created'):
                        model._created = model.created_at == model.updated_at
                    if model._created:
                        stats['models_created'] += 1

                    # Find or create product
                    product = find_or_create_product(
                        session, model, product_data.product_name, product_data
                    )
                    if not hasattr(product, '_created'):
                        product._created = product.created_at == product.updated_at
                    if product._created:
                        stats['products_created'] += 1

                    # Create or update offer
                    offer_existed = session.execute(
                        select(func.count()).select_from(ShoeOffer).where(
                            ShoeOffer.product_id == product.id,
                            ShoeOffer.merchant == 'running_warehouse',
                            ShoeOffer.url == product_data.url,
                        )
                    ).scalar() > 0

                    offer = create_or_update_offer(session, product, product_data)

                    if offer_existed:
                        stats['offers_updated'] += 1
                        print(f"  -> Updated: {product_data.product_name} - ${product_data.price or '?'}")
                    else:
                        stats['offers_created'] += 1
                        print(f"  -> Created: {product_data.product_name} - ${product_data.price or '?'}")

                    # Commit periodically
                    if (stats['offers_created'] + stats['offers_updated']) % 20 == 0:
                        session.commit()
                        print(f"  [Committed - Models: {stats['models_created']}, Products: {stats['products_created']}, Offers: {stats['offers_created']}]")

                except Exception as e:
                    print(f"  -> ERROR: {e}")
                    stats['errors'] += 1
                    continue

            # Final commit
            session.commit()

            print("\n" + "=" * 70)
            print("SUMMARY")
            print("=" * 70)
            print(f"Total discovered: {len(product_urls)}")
            print(f"Models created: {stats['models_created']}")
            print(f"Products created: {stats['products_created']}")
            print(f"Offers created: {stats['offers_created']}")
            print(f"Offers updated: {stats['offers_updated']}")
            print(f"Skipped (unknown brand): {stats['skipped_unknown_brand']}")
            print(f"Errors: {stats['errors']}")

    finally:
        scraper.stop_browser()


if __name__ == '__main__':
    main()
