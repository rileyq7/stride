#!/usr/bin/env python
"""
Test the ReviewMatcher service.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import sync_session_maker
from app.services.review_matcher import (
    ReviewMatcher,
    normalize_brand,
    fuzzy_match_score,
    extract_brand_model_from_title
)


def main():
    print("=" * 70)
    print("REVIEW MATCHER TEST")
    print("=" * 70)

    # Test brand normalization
    print("\n--- Brand Normalization ---")
    test_brands = ['Brooks', 'HOKA', 'New Balance', 'NB', 'On Running', 'Altra']
    for brand in test_brands:
        print(f"  {brand} -> {normalize_brand(brand)}")

    # Test fuzzy matching
    print("\n--- Fuzzy Match Scores ---")
    test_pairs = [
        ("Ghost 16", "Ghost 16"),
        ("Ghost 16", "ghost-16"),
        ("Ghost Max 2", "Ghost Max"),
        ("Pegasus 41", "Air Zoom Pegasus 41"),
        ("Clifton 9", "Clifton 10"),
        ("Totally Different", "Ghost 16"),
    ]
    for query, target in test_pairs:
        score = fuzzy_match_score(query, target)
        print(f"  '{query}' vs '{target}': {score:.2f}")

    # Test title extraction
    print("\n--- Title Extraction ---")
    test_titles = [
        "Brooks Ghost 16 Review: Great Daily Trainer",
        "HOKA Clifton 9 Review",
        "Saucony Guide 19 Review: Pulling In a Different Direction",
        "Nike Pegasus 41 - Review",
        "Asics Gel Nimbus 26 Review",
    ]
    for title in test_titles:
        brand, model = extract_brand_model_from_title(title)
        print(f"  '{title[:40]}...' -> brand={brand}, model={model}")

    # Test actual product matching
    print("\n--- Product Matching (DB) ---")
    with sync_session_maker() as session:
        matcher = ReviewMatcher(session)

        test_matches = [
            ("Brooks", "Ghost 16"),
            ("Hoka", "Clifton 9"),
            ("Nike", "Pegasus 41"),
            ("Asics", "Gel Nimbus 26"),
            ("Saucony", "Guide 19"),
            ("Unknown Brand", "Some Shoe"),
        ]

        for brand, model in test_matches:
            result = matcher.match_product(brand, model)
            if result:
                product, score = result
                print(f"  {brand} {model} -> {product.name} (score={score:.2f})")
            else:
                print(f"  {brand} {model} -> No match")


if __name__ == '__main__':
    main()
