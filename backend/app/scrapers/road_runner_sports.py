"""
Scraper for Road Runner Sports user reviews.

Site: https://www.roadrunnersports.com
Type: Next.js (requires Playwright)
Content: User reviews with fit feedback
"""

import re
import logging
from typing import List, Optional
from bs4 import BeautifulSoup

from .playwright_base import PlaywrightBaseScraper
from .base import RawReview
from .utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class RoadRunnerSportsScraper(PlaywrightBaseScraper):
    """Scraper for Road Runner Sports user reviews."""

    SOURCE_NAME = 'road_runner_sports'
    BASE_URL = 'https://www.roadrunnersports.com'

    def __init__(self, config: dict):
        super().__init__(config)
        self.rate_limiter = RateLimiter(self.SOURCE_NAME)

    async def get_product_url_async(self, shoe) -> Optional[str]:
        """Find the product URL on Road Runner Sports."""
        shoe_name = shoe.name.lower()
        brand_name = shoe.brand.name.lower() if hasattr(shoe, 'brand') and shoe.brand else ''

        # Try search
        search_query = f"{brand_name} {shoe_name}".replace(' ', '%20')
        search_url = f"{self.BASE_URL}/search/?q={search_query}"

        content = await self.get_page_content(search_url, wait_selector='.product-tile')
        if not content:
            return None

        soup = BeautifulSoup(content, 'lxml')

        # Find product tiles
        product_tiles = soup.select('.product-tile, [data-product], .product-card')

        for tile in product_tiles:
            link = tile.select_one('a[href*="/product/"]')
            if link:
                href = link.get('href', '')
                tile_text = tile.get_text(strip=True).lower()

                if self._matches_shoe(brand_name, shoe_name, href, tile_text):
                    if not href.startswith('http'):
                        href = f"{self.BASE_URL}{href}"
                    return href

        return None

    def _matches_shoe(self, brand: str, shoe_name: str, href: str, text: str) -> bool:
        """Check if a product matches the target shoe."""
        combined = f"{href.lower()} {text}"
        name_parts = shoe_name.split()[:2]

        brand_match = brand in combined if brand else True
        name_match = all(part.lower() in combined for part in name_parts)

        return brand_match and name_match

    async def scrape_reviews_async(self, product_url: str) -> List[RawReview]:
        """Scrape user reviews from a Road Runner Sports product page."""
        content = await self.get_page_with_scroll(product_url, scroll_count=5)
        if not content:
            return []

        soup = BeautifulSoup(content, 'lxml')
        reviews = []

        # Find review containers
        review_elements = soup.select(
            '.review, .review-item, [data-review-id], '
            '.pr-review, [class*="ReviewItem"]'
        )

        for elem in review_elements:
            review = self._parse_review_element(elem, product_url)
            if review:
                reviews.append(review)

        return reviews

    def _parse_review_element(self, elem, source_url: str) -> Optional[RawReview]:
        """Parse a single review element."""
        try:
            # Extract review body
            body_elem = elem.select_one(
                '.review-text, .review-body, .pr-review-text, '
                '[class*="ReviewText"], .review-content'
            )
            body = body_elem.get_text(strip=True) if body_elem else ''

            if not body or len(body) < 20:
                return None

            # Extract rating
            rating = self._extract_rating(elem)

            # Extract reviewer name
            name_elem = elem.select_one(
                '.reviewer-name, .pr-reviewer-name, '
                '[class*="ReviewerName"]'
            )
            reviewer_name = name_elem.get_text(strip=True) if name_elem else None

            # Extract title
            title_elem = elem.select_one(
                '.review-title, .pr-review-title, '
                '[class*="ReviewTitle"]'
            )
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract date
            date_elem = elem.select_one(
                '.review-date, .pr-review-date, time, '
                '[class*="ReviewDate"]'
            )
            review_date = None
            if date_elem:
                review_date = date_elem.get('datetime') or date_elem.get_text(strip=True)

            # Extract fit feedback
            fit_info = self._extract_fit_feedback(elem)

            # Append fit info to body if available
            if fit_info:
                body = f"{body}\n\n[FIT FEEDBACK] {fit_info}"

            # Generate review ID
            review_id = elem.get('data-review-id') or elem.get('id') or f"rrs-{hash(body[:50])}"

            return RawReview(
                source=self.SOURCE_NAME,
                source_review_id=str(review_id),
                source_url=source_url,
                reviewer_name=reviewer_name,
                rating=rating,
                title=title,
                body=body,
                review_date=review_date,
                reviewer_foot_width=None,
                reviewer_arch_type=None,
                reviewer_size_purchased=None,
                reviewer_typical_size=None,
            )

        except Exception as e:
            logger.error(f"Failed to parse review: {e}")
            return None

    def _extract_rating(self, elem) -> Optional[float]:
        """Extract rating from review element."""
        rating_elem = elem.select_one(
            '[class*="rating"], .stars, .pr-rating, '
            '[data-rating]'
        )

        if rating_elem:
            rating_val = rating_elem.get('data-rating')
            if rating_val:
                try:
                    return float(rating_val)
                except ValueError:
                    pass

            text = rating_elem.get_text(strip=True)
            match = re.search(r'(\d+(?:\.\d+)?)', text)
            if match:
                return float(match.group(1))

        # Count stars
        filled = elem.select('[class*="star"][class*="filled"], .star-full')
        if filled:
            return float(len(filled))

        return None

    def _extract_fit_feedback(self, elem) -> Optional[str]:
        """Extract fit-related feedback from the review."""
        fit_parts = []

        # Look for specific fit attribute sections
        fit_selectors = [
            '.fit-feedback', '.size-feedback', '.pr-fit-attributes',
            '[class*="FitFeedback"]', '[data-fit]'
        ]

        for selector in fit_selectors:
            fit_elem = elem.select_one(selector)
            if fit_elem:
                fit_parts.append(fit_elem.get_text(strip=True))

        # Also check for common fit indicators in attribute badges
        badge_elems = elem.select('.badge, .attribute, .tag, [class*="Badge"]')
        for badge in badge_elems:
            text = badge.get_text(strip=True).lower()
            if any(kw in text for kw in ['fit', 'size', 'width', 'true to size', 'runs']):
                fit_parts.append(badge.get_text(strip=True))

        return ' | '.join(fit_parts) if fit_parts else None
