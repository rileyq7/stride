#!/usr/bin/env python
"""
Script to run scrapers and ingest real data.

Usage:
    python scripts/run_scrapers.py --help
    python scripts/run_scrapers.py reviews --shoe-id <uuid>
    python scripts/run_scrapers.py reviews --category running
    python scripts/run_scrapers.py specs --brand Nike
    python scripts/run_scrapers.py full --shoe-id <uuid>
    python scripts/run_scrapers.py list-reviews --source doctors_of_running --limit 10
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.scrapers import (
    SCRAPER_CONFIGS,
    get_scraper_for_source,
    DoctorsOfRunningScraper,
    BelieveInTheRunScraper,
    get_brand_scraper,
)
from app.tasks.scraper_tasks import (
    scrape_shoe_reviews,
    scrape_shoe_specs,
    scrape_category,
    full_shoe_scrape,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def list_available_sources():
    """List all available scraper sources."""
    print("\n=== Available Review Sources ===")
    for category, sources in SCRAPER_CONFIGS.items():
        print(f"\n{category.upper()}:")
        for source, config in sources.items():
            review_type = config.get('review_type', 'user')
            requires_browser = config.get('requires_browser', False)
            browser_note = " (requires browser)" if requires_browser else ""
            print(f"  - {source} [{review_type}]{browser_note}")


def list_reviews_from_source(source: str, limit: int = 10):
    """List available reviews from a specific source."""
    print(f"\nFetching reviews from {source}...")

    if source == 'doctors_of_running':
        scraper = DoctorsOfRunningScraper({'base_url': 'https://www.doctorsofrunning.com'})
        urls = scraper.get_all_review_urls()
        print(f"Found {len(urls)} reviews")
        print("\nSample URLs:")
        for url in urls[:limit]:
            print(f"  {url}")

    elif source == 'believe_in_the_run':
        scraper = BelieveInTheRunScraper({'base_url': 'https://believeintherun.com'})
        total_pages = scraper.get_total_pages()
        print(f"Found {total_pages} pages of reviews")
        urls = scraper.get_reviews_by_page(1)
        print(f"\nPage 1 has {len(urls)} reviews:")
        for url in urls[:limit]:
            print(f"  {url}")

    else:
        print(f"Direct listing not supported for {source}")


async def run_review_scrape(shoe_id: str = None, category: str = None, sources: list = None):
    """Run review scraping."""
    if shoe_id:
        print(f"Scraping reviews for shoe: {shoe_id}")
        result = await scrape_shoe_reviews(shoe_id, sources)
        print(f"Result: {result}")

    elif category:
        # Would need to look up category ID from database
        print(f"Category scraping requires database connection")
        print("Use: python scripts/run_scrapers.py reviews --shoe-id <uuid>")


async def run_specs_scrape(brand: str = None, shoe_id: str = None):
    """Run brand specs scraping."""
    if shoe_id:
        print(f"Scraping specs for shoe: {shoe_id}")
        result = await scrape_shoe_specs(shoe_id)
        print(f"Result: {result}")

    elif brand:
        scraper = get_brand_scraper(brand)
        if scraper:
            print(f"Brand scraper available: {type(scraper).__name__}")
            print("Note: Full scraping requires database connection with shoe IDs")
        else:
            print(f"No scraper available for brand: {brand}")


def main():
    parser = argparse.ArgumentParser(description='Run shoe scrapers')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # List command
    list_parser = subparsers.add_parser('list', help='List available sources')

    # List reviews command
    list_reviews_parser = subparsers.add_parser('list-reviews', help='List reviews from a source')
    list_reviews_parser.add_argument('--source', required=True, help='Source name')
    list_reviews_parser.add_argument('--limit', type=int, default=10, help='Number of reviews to list')

    # Reviews command
    reviews_parser = subparsers.add_parser('reviews', help='Scrape reviews')
    reviews_parser.add_argument('--shoe-id', help='Shoe UUID to scrape')
    reviews_parser.add_argument('--category', help='Category to scrape (running/basketball)')
    reviews_parser.add_argument('--sources', nargs='+', help='Specific sources to use')

    # Specs command
    specs_parser = subparsers.add_parser('specs', help='Scrape brand specs')
    specs_parser.add_argument('--shoe-id', help='Shoe UUID to scrape specs for')
    specs_parser.add_argument('--brand', help='Brand to test')

    # Full command
    full_parser = subparsers.add_parser('full', help='Full scrape (specs + reviews)')
    full_parser.add_argument('--shoe-id', required=True, help='Shoe UUID')

    args = parser.parse_args()

    if args.command == 'list':
        list_available_sources()

    elif args.command == 'list-reviews':
        list_reviews_from_source(args.source, args.limit)

    elif args.command == 'reviews':
        asyncio.run(run_review_scrape(
            shoe_id=args.shoe_id,
            category=args.category,
            sources=args.sources
        ))

    elif args.command == 'specs':
        asyncio.run(run_specs_scrape(brand=args.brand, shoe_id=args.shoe_id))

    elif args.command == 'full':
        asyncio.run(full_shoe_scrape(args.shoe_id))

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
