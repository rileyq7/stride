"""
Celery tasks for scraping and processing shoe reviews.

Note: In development without Celery, these can be called directly as async functions.
In production, they would be Celery tasks.
"""

import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import async_session_maker
from app.models import Shoe, ShoeReview, ShoeFitProfile, Category, RunningShoeAttributes, BasketballShoeAttributes
from app.scrapers.base import get_scraper_for_source, get_default_sources, RawReview
from app.scrapers.ai_parser import ReviewFitExtractor
from app.scrapers.brand_scrapers import get_brand_scraper

logger = logging.getLogger(__name__)


async def store_reviews(shoe_id: str, reviews: List[RawReview]) -> int:
    """Store raw reviews in the database."""
    stored_count = 0

    async with async_session_maker() as session:
        for review in reviews:
            # Check if review already exists
            existing = await session.execute(
                select(ShoeReview).where(
                    ShoeReview.shoe_id == shoe_id,
                    ShoeReview.source == review.source,
                    ShoeReview.source_review_id == review.source_review_id,
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Create new review
            db_review = ShoeReview(
                shoe_id=shoe_id,
                source=review.source,
                source_url=review.source_url,
                source_review_id=review.source_review_id,
                reviewer_name=review.reviewer_name,
                rating=review.rating,
                title=review.title,
                body=review.body,
                review_date=review.review_date,
                reviewer_foot_width=review.reviewer_foot_width,
                reviewer_arch_type=review.reviewer_arch_type,
                reviewer_size_purchased=review.reviewer_size_purchased,
                reviewer_typical_size=review.reviewer_typical_size,
            )
            session.add(db_review)
            stored_count += 1

        await session.commit()

    return stored_count


async def update_fit_profile(shoe_id: str, profile_data: dict, needs_review: bool = True) -> None:
    """Update or create fit profile for a shoe."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(ShoeFitProfile).where(ShoeFitProfile.shoe_id == shoe_id)
        )
        fit_profile = result.scalar_one_or_none()

        if fit_profile:
            # Update existing profile
            for key, value in profile_data.items():
                if hasattr(fit_profile, key):
                    setattr(fit_profile, key, value)
            fit_profile.needs_review = needs_review
            fit_profile.last_updated = datetime.utcnow()
        else:
            # Create new profile
            fit_profile = ShoeFitProfile(
                shoe_id=shoe_id,
                needs_review=needs_review,
                **{k: v for k, v in profile_data.items() if hasattr(ShoeFitProfile, k)}
            )
            session.add(fit_profile)

        # Update shoe's last_scraped_at
        shoe_result = await session.execute(select(Shoe).where(Shoe.id == shoe_id))
        shoe = shoe_result.scalar_one_or_none()
        if shoe:
            shoe.last_scraped_at = datetime.utcnow()

        await session.commit()


async def get_reviews_for_shoe(shoe_id: str) -> List[RawReview]:
    """Get all reviews for a shoe from the database."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(ShoeReview).where(ShoeReview.shoe_id == shoe_id)
        )
        db_reviews = result.scalars().all()

        return [
            RawReview(
                source=r.source,
                source_review_id=r.source_review_id or '',
                source_url=r.source_url or '',
                reviewer_name=r.reviewer_name,
                rating=float(r.rating) if r.rating else None,
                title=r.title,
                body=r.body or '',
                review_date=str(r.review_date) if r.review_date else None,
                reviewer_foot_width=r.reviewer_foot_width,
                reviewer_arch_type=r.reviewer_arch_type,
                reviewer_size_purchased=r.reviewer_size_purchased,
                reviewer_typical_size=r.reviewer_typical_size,
            )
            for r in db_reviews
        ]


async def scrape_shoe_reviews(
    shoe_id: str,
    sources: Optional[List[str]] = None
) -> dict:
    """
    Scrape reviews for a single shoe from specified sources.

    In production with Celery:
    @app.task(bind=True, max_retries=3)
    def scrape_shoe_reviews(self, shoe_id: str, sources: List[str] = None):
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(Shoe)
            .where(Shoe.id == shoe_id)
            .options(
                selectinload(Shoe.brand),
                selectinload(Shoe.category),
            )
        )
        shoe = result.scalar_one_or_none()

        if not shoe:
            logger.error(f"Shoe not found: {shoe_id}")
            return {'error': 'Shoe not found'}

        category_slug = shoe.category.slug if shoe.category else 'running'
        sources = sources or get_default_sources(category_slug)

        all_reviews = []

        for source in sources:
            try:
                scraper = get_scraper_for_source(source, category_slug)
                if not scraper:
                    continue

                reviews = scraper.scrape_shoe(shoe)
                all_reviews.extend(reviews)

                # Store reviews
                stored = await store_reviews(str(shoe_id), reviews)
                logger.info(f"Stored {stored} reviews from {source} for {shoe.name}")

            except Exception as e:
                logger.error(f"Scrape failed for {source}: {e}")
                continue

        # Trigger AI extraction if we have reviews
        if all_reviews:
            await extract_fit_profile(str(shoe_id))

        return {
            'shoe_id': str(shoe_id),
            'reviews_scraped': len(all_reviews),
            'sources': sources,
        }


async def extract_fit_profile(shoe_id: str) -> dict:
    """
    Extract fit profile from stored reviews using AI.

    In production with Celery:
    @app.task
    def extract_fit_profile(shoe_id: str):
    """
    reviews = await get_reviews_for_shoe(shoe_id)

    if not reviews:
        logger.warning(f"No reviews found for shoe {shoe_id}")
        return {'shoe_id': shoe_id, 'profile_extracted': False}

    extractor = ReviewFitExtractor()
    fit_profile = extractor.extract_fit_profile(reviews)

    if fit_profile:
        await update_fit_profile(shoe_id, fit_profile, needs_review=True)
        return {'shoe_id': shoe_id, 'profile_extracted': True}

    return {'shoe_id': shoe_id, 'profile_extracted': False}


async def scrape_category(category_id: str) -> dict:
    """
    Scrape all shoes in a category.

    In production with Celery:
    @app.task
    def scrape_category(category_id: str):
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(Shoe)
            .where(Shoe.category_id == category_id, Shoe.is_active == True)
        )
        shoes = result.scalars().all()

        results = []
        for shoe in shoes:
            try:
                result = await scrape_shoe_reviews(str(shoe.id))
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to scrape {shoe.name}: {e}")
                results.append({'shoe_id': str(shoe.id), 'error': str(e)})

        return {
            'category_id': category_id,
            'shoes_processed': len(results),
            'results': results,
        }


