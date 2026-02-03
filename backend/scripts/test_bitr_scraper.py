#!/usr/bin/env python
"""
Test the existing BelieveInTheRunScraper.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.scrapers.believe_in_the_run import BelieveInTheRunScraper


def main():
    print("=" * 70)
    print("TESTING BITR SCRAPER")
    print("=" * 70)

    scraper = BelieveInTheRunScraper({})

    # Test getting review pages
    print("\n--- Getting archive pages ---")
    total_pages = scraper.get_total_pages()
    print(f"Total pages: {total_pages}")

    print("\n--- Getting reviews from page 1 ---")
    urls = scraper.get_reviews_by_page(1)
    print(f"Found {len(urls)} review URLs:")
    for url in urls[:5]:
        print(f"  {url}")

    if urls:
        # Test scraping first review
        print(f"\n--- Scraping: {urls[0]} ---")
        reviews = scraper.scrape_reviews(urls[0])

        if reviews:
            review = reviews[0]
            print(f"Title: {review.title}")
            print(f"Author: {review.reviewer_name}")
            print(f"Rating: {review.rating}")
            print(f"Date: {review.review_date}")
            print(f"Body preview: {review.body[:500] if review.body else 'None'}...")
        else:
            print("No reviews extracted!")


if __name__ == '__main__':
    main()
