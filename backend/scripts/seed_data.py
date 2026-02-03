"""
Seed the database with initial data for development.
Run with: python scripts/seed_data.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.core.database import async_session_maker, engine, Base
from app.core.security import get_password_hash
from app.models import Category, Brand, Shoe, RunningShoeAttributes, BasketballShoeAttributes, ShoeFitProfile, AdminUser


async def seed_categories():
    """Seed categories."""
    async with async_session_maker() as session:
        # Check if already seeded
        result = await session.execute(select(Category).limit(1))
        if result.first():
            print("Categories already seeded, skipping...")
            return

        categories = [
            Category(name="Running", slug="running", display_order=1, is_active=True),
            Category(name="Basketball", slug="basketball", display_order=2, is_active=True),
        ]
        session.add_all(categories)
        await session.commit()
        print("Categories seeded")


async def seed_brands():
    """Seed brands."""
    async with async_session_maker() as session:
        result = await session.execute(select(Brand).limit(1))
        if result.first():
            print("Brands already seeded, skipping...")
            return

        brands = [
            Brand(name="Nike", slug="nike"),
            Brand(name="Adidas", slug="adidas"),
            Brand(name="Brooks", slug="brooks"),
            Brand(name="Hoka", slug="hoka"),
            Brand(name="New Balance", slug="new-balance"),
            Brand(name="Asics", slug="asics"),
            Brand(name="Saucony", slug="saucony"),
            Brand(name="Jordan", slug="jordan"),
            Brand(name="Under Armour", slug="under-armour"),
            Brand(name="Puma", slug="puma"),
        ]
        session.add_all(brands)
        await session.commit()
        print("Brands seeded")


async def seed_sample_shoes():
    """Seed sample shoes for testing."""
    async with async_session_maker() as session:
        # Get categories and brands
        running_result = await session.execute(select(Category).where(Category.slug == "running"))
        running_cat = running_result.scalar_one_or_none()

        basketball_result = await session.execute(select(Category).where(Category.slug == "basketball"))
        basketball_cat = basketball_result.scalar_one_or_none()

        brooks_result = await session.execute(select(Brand).where(Brand.slug == "brooks"))
        brooks = brooks_result.scalar_one_or_none()

        hoka_result = await session.execute(select(Brand).where(Brand.slug == "hoka"))
        hoka = hoka_result.scalar_one_or_none()

        nike_result = await session.execute(select(Brand).where(Brand.slug == "nike"))
        nike = nike_result.scalar_one_or_none()

        if not all([running_cat, basketball_cat, brooks, hoka, nike]):
            print("Required categories/brands not found, run seed_categories and seed_brands first")
            return

        # Check if shoes exist
        result = await session.execute(select(Shoe).limit(1))
        if result.first():
            print("Shoes already seeded, skipping...")
            return

        # Sample running shoes
        ghost = Shoe(
            brand_id=brooks.id,
            category_id=running_cat.id,
            name="Ghost 15",
            slug="ghost-15",
            model_year=2023,
            msrp_usd=140,
            current_price_min=119.99,
            current_price_max=140,
            width_options=["standard", "wide"],
            primary_image_url="https://example.com/ghost15.jpg",
            is_active=True,
        )
        session.add(ghost)
        await session.flush()

        ghost_attrs = RunningShoeAttributes(
            shoe_id=ghost.id,
            terrain="road",
            subcategory="neutral",
            weight_oz=10.1,
            stack_height_heel_mm=35,
            stack_height_forefoot_mm=23,
            drop_mm=12,
            cushion_type="foam",
            cushion_level="moderate",
            best_for_distances=["5k", "10k", "half_marathon"],
            best_for_pace="easy",
        )
        session.add(ghost_attrs)

        ghost_fit = ShoeFitProfile(
            shoe_id=ghost.id,
            size_runs="true",
            width_runs="true",
            toe_box_room="roomy",
            arch_support="neutral",
            break_in_period="none",
            durability_rating="good",
            expected_miles_min=400,
            expected_miles_max=500,
            works_well_for=["neutral_runners", "daily_training"],
            overall_sentiment=0.87,
            review_count=342,
            needs_review=False,
        )
        session.add(ghost_fit)

        # Hoka Clifton
        clifton = Shoe(
            brand_id=hoka.id,
            category_id=running_cat.id,
            name="Clifton 9",
            slug="clifton-9",
            model_year=2023,
            msrp_usd=145,
            current_price_min=129.99,
            width_options=["standard", "wide"],
            is_active=True,
        )
        session.add(clifton)
        await session.flush()

        clifton_attrs = RunningShoeAttributes(
            shoe_id=clifton.id,
            terrain="road",
            subcategory="neutral",
            weight_oz=9.1,
            stack_height_heel_mm=37,
            stack_height_forefoot_mm=32,
            drop_mm=5,
            cushion_type="foam",
            cushion_level="max",
            has_rocker=True,
            best_for_distances=["half_marathon", "marathon"],
            best_for_pace="easy",
        )
        session.add(clifton_attrs)

        clifton_fit = ShoeFitProfile(
            shoe_id=clifton.id,
            size_runs="true",
            width_runs="true",
            toe_box_room="roomy",
            arch_support="neutral",
            break_in_period="short",
            durability_rating="average",
            expected_miles_min=300,
            expected_miles_max=400,
            works_well_for=["high_arches", "long_distance"],
            overall_sentiment=0.85,
            review_count=450,
            needs_review=False,
        )
        session.add(clifton_fit)

        # Nike basketball shoe
        lebron = Shoe(
            brand_id=nike.id,
            category_id=basketball_cat.id,
            name="LeBron 21",
            slug="lebron-21",
            model_year=2024,
            msrp_usd=200,
            current_price_min=180,
            width_options=["standard"],
            is_active=True,
        )
        session.add(lebron)
        await session.flush()

        lebron_attrs = BasketballShoeAttributes(
            shoe_id=lebron.id,
            cut="mid",
            court_type=["indoor", "outdoor"],
            weight_oz=16.5,
            cushion_type="air",
            cushion_level="impact_protection",
            ankle_support_level="moderate",
            lockdown_level="tight",
            best_for_position=["wing", "big"],
            best_for_playstyle=["power", "all_around"],
            outdoor_durability="moderate",
        )
        session.add(lebron_attrs)

        lebron_fit = ShoeFitProfile(
            shoe_id=lebron.id,
            size_runs="true",
            width_runs="true",
            toe_box_room="snug",
            arch_support="neutral",
            break_in_period="short",
            durability_rating="good",
            works_well_for=["wide_feet", "impact_protection"],
            overall_sentiment=0.82,
            review_count=230,
            needs_review=False,
        )
        session.add(lebron_fit)

        await session.commit()
        print("Sample shoes seeded")


async def seed_admin_user():
    """Seed default admin user."""
    async with async_session_maker() as session:
        result = await session.execute(select(AdminUser).limit(1))
        if result.first():
            print("Admin user already exists, skipping...")
            return

        admin = AdminUser(
            email="admin@shoematcher.com",
            password_hash=get_password_hash("admin123"),
            name="Admin User",
            role="admin",
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        print("Admin user seeded (email: admin@shoematcher.com, password: admin123)")


async def main():
    print("Seeding database...")
    await seed_categories()
    await seed_brands()
    await seed_sample_shoes()
    await seed_admin_user()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
