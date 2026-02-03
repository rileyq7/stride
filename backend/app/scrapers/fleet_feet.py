"""
Scraper for Fleet Feet user reviews.

Site: https://www.fleetfeet.com
Type: React/Next.js (requires Playwright)
Content: User reviews with foot characteristic data
"""

import re
import logging
from typing import List, Optional
from bs4 import BeautifulSoup

from .playwright_base import PlaywrightBaseScraper
from .base import RawReview
from .utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class FleetFeetScraper(PlaywrightBaseScraper):
    """Scraper for Fleet Feet user reviews."""

    SOURCE_NAME = 'fleet_feet'
    BASE_URL = 'https://www.fleetfeet.com'

    def __init__(self, config: dict):
        super().__init__(config)
        self.rate_limiter = RateLimiter(self.SOURCE_NAME)

    async def get_product_url_async(self, shoe) -> Optional[str]:
        """Find the product URL on Fleet Feet."""
        shoe_name = shoe.name.lower()
        brand_name = shoe.brand.name.lower() if hasattr(shoe, 'brand') and shoe.brand else ''

        # Try search
        search_query = f"{brand_name} {shoe_name}".replace(' ', '+')
        search_url = f"{self.BASE_URL}/search?q={search_query}"

        content = await self.get_page_content(search_url, wait_selector='[data-testid="product-card"]')
        if not content:
            return None

        soup = BeautifulSoup(content, 'lxml')

        # Find product cards
        product_cards = soup.select('[data-testid="product-card"], .product-card, .product-tile')

        for card in product_cards:
            link = card.select_one('a[href*="/products/"]')
            if link:
                href = link.get('href', '')
                card_text = card.get_text(strip=True).lower()

                if self._matches_shoe(brand_name, shoe_name, href, card_text):
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
        """Scrape user reviews from a Fleet Feet product page."""
        # Load page with scrolling to trigger review widget
        content = await self.get_page_with_scroll(product_url, scroll_count=5)
        if not content:
            return []

        soup = BeautifulSoup(content, 'lxml')
        reviews = []

        # Find review containers
        review_elements = soup.select(
            '[data-testid="review"], .review-item, .review-card, '
            '.bv-content-item, [class*="ReviewCard"]'
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
                '.review-text, .review-body, .bv-content-summary-body, '
                '[class*="ReviewText"], [class*="review-content"]'
            )
            body = body_elem.get_text(strip=True) if body_elem else ''

            if not body or len(body) < 20:
                return None

            # Extract rating
            rating = self._extract_rating(elem)

            # Extract reviewer name
            name_elem = elem.select_one(
                '.reviewer-name, .author-name, .bv-author, '
                '[class*="ReviewerName"]'
            )
            reviewer_name = name_elem.get_text(strip=True) if name_elem else None

            # Extract title
            title_elem = elem.select_one(
                '.review-title, .bv-content-title, '
                '[class*="ReviewTitle"]'
            )
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract date
            date_elem = elem.select_one(
                '.review-date, .bv-content-datetime, time, '
                '[class*="ReviewDate"]'
            )
            review_date = None
            if date_elem:
                review_date = date_elem.get('datetime') or date_elem.get_text(strip=True)

            # Extract reviewer characteristics
            width, arch, size = self._extract_reviewer_characteristics(elem)

            # Generate review ID
            review_id = elem.get('data-review-id') or elem.get('id') or f"ff-{hash(body[:50])}"

            return RawReview(
                source=self.SOURCE_NAME,
                source_review_id=str(review_id),
                source_url=source_url,
                reviewer_name=reviewer_name,
                rating=rating,
                title=title,
                body=body,
                review_date=review_date,
                reviewer_foot_width=width,
                reviewer_arch_type=arch,
                reviewer_size_purchased=size,
                reviewer_typical_size=None,
            )

        except Exception as e:
            logger.error(f"Failed to parse review: {e}")
            return None

    def _extract_rating(self, elem) -> Optional[float]:
        """Extract rating from review element."""
        # Try various rating selectors
        rating_elem = elem.select_one(
            '[class*="rating"], .stars, .bv-rating, '
            '[data-rating], [aria-label*="star"]'
        )

        if rating_elem:
            # Check for data attribute
            rating_val = rating_elem.get('data-rating')
            if rating_val:
                try:
                    return float(rating_val)
                except ValueError:
                    pass

            # Check aria-label
            aria = rating_elem.get('aria-label', '')
            match = re.search(r'(\d+(?:\.\d+)?)\s*(?:out of|/)\s*5', aria)
            if match:
                return float(match.group(1))

            # Check text content
            text = rating_elem.get_text(strip=True)
            match = re.search(r'(\d+(?:\.\d+)?)', text)
            if match:
                return float(match.group(1))

        # Count filled stars
        filled_stars = elem.select('.star-filled, .star-full, [class*="StarFilled"]')
        if filled_stars:
            return float(len(filled_stars))

        return None

    def _extract_reviewer_characteristics(self, elem):
        """Extract foot width, arch type, and size from reviewer info."""
        width = None
        arch = None
        size = None

        # Look for characteristic badges or text
        stats_elem = elem.select_one(
            '.reviewer-stats, .reviewer-info, .bv-content-author-badges, '
            '[class*="ReviewerInfo"]'
        )

        if stats_elem:
            text = stats_elem.get_text(strip=True).lower()

            # Width
            if 'wide' in text:
                width = 'wide'
            elif 'narrow' in text:
                width = 'narrow'
            elif 'regular' in text or 'normal' in text:
                width = 'normal'

            # Arch
            if 'high arch' in text:
                arch = 'high'
            elif 'flat' in text or 'low arch' in text:
                arch = 'flat'
            elif 'neutral' in text or 'normal arch' in text:
                arch = 'neutral'

            # Size
            size_match = re.search(r'size[:\s]*([\d.]+)', text)
            if size_match:
                size = size_match.group(1)

        # Also check data attributes
        for attr in ['data-width', 'data-arch', 'data-size']:
            val = elem.get(attr)
            if val:
                if 'width' in attr:
                    width = val
                elif 'arch' in attr:
                    arch = val
                elif 'size' in attr:
                    size = val

        return width, arch, size
