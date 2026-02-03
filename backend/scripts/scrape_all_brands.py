#!/usr/bin/env python
"""
Scrape ALL shoes dynamically from brand websites and add to database.

This script uses dynamic product discovery to find every shoe on each brand's
website, rather than relying on hardcoded shoe lists.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.core.database import async_session_maker
from app.models import Brand, Category, Shoe, RunningShoeAttributes, ShoeFitProfile

# Import scrapers
from app.scrapers.brand_scrapers import (
    NikeScraper,
    HokaScraper,
    BrooksScraper,
    AsicsScraper,
    SauconyScraper,
    AdidasScraper,
    NewBalanceScraper,
    OnRunningScraper,
    AltraScraper,
    MizunoScraper,
)

SCRAPER_MAP = {
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


async def scrape_brand_dynamic(brand_slug: str, session, running_cat_id):
    """Dynamically discover and scrape ALL shoes for a brand."""
    scraper_class = SCRAPER_MAP.get(brand_slug)
    if not scraper_class:
        print(f"  No scraper for {brand_slug}")
        return 0

    # Get brand from DB
    result = await session.execute(select(Brand).where(Brand.slug == brand_slug))
    brand = result.scalar_one_or_none()
    if not brand:
        print(f"  Brand not found in DB: {brand_slug}")
        return 0

    scraper = scraper_class()
    added = 0
    errors = 0

    # DYNAMIC DISCOVERY - Find ALL products on the brand's website
    print(f"  Discovering all products from {brand.name}'s website...")
    try:
        product_urls = await scraper.discover_all_products()
        print(f"  Found {len(product_urls)} product URLs!")
    except NotImplementedError:
        print(f"  ERROR: Scraper for {brand.name} doesn't support dynamic discovery")
        return 0
    except Exception as e:
        print(f"  ERROR discovering products: {e}")
        return 0

    if not product_urls:
        print(f"  No products found for {brand.name}")
        return 0

    # Scrape each discovered product
    for i, url in enumerate(product_urls):
        try:
            print(f"  [{i+1}/{len(product_urls)}] Scraping: {url}...", end=" ", flush=True)

            specs = await scraper.scrape_product_specs_async(url)
            if not specs or not specs.name:
                print("No specs found")
                errors += 1
                continue

            # Create slug
            slug = specs.name.lower().replace(' ', '-').replace("'", "")

            # Check if exists
            existing = await session.execute(
                select(Shoe).where(Shoe.brand_id == brand.id, Shoe.slug == slug)
            )
            if existing.scalar_one_or_none():
                print("Already exists")
                continue

            # Create shoe
            shoe = Shoe(
                brand_id=brand.id,
                category_id=running_cat_id,
                name=specs.name,
                slug=slug,
                msrp_usd=specs.msrp,
                primary_image_url=specs.primary_image_url,
                image_urls=specs.image_urls,
                is_active=True,
                last_scraped_at=datetime.utcnow(),
            )
            session.add(shoe)
            await session.flush()

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
                has_carbon_plate=specs.has_carbon_plate or False,
                has_rocker=specs.has_rocker or False,
            )
            session.add(attrs)

            # Create fit profile placeholder
            fit = ShoeFitProfile(
                shoe_id=shoe.id,
                size_runs='true_to_size',
                needs_review=True,
            )
            session.add(fit)

            print(f"OK - {specs.name}, ${specs.msrp or '?'}")
            added += 1

        except Exception as e:
            print(f"Error: {e}")
            errors += 1
            continue

    return added


async def main():
    print("=" * 70)
    print("DYNAMIC SHOE DISCOVERY - SCRAPING ALL SHOES FROM BRAND WEBSITES")
    print("=" * 70)

    async with async_session_maker() as session:
        # Get running category
        result = await session.execute(select(Category).where(Category.slug == 'running'))
        running_cat = result.scalar_one_or_none()
        if not running_cat:
            print("Running category not found!")
            return

        total_added = 0

        for brand_slug in SCRAPER_MAP.keys():
            print(f"\n{'='*60}")
            print(f"{brand_slug.upper()}")
            print("-" * 60)
            added = await scrape_brand_dynamic(brand_slug, session, running_cat.id)
            total_added += added
            print(f"  Added {added} shoes for {brand_slug}")

        await session.commit()

        print("\n" + "=" * 70)
        print(f"TOTAL SHOES ADDED: {total_added}")
        print("=" * 70)


if __name__ == '__main__':
    asyncio.run(main())
