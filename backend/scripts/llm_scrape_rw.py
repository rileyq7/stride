#!/usr/bin/env python
"""
LLM-assisted Running Warehouse scraper.
Uses Granite4 via Ollama to extract structured product data.
"""

import sys
import time
from pathlib import Path
from decimal import Decimal
from datetime import datetime, UTC
from typing import Optional, Set

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from sqlalchemy import select, func

from app.core.database import sync_session_maker
from app.models import Brand
from app.models.catalog import (
    ShoeModel, ShoeProduct, ShoeOffer,
    Gender, Terrain, ShoeCategory
)

from llm_product_extractor import extract_product_with_llm, ExtractedProduct


BASE_URL = 'https://www.runningwarehouse.com'
MERCHANT_SLUG = 'running_warehouse'

CATALOG_URLS = [
    f'{BASE_URL}/catpage-MBESTUSE.html',  # Men's road
    f'{BASE_URL}/catpage-WBESTUSE.html',  # Women's road
    f'{BASE_URL}/trailshoesmen.html',     # Men's trail
    f'{BASE_URL}/trailshoeswomen.html',   # Women's trail
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
    'topo athletic': 'topo-athletic',
    'topo': 'topo-athletic',
    'the north face': 'the-north-face',
    'north face': 'the-north-face',
    'puma': 'puma',
    'inov-8': 'inov-8',
    'inov8': 'inov-8',
    'craft': 'craft',
    '361 degrees': '361-degrees',
    '361': '361-degrees',
    'karhu': 'karhu',
    'nnormal': 'nnormal',
    'diadora': 'diadora',
    'merrell': 'merrell',
    'under armour': 'under-armour',
    'reebok': 'reebok',
    'newton': 'newton',
    'scott': 'scott',
}

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
"""


def discover_products(context) -> Set[str]:
    """Discover all product URLs from catalog pages."""
    all_urls = set()

    for catalog_url in CATALOG_URLS:
        print(f"\nCrawling: {catalog_url}")
        page = context.new_page()
        try:
            page.goto(catalog_url, wait_until='domcontentloaded', timeout=60000)
            time.sleep(3)

            # Scroll to load products
            for _ in range(10):
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(1)

            html = page.content()
            soup = BeautifulSoup(html, 'lxml')

            # Extract descpage URLs
            for link in soup.select('a[href*="descpage-"]'):
                href = link.get('href', '').strip()
                if '\n' in href:
                    for part in href.split('\n'):
                        if 'descpage-' in part and '.html' in part:
                            href = part.strip()
                            break

                if 'descpage-' in href and '.html' in href:
                    if href.startswith('/'):
                        href = f"{BASE_URL}{href}"
                    elif not href.startswith('http'):
                        href = f"{BASE_URL}/{href}"
                    href = href.split('?')[0].split('#')[0]
                    all_urls.add(href)

            print(f"  Found {len(all_urls)} total unique products")

        except Exception as e:
            print(f"  ERROR: {e}")
        finally:
            page.close()

    return all_urls


def map_gender(gender_str: Optional[str]) -> Gender:
    """Map extracted gender to enum."""
    if not gender_str:
        return Gender.UNISEX
    g = gender_str.lower()
    if 'women' in g:
        return Gender.WOMENS
    elif 'men' in g:
        return Gender.MENS
    return Gender.UNISEX


def map_terrain(terrain_str: Optional[str]) -> Terrain:
    """Map extracted terrain to enum."""
    if not terrain_str:
        return Terrain.ROAD
    t = terrain_str.lower()
    if 'trail' in t:
        return Terrain.TRAIL
    elif 'track' in t:
        return Terrain.TRACK
    return Terrain.ROAD


def map_category(cat_str: Optional[str]) -> Optional[ShoeCategory]:
    """Map extracted category to enum."""
    if not cat_str:
        return None
    c = cat_str.lower()
    mapping = {
        'daily_trainer': ShoeCategory.DAILY_TRAINER,
        'racing': ShoeCategory.RACING,
        'stability': ShoeCategory.DAILY_TRAINER,  # Map to daily trainer
        'tempo': ShoeCategory.TEMPO,
        'recovery': ShoeCategory.RECOVERY,
        'trail': ShoeCategory.TRAIL,
    }
    return mapping.get(c)


def scrape_with_llm(context, url: str) -> Optional[ExtractedProduct]:
    """Scrape a product page and extract data with LLM."""
    page = context.new_page()
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(2)

        # Dismiss popups
        for selector in ['#onetrust-accept-btn-handler', 'button:has-text("Accept")',
                         'button[aria-label="Close"]']:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=500):
                    btn.click()
                    time.sleep(0.3)
            except:
                pass

        html = page.content()

        # Check for 404
        if 'Page Not Found' in html or '404' in page.title():
            return None

        return extract_product_with_llm(html, url)

    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return None
    finally:
        page.close()


def save_product(session, brand_by_slug: dict, extracted: ExtractedProduct, url: str) -> bool:
    """Save extracted product to database."""
    # Find brand
    brand_key = extracted.brand.lower()
    brand_slug = BRAND_MAP.get(brand_key)
    if not brand_slug or brand_slug not in brand_by_slug:
        return False

    brand = brand_by_slug[brand_slug]
    gender = map_gender(extracted.gender)
    terrain = map_terrain(extracted.terrain)
    category = map_category(extracted.category)

    # Model name
    model_name = extracted.model_name or extracted.full_name or "Unknown"
    model_slug = model_name.lower().replace(' ', '-').replace("'", "")[:200]

    # Find or create model
    existing_model = session.execute(
        select(ShoeModel).where(
            ShoeModel.brand_id == brand.id,
            ShoeModel.slug == model_slug,
            ShoeModel.gender == gender.value,
        )
    ).scalar_one_or_none()

    if existing_model:
        model = existing_model
        # Update model with any new specs
        if extracted.weight_oz and not model.typical_weight_oz:
            model.typical_weight_oz = Decimal(str(extracted.weight_oz))
        if extracted.drop_mm and not model.typical_drop_mm:
            model.typical_drop_mm = Decimal(str(extracted.drop_mm))
        if extracted.stack_height_heel_mm and not model.typical_stack_heel_mm:
            model.typical_stack_heel_mm = Decimal(str(extracted.stack_height_heel_mm))
        if extracted.has_carbon_plate:
            model.has_carbon_plate = True
        if category and not model.category:
            model.category = category.value
        if extracted.cushion_type and not model.cushion_type:
            model.cushion_type = extracted.cushion_type
    else:
        model = ShoeModel(
            brand_id=brand.id,
            name=model_name,
            slug=model_slug,
            gender=gender.value,
            terrain=terrain.value,
            category=category.value if category else None,
            typical_weight_oz=Decimal(str(extracted.weight_oz)) if extracted.weight_oz else None,
            typical_drop_mm=Decimal(str(extracted.drop_mm)) if extracted.drop_mm else None,
            typical_stack_heel_mm=Decimal(str(extracted.stack_height_heel_mm)) if extracted.stack_height_heel_mm else None,
            typical_stack_forefoot_mm=Decimal(str(extracted.stack_height_forefoot_mm)) if extracted.stack_height_forefoot_mm else None,
            has_carbon_plate=extracted.has_carbon_plate,
            cushion_type=extracted.cushion_type,
        )
        session.add(model)
        session.flush()

    # Product name and slug
    product_name = extracted.full_name or f"{extracted.brand} {model_name}"
    product_slug = product_name.lower().replace(' ', '-').replace("'", "")[:300]

    # Find or create product
    existing_product = session.execute(
        select(ShoeProduct).where(
            ShoeProduct.model_id == model.id,
            ShoeProduct.slug == product_slug,
        )
    ).scalar_one_or_none()

    if existing_product:
        product = existing_product
        # Update product with new data
        if extracted.price_usd and not product.msrp_usd:
            product.msrp_usd = Decimal(str(extracted.msrp_usd or extracted.price_usd))
        if extracted.colorway:
            product.colorway = extracted.colorway
        if extracted.style_id:
            product.style_id = extracted.style_id
        if extracted.weight_oz:
            product.weight_oz = Decimal(str(extracted.weight_oz))
        if extracted.drop_mm:
            product.drop_mm = Decimal(str(extracted.drop_mm))
    else:
        product = ShoeProduct(
            model_id=model.id,
            name=product_name,
            slug=product_slug,
            colorway=extracted.colorway,
            style_id=extracted.style_id,
            msrp_usd=Decimal(str(extracted.msrp_usd or extracted.price_usd)) if (extracted.msrp_usd or extracted.price_usd) else None,
            weight_oz=Decimal(str(extracted.weight_oz)) if extracted.weight_oz else None,
            drop_mm=Decimal(str(extracted.drop_mm)) if extracted.drop_mm else None,
            stack_height_heel_mm=Decimal(str(extracted.stack_height_heel_mm)) if extracted.stack_height_heel_mm else None,
            stack_height_forefoot_mm=Decimal(str(extracted.stack_height_forefoot_mm)) if extracted.stack_height_forefoot_mm else None,
            discovered_from='running_warehouse_llm',
            discovered_at=datetime.now(UTC),
            needs_review=False,  # LLM extracted, more reliable
        )
        session.add(product)
        session.flush()

    # Create or update offer
    now = datetime.now(UTC)
    existing_offer = session.execute(
        select(ShoeOffer).where(
            ShoeOffer.product_id == product.id,
            ShoeOffer.merchant == MERCHANT_SLUG,
            ShoeOffer.url == url,
        )
    ).scalar_one_or_none()

    if existing_offer:
        if extracted.price_usd:
            existing_offer.price = Decimal(str(extracted.price_usd))
        existing_offer.last_seen_at = now
        existing_offer.price_updated_at = now
    else:
        offer = ShoeOffer(
            product_id=product.id,
            merchant=MERCHANT_SLUG,
            url=url,
            price=Decimal(str(extracted.price_usd)) if extracted.price_usd else None,
            in_stock=True,
            first_seen_at=now,
            last_seen_at=now,
            price_updated_at=now,
        )
        session.add(offer)

    return True


def main():
    print("=" * 70)
    print("LLM-ASSISTED RUNNING WAREHOUSE SCRAPER")
    print("Using Granite4 for structured extraction")
    print("=" * 70)

    # Parse args
    limit = None
    if '--limit' in sys.argv:
        idx = sys.argv.index('--limit')
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])

    playwright = sync_playwright().start()
    browser = playwright.firefox.launch(headless=True)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        locale='en-US',
    )
    context.add_init_script(STEALTH_SCRIPT)

    try:
        # Discover products
        print("\n" + "=" * 70)
        print("PHASE 1: DISCOVERING PRODUCTS")
        print("=" * 70)

        product_urls = list(discover_products(context))
        print(f"\nTotal products discovered: {len(product_urls)}")

        if limit:
            product_urls = product_urls[:limit]
            print(f"Limiting to {limit} products")

        # Scrape with LLM
        print("\n" + "=" * 70)
        print("PHASE 2: LLM EXTRACTION & SAVING")
        print("=" * 70)

        with sync_session_maker() as session:
            brands = session.execute(select(Brand)).scalars().all()
            brand_by_slug = {b.slug: b for b in brands}

            stats = {
                'processed': 0,
                'saved': 0,
                'skipped_brand': 0,
                'errors': 0,
            }

            for i, url in enumerate(product_urls):
                print(f"\n[{i+1}/{len(product_urls)}] {url}")

                extracted = scrape_with_llm(context, url)

                if not extracted:
                    print("  -> Extraction failed")
                    stats['errors'] += 1
                    continue

                if not extracted.brand:
                    print("  -> No brand detected")
                    stats['errors'] += 1
                    continue

                stats['processed'] += 1

                # Save to DB
                if save_product(session, brand_by_slug, extracted, url):
                    stats['saved'] += 1
                    print(f"  -> {extracted.brand} {extracted.model_name}: ${extracted.price_usd}")
                    if extracted.weight_oz:
                        print(f"     Weight: {extracted.weight_oz}oz, Drop: {extracted.drop_mm}mm")
                else:
                    stats['skipped_brand'] += 1
                    print(f"  -> Unknown brand: {extracted.brand}")

                # Commit every 20
                if stats['saved'] % 20 == 0:
                    session.commit()
                    print(f"  [Committed {stats['saved']} products]")

            session.commit()

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total URLs: {len(product_urls)}")
        print(f"Processed: {stats['processed']}")
        print(f"Saved: {stats['saved']}")
        print(f"Skipped (unknown brand): {stats['skipped_brand']}")
        print(f"Errors: {stats['errors']}")

    finally:
        context.close()
        browser.close()
        playwright.stop()


if __name__ == '__main__':
    main()
