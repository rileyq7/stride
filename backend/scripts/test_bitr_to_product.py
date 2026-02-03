#!/usr/bin/env python
"""
Test the full BITR -> Product matching flow.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import sync_session_maker
from app.scrapers.believe_in_the_run import BelieveInTheRunScraper
from app.services.review_matcher import ReviewMatcher, extract_brand_model_from_title


def main():
    print("=" * 70)
    print("BITR -> PRODUCT MATCHING TEST")
    print("=" * 70)

    scraper = BelieveInTheRunScraper({})

    # Get first page of reviews
    print("\n--- Getting BITR reviews from page 1 ---")
    review_urls = scraper.get_reviews_by_page(1)
    print(f"Found {len(review_urls)} review URLs")

    stats = {
        "scraped": 0,
        "extracted": 0,
        "matched": 0,
    }

    with sync_session_maker() as session:
        matcher = ReviewMatcher(session)

        # Test first 5 reviews
        for url in review_urls[:5]:
            print(f"\n{'='*60}")
            print(f"URL: {url}")

            reviews = scraper.scrape_reviews(url)
            if not reviews:
                print("  -> No review data extracted")
                continue

            review = reviews[0]
            stats["scraped"] += 1
            print(f"  Title: {review.title}")

            # Extract brand/model
            brand, model = extract_brand_model_from_title(review.title or "")

            if not brand or not model:
                print(f"  -> Could not extract brand/model")
                continue

            stats["extracted"] += 1
            print(f"  Brand: {brand}, Model: {model}")

            # Match to product
            match = matcher.match_product(brand, model, url)

            if match:
                product, score = match
                stats["matched"] += 1
                print(f"  -> MATCHED: {product.name} (score={score:.2f})")

                # Show product details
                print(f"     Product ID: {product.id}")
                print(f"     Weight: {product.weight_oz}oz, Drop: {product.drop_mm}mm")
            else:
                print(f"  -> No match in database")

    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Reviews scraped: {stats['scraped']}")
    print(f"Brand/model extracted: {stats['extracted']}")
    print(f"Matched to products: {stats['matched']}")


if __name__ == '__main__':
    main()