async def scrape_shoe_specs(shoe_id: str) -> dict:
    """
    Scrape official product specs from brand website.

    This updates the Shoe and RunningShoeAttributes/BasketballShoeAttributes
    with official technical specifications.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(Shoe)
            .where(Shoe.id == shoe_id)
            .options(
                selectinload(Shoe.brand),
                selectinload(Shoe.category),
                selectinload(Shoe.running_attributes),
                selectinload(Shoe.basketball_attributes),
            )
        )
        shoe = result.scalar_one_or_none()

        if not shoe:
            logger.error(f"Shoe not found: {shoe_id}")
            return {'error': 'Shoe not found'}

        brand_name = shoe.brand.name if shoe.brand else None
        if not brand_name:
            return {'error': 'No brand associated with shoe'}

        # Get brand scraper
        scraper = get_brand_scraper(brand_name)
        if not scraper:
            logger.warning(f"No scraper available for brand: {brand_name}")
            return {'error': f'No scraper for brand: {brand_name}'}

        try:
            # Scrape specs
            specs = scraper.scrape_shoe(shoe.name)
            if not specs:
                return {'shoe_id': str(shoe_id), 'specs_found': False}

            # Update shoe base data
            shoe_data = specs.to_shoe_data()
            for key, value in shoe_data.items():
                if value is not None and hasattr(shoe, key):
                    setattr(shoe, key, value)

            # Update category-specific attributes
            category_slug = shoe.category.slug if shoe.category else 'running'

            if category_slug == 'running':
                running_attrs = specs.to_running_attributes()
                if shoe.running_attributes:
                    for key, value in running_attrs.items():
                        if value is not None and hasattr(shoe.running_attributes, key):
                            setattr(shoe.running_attributes, key, value)
                else:
                    # Create new running attributes
                    new_attrs = RunningShoeAttributes(
                        shoe_id=shoe.id,
                        terrain=running_attrs.get('terrain', 'road'),
                        **{k: v for k, v in running_attrs.items() if v is not None and k != 'terrain'}
                    )
                    session.add(new_attrs)

            elif category_slug == 'basketball':
                bball_attrs = specs.to_basketball_attributes()
                if shoe.basketball_attributes:
                    for key, value in bball_attrs.items():
                        if value is not None and hasattr(shoe.basketball_attributes, key):
                            setattr(shoe.basketball_attributes, key, value)
                else:
                    # Create new basketball attributes
                    new_attrs = BasketballShoeAttributes(
                        shoe_id=shoe.id,
                        cut=bball_attrs.get('cut', 'low'),
                        **{k: v for k, v in bball_attrs.items() if v is not None and k != 'cut'}
                    )
                    session.add(new_attrs)

            shoe.last_scraped_at = datetime.utcnow()
            await session.commit()

            logger.info(f"Updated specs for {shoe.name} from {brand_name}")

            return {
                'shoe_id': str(shoe_id),
                'specs_found': True,
                'brand': brand_name,
                'weight_oz': float(specs.weight_oz) if specs.weight_oz else None,
                'drop_mm': float(specs.drop_mm) if specs.drop_mm else None,
                'msrp': float(specs.msrp) if specs.msrp else None,
            }

        except Exception as e:
            logger.error(f"Failed to scrape specs for {shoe.name}: {e}")
            return {'shoe_id': str(shoe_id), 'error': str(e)}


async def scrape_all_brand_specs(brand_id: str) -> dict:
    """
    Scrape specs for all active shoes from a brand.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(Shoe)
            .where(Shoe.brand_id == brand_id, Shoe.is_active == True)
        )
        shoes = result.scalars().all()

        results = []
        for shoe in shoes:
            try:
                result = await scrape_shoe_specs(str(shoe.id))
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to scrape specs for {shoe.name}: {e}")
                results.append({'shoe_id': str(shoe.id), 'error': str(e)})

        return {
            'brand_id': brand_id,
            'shoes_processed': len(results),
            'results': results,
        }


async def full_shoe_scrape(shoe_id: str, sources: Optional[List[str]] = None) -> dict:
    """
    Perform a full scrape of a shoe: specs + reviews + fit extraction.
    """
    results = {
        'shoe_id': shoe_id,
        'specs': None,
        'reviews': None,
        'fit_profile': None,
    }

    # 1. Scrape official specs from brand site
    try:
        results['specs'] = await scrape_shoe_specs(shoe_id)
    except Exception as e:
        logger.error(f"Specs scrape failed: {e}")
        results['specs'] = {'error': str(e)}

    # 2. Scrape reviews from all sources
    try:
        results['reviews'] = await scrape_shoe_reviews(shoe_id, sources)
    except Exception as e:
        logger.error(f"Reviews scrape failed: {e}")
        results['reviews'] = {'error': str(e)}

    # 3. Extract fit profile (already called by scrape_shoe_reviews if reviews found)
    results['fit_profile'] = {'extracted': results['reviews'].get('reviews_scraped', 0) > 0}

    return results
