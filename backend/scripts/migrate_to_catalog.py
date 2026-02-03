#!/usr/bin/env python
"""
Migrate existing shoe data from the legacy Shoe table to the new 3-layer catalog model.

This script:
1. Creates ShoeModel entries for unique brand+model combinations
2. Creates ShoeProduct entries linked to models
3. Preserves relationships with existing data

Usage:
    python migrate_to_catalog.py          # Migrate all shoes
    python migrate_to_catalog.py --dry-run  # Show what would be migrated
"""

import sys
import re
from pathlib import Path
from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional, Tuple

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from app.core.database import sync_session_maker
from app.models import (
    Brand, Shoe, RunningShoeAttributes,
    ShoeModel, ShoeProduct, Gender, Terrain, SupportType, ShoeCategory
)


def normalize_model_name(name: str, brand_name: str) -> str:
    """
    Normalize a shoe name to extract the model name.
    Example: "Nike Pegasus 41 Men's Road Running Shoes" -> "Pegasus 41"
    """
    # Remove brand prefix
    name_lower = name.lower()
    brand_lower = brand_name.lower()

    if name_lower.startswith(brand_lower):
        name = name[len(brand_lower):].strip()

    # Remove [URL] prefix if present
    if name.startswith('[URL]'):
        name = name[5:].strip()

    # Remove common suffixes
    patterns_to_remove = [
        r"men'?s?\s*",
        r"women'?s?\s*",
        r"unisex\s*",
        r"road\s*running\s*shoe[s]?\s*",
        r"trail\s*running\s*shoe[s]?\s*",
        r"running\s*shoe[s]?\s*",
        r"shoe[s]?\s*$",
    ]
    for pattern in patterns_to_remove:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    # Remove colorway (after last hyphen or parentheses)
    name = re.sub(r'\s*[-/]\s*[\w\s/]+$', '', name)
    name = re.sub(r'\s*\([^)]+\)\s*$', '', name)

    # Clean up URL-style names (replace hyphens with spaces)
    if '-' in name and ' ' not in name:
        name = name.replace('-', ' ')

    # Capitalize properly
    name = ' '.join(word.capitalize() for word in name.split())

    return name.strip()


def extract_gender(name: str, url_slug: str) -> Gender:
    """Extract gender from name or URL."""
    combined = (name + ' ' + url_slug).lower()

    if 'women' in combined or 'womens' in combined or "women's" in combined:
        return Gender.WOMENS
    elif 'men' in combined or 'mens' in combined or "men's" in combined:
        return Gender.MENS
    elif 'unisex' in combined or 'kid' in combined:
        return Gender.UNISEX

    return Gender.UNISEX  # Default


def extract_terrain(attrs: Optional[RunningShoeAttributes], name: str) -> Terrain:
    """Extract terrain from attributes or name."""
    if attrs and attrs.terrain:
        terrain_map = {
            'road': Terrain.ROAD,
            'trail': Terrain.TRAIL,
            'track': Terrain.TRACK,
        }
        return terrain_map.get(attrs.terrain.lower(), Terrain.ROAD)

    name_lower = name.lower()
    if 'trail' in name_lower:
        return Terrain.TRAIL
    elif 'track' in name_lower or 'spike' in name_lower:
        return Terrain.TRACK

    return Terrain.ROAD


def extract_category(attrs: Optional[RunningShoeAttributes], name: str) -> Optional[ShoeCategory]:
    """Extract shoe category."""
    name_lower = name.lower()

    if any(x in name_lower for x in ['vaporfly', 'alphafly', 'metaspeed', 'endorphin pro', 'adizero pro']):
        return ShoeCategory.RACING
    elif any(x in name_lower for x in ['tempo', 'speed']):
        return ShoeCategory.TEMPO
    elif 'trail' in name_lower:
        return ShoeCategory.TRAIL
    elif any(x in name_lower for x in ['spike', 'xc']):
        return ShoeCategory.TRACK_SPIKE

    if attrs and attrs.subcategory:
        cat_map = {
            'racing': ShoeCategory.RACING,
            'neutral': ShoeCategory.DAILY_TRAINER,
            'stability': ShoeCategory.DAILY_TRAINER,
            'daily_trainer': ShoeCategory.DAILY_TRAINER,
        }
        return cat_map.get(attrs.subcategory.lower())

    return ShoeCategory.DAILY_TRAINER


