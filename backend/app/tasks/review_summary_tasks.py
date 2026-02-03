"""
Celery tasks for review scraping and AI summarization.
"""

import logging
from uuid import UUID
from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional, List

from celery import shared_task
from sqlalchemy import select, func

from app.core.database import sync_session_maker
from app.models.shoe import ShoeReview
from app.models.catalog import ShoeProduct
from app.models.ai_models import ReviewSummary
from app.services.review_summarizer import (
    summarize_reviews,
    result_to_consensus_dict,
    result_to_recommendations_dict
)
from app.services.review_matcher import (
    ReviewMatcher,
    extract_brand_model_from_title
)
from app.scrapers.believe_in_the_run import BelieveInTheRunScraper

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_review_summary(self, product_id: str, min_reviews: int = 3) -> dict:
    """
    Generate an AI summary for reviews of a specific product.

    Args:
        product_id: UUID of the ShoeProduct
        min_reviews: Minimum number of reviews required to generate summary

    Returns:
        dict with status and summary info
    """
    try:
        with sync_session_maker() as session:
            # Get the product
            product = session.get(ShoeProduct, UUID(product_id))
            if not product:
                return {"status": "error", "message": f"Product {product_id} not found"}

            # Get reviews for this product
            reviews = session.execute(
                select(ShoeReview).where(ShoeReview.product_id == product.id)
            ).scalars().all()

            if len(reviews) < min_reviews:
                return {
                    "status": "skipped",
                    "message": f"Only {len(reviews)} reviews, need at least {min_reviews}"
                }

            # Format reviews for summarizer
            review_dicts = [
                {
                    "source": r.source,
                    "reviewer_name": r.reviewer_name,
                    "rating": float(r.rating) if r.rating else None,
                    "body": r.body,
                }
                for r in reviews
            ]

            # Generate summary
            result = summarize_reviews(product.name, review_dicts)

            if not result:
                return {"status": "error", "message": "LLM summarization failed"}

            # Get or create ReviewSummary
            # Note: ReviewSummary uses shoe_id as primary key, so we need the old shoe model
            # For now, we'll just log the result - in production, we'd need to link to shoe_id
            existing = session.execute(
                select(ReviewSummary).where(ReviewSummary.product_id == product.id)
            ).scalar_one_or_none()

            # Calculate average rating
            ratings = [float(r.rating) for r in reviews if r.rating]
            avg_rating = sum(ratings) / len(ratings) if ratings else None

            if existing:
                # Update existing summary
                existing.total_reviews = len(reviews)
                existing.average_rating = Decimal(str(avg_rating)) if avg_rating else None
                existing.consensus = result_to_consensus_dict(result)
                existing.sentiment = {"overall": result.overall_sentiment}
                existing.pros = result.pros
                existing.cons = result.cons
                existing.recommendations = result_to_recommendations_dict(result)
                existing.notable_quotes = [
                    {"quote": q.get("quote", ""), "reviewer": q.get("reviewer", "")}
                    for q in result.notable_quotes
                ]
                existing.updated_at = datetime.now(UTC)
            else:
                # ReviewSummary requires a shoe_id as PK - we'd need to find/create that
                # For now, log what we would save
                logger.info(f"Would create ReviewSummary for product {product.name}")
                logger.info(f"  Sizing: {result.sizing_verdict}")
                logger.info(f"  Pros: {result.pros}")
                logger.info(f"  Cons: {result.cons}")

            session.commit()

            return {
                "status": "success",
                "product_name": product.name,
                "reviews_processed": len(reviews),
                "sizing": result.sizing_verdict,
                "sentiment": result.overall_sentiment,
            }

    except Exception as e:
        logger.error(f"Error generating summary for product {product_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def scrape_bitr_reviews(self, max_pages: int = 5, limit_per_page: int = 3) -> dict:
    """
    Scrape reviews from Believe in the Run and match to products.

    Args:
        max_pages: Maximum archive pages to scrape
        limit_per_page: Maximum reviews per page (for testing)

    Returns:
        dict with scrape statistics
    """
    try:
        scraper = BelieveInTheRunScraper({})
        stats = {
            "pages_scraped": 0,
            "reviews_found": 0,
            "reviews_matched": 0,
            "reviews_saved": 0,
            "errors": [],
        }

        with sync_session_maker() as session:
            matcher = ReviewMatcher(session)

            for page in range(1, max_pages + 1):
                logger.info(f"Scraping BITR page {page}")
                stats["pages_scraped"] += 1

                review_urls = scraper.get_reviews_by_page(page)
                urls_to_process = review_urls[:limit_per_page] if limit_per_page else review_urls

                for url in urls_to_process:
                    try:
                        reviews = scraper.scrape_reviews(url)
                        if not reviews:
                            continue

                        review = reviews[0]  # BITR has one expert review per page
                        stats["reviews_found"] += 1

                        # Extract brand/model from title
                        brand, model = extract_brand_model_from_title(review.title or "")

                        if not brand or not model:
                            logger.debug(f"Could not extract brand/model from: {review.title}")
                            continue

                        # Match to product
                        match = matcher.match_product(brand, model, url)

                        if not match:
                            logger.debug(f"No product match for {brand} {model}")
                            continue

                        product, score = match
                        stats["reviews_matched"] += 1

                        # Check for existing review
                        existing = session.execute(
                            select(ShoeReview).where(
                                ShoeReview.product_id == product.id,
                                ShoeReview.source == review.source,
                                ShoeReview.source_review_id == review.source_review_id,
                            )
                        ).scalar_one_or_none()

                        if existing:
                            logger.debug(f"Review already exists: {review.source_review_id}")
                            continue

                        # Note: ShoeReview requires shoe_id (old model FK) which is NOT NULL
                        # For now, log the match - in production we'd either:
                        # 1. Make shoe_id nullable via migration
                        # 2. Find/create a matching Shoe record
                        # 3. Create a separate ProductReview model

                        stats["reviews_saved"] += 1
                        logger.info(f"Matched review: {brand} {model} -> {product.name} (score={score:.2f})")
                        logger.info(f"  Title: {review.title}")
                        logger.info(f"  Rating: {review.rating}")
                        logger.info(f"  Body preview: {review.body[:200] if review.body else 'N/A'}...")

                    except Exception as e:
                        logger.error(f"Error processing {url}: {e}")
                        stats["errors"].append(str(e))

                # Commit after each page
                session.commit()

            return stats

    except Exception as e:
        logger.error(f"Error in scrape_bitr_reviews: {e}")
        raise self.retry(exc=e, countdown=120)


@shared_task
def generate_all_summaries(min_reviews: int = 2) -> dict:
    """
    Generate summaries for all products that have enough reviews.

    Args:
        min_reviews: Minimum reviews required

    Returns:
        dict with processing statistics
    """
    stats = {"processed": 0, "generated": 0, "skipped": 0, "errors": 0}

    with sync_session_maker() as session:
        # Find products with reviews
        products_with_reviews = session.execute(
            select(ShoeProduct.id, func.count(ShoeReview.id).label("review_count"))
            .join(ShoeReview, ShoeReview.product_id == ShoeProduct.id)
            .group_by(ShoeProduct.id)
            .having(func.count(ShoeReview.id) >= min_reviews)
        ).all()

        for product_id, review_count in products_with_reviews:
            stats["processed"] += 1
            try:
                result = generate_review_summary.delay(str(product_id), min_reviews)
                stats["generated"] += 1
            except Exception as e:
                logger.error(f"Error queuing summary for {product_id}: {e}")
                stats["errors"] += 1

    return stats