def migrate_shoes(dry_run: bool = False):
    """Migrate legacy Shoe records to the new catalog model."""
    print("=" * 70)
    print("MIGRATING TO 3-LAYER CATALOG MODEL")
    print("=" * 70)
    print(f"Dry run: {dry_run}")

    with sync_session_maker() as session:
        # Get all shoes with their attributes
        shoes = session.execute(
            select(Shoe)
            .options()  # Load relationships
        ).scalars().all()

        print(f"\nFound {len(shoes)} shoes to migrate")

        # Track statistics
        stats = {
            'models_created': 0,
            'products_created': 0,
            'skipped': 0,
        }

        # Cache for models we've created
        model_cache = {}

        for shoe in shoes:
            # Get brand
            brand = session.execute(
                select(Brand).where(Brand.id == shoe.brand_id)
            ).scalar_one_or_none()

            if not brand:
                stats['skipped'] += 1
                continue

            # Get running attributes
            attrs = session.execute(
                select(RunningShoeAttributes).where(RunningShoeAttributes.shoe_id == shoe.id)
            ).scalar_one_or_none()

            # Normalize model name
            model_name = normalize_model_name(shoe.name, brand.name)
            if not model_name or len(model_name) < 2:
                model_name = shoe.name  # Fallback

            # Extract characteristics
            gender = extract_gender(shoe.name, shoe.slug)
            terrain = extract_terrain(attrs, shoe.name)
            category = extract_category(attrs, shoe.name)

            # Create model key
            model_slug = model_name.lower().replace(' ', '-').replace("'", "")[:200]
            model_key = (brand.id, model_slug, gender)

            # Check if model exists in cache
            if model_key not in model_cache:
                # Check if model exists in DB
                existing_model = session.execute(
                    select(ShoeModel).where(
                        ShoeModel.brand_id == brand.id,
                        ShoeModel.slug == model_slug,
                        ShoeModel.gender == gender,
                    )
                ).scalar_one_or_none()

                if existing_model:
                    model_cache[model_key] = existing_model
                else:
                    # Create new model
                    if not dry_run:
                        new_model = ShoeModel(
                            brand_id=brand.id,
                            name=model_name,
                            slug=model_slug,
                            gender=gender,
                            terrain=terrain,
                            category=category,
                            typical_weight_oz=attrs.weight_oz if attrs else None,
                            typical_drop_mm=attrs.drop_mm if attrs else None,
                            typical_stack_heel_mm=attrs.stack_height_heel_mm if attrs else None,
                            typical_stack_forefoot_mm=attrs.stack_height_forefoot_mm if attrs else None,
                            has_carbon_plate=attrs.has_carbon_plate if attrs else False,
                            has_rocker=attrs.has_rocker if attrs else False,
                            cushion_type=attrs.cushion_type if attrs else None,
                            cushion_level=attrs.cushion_level if attrs else None,
                        )
                        session.add(new_model)
                        session.flush()
                        model_cache[model_key] = new_model
                    stats['models_created'] += 1
                    print(f"  + Model: {brand.name} {model_name} ({gender.value})")

            # Get model (if not dry run)
            model = model_cache.get(model_key)

            # Create product
            product_slug = shoe.slug[:300]

            if not dry_run and model:
                # Check if product already exists
                existing_product = session.execute(
                    select(ShoeProduct).where(
                        ShoeProduct.model_id == model.id,
                        ShoeProduct.slug == product_slug,
                    )
                ).scalar_one_or_none()

                if not existing_product:
                    new_product = ShoeProduct(
                        model_id=model.id,
                        name=shoe.name,
                        slug=product_slug,
                        msrp_usd=shoe.msrp_usd,
                        primary_image_url=shoe.primary_image_url,
                        image_urls=shoe.image_urls,
                        weight_oz=attrs.weight_oz if attrs else None,
                        drop_mm=attrs.drop_mm if attrs else None,
                        stack_height_heel_mm=attrs.stack_height_heel_mm if attrs else None,
                        stack_height_forefoot_mm=attrs.stack_height_forefoot_mm if attrs else None,
                        width_options=shoe.width_options,
                        is_discontinued=shoe.is_discontinued,
                        discovered_from='legacy_migration',
                        discovered_at=datetime.now(UTC),
                        needs_review=shoe.needs_review,
                    )
                    session.add(new_product)
                    stats['products_created'] += 1

            # Commit periodically
            if not dry_run and stats['products_created'] % 100 == 0:
                session.commit()
                print(f"  Progress: {stats}")

        if not dry_run:
            session.commit()

        print("\n" + "=" * 70)
        print("MIGRATION COMPLETE")
        print("=" * 70)
        print(f"  Models created: {stats['models_created']}")
        print(f"  Products created: {stats['products_created']}")
        print(f"  Skipped: {stats['skipped']}")


def print_catalog_report():
    """Print a report of the new catalog."""
    print("\n" + "=" * 70)
    print("CATALOG REPORT")
    print("=" * 70)

    with sync_session_maker() as session:
        # Count by brand
        result = session.execute(text('''
            SELECT b.name,
                   COUNT(DISTINCT sm.id) as models,
                   COUNT(DISTINCT sp.id) as products
            FROM shoe_models sm
            JOIN brands b ON sm.brand_id = b.id
            LEFT JOIN shoe_products sp ON sp.model_id = sm.id
            GROUP BY b.name
            ORDER BY models DESC
        '''))

        print("\nModels/Products by Brand:")
        print("-" * 50)
        total_models = 0
        total_products = 0
        for row in result:
            print(f"  {row[0]:15} {row[1]:4} models, {row[2]:4} products")
            total_models += row[1]
            total_products += row[2]
        print("-" * 50)
        print(f"  {'TOTAL':15} {total_models:4} models, {total_products:4} products")

        # By gender
        result = session.execute(text('''
            SELECT gender, COUNT(*) FROM shoe_models GROUP BY gender
        '''))
        print("\nModels by Gender:")
        for row in result:
            print(f"  {row[0]:15} {row[1]:4}")

        # By terrain
        result = session.execute(text('''
            SELECT terrain, COUNT(*) FROM shoe_models GROUP BY terrain
        '''))
        print("\nModels by Terrain:")
        for row in result:
            print(f"  {row[0]:15} {row[1]:4}")


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    report_only = '--report' in args

    if report_only:
        print_catalog_report()
        return

    migrate_shoes(dry_run=dry_run)
    print_catalog_report()


if __name__ == '__main__':
    main()
