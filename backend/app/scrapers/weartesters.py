"""
Scraper for WearTesters basketball shoe reviews.

Site: https://weartesters.com
Type: WordPress (requires Playwright due to 403 blocks)
Content: Expert basketball shoe performance reviews
"""

import re
import logging
from typing import List, Optional, Dict
from bs4 import BeautifulSoup

from .playwright_base import PlaywrightBaseScraper
from .base import RawReview
from .utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class WearTestersScraper(PlaywrightBaseScraper):
    """Scraper for WearTesters basketball shoe expert reviews."""

    SOURCE_NAME = 'weartesters'
    BASE_URL = 'https://weartesters.com'
    REVIEW_INDEX_URL = 'https://weartesters.com/category/performance-reviews/basketball-shoes-reviews/'

    def __init__(self, config: dict):
        super().__init__(config)
        self.rate_limiter = RateLimiter(self.SOURCE_NAME)

    async def get_product_url_async(self, shoe) -> Optional[str]:
        """Find the review URL for a given basketball shoe."""
        shoe_name = shoe.name.lower()
        brand_name = shoe.brand.name.lower() if hasattr(shoe, 'brand') and shoe.brand else ''

        # Try direct URL pattern first
        slug = self._create_slug(brand_name, shoe_name)
        patterns = [
            f"{self.BASE_URL}/{slug}-performance-review/",
            f"{self.BASE_URL}/{slug}-performance-review-2/",
            f"{self.BASE_URL}/{slug}-review/",
        ]

        for url in patterns:
            content = await self.get_page_content(url)
            if content and 'performance' in content.lower():
                return url

        # Fall back to search
        return await self._search_for_review(brand_name, shoe_name)

    def _create_slug(self, brand: str, name: str) -> str:
        """Create URL slug from brand and shoe name."""
        combined = f"{brand} {name}".lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', combined)
        slug = re.sub(r'\s+', '-', slug)
        return slug

    async def _search_for_review(self, brand: str, shoe_name: str) -> Optional[str]:
        """Search for a review using the site search."""
        search_query = f"{brand} {shoe_name}".replace(' ', '+')
        search_url = f"{self.BASE_URL}/?s={search_query}"

        content = await self.get_page_content(search_url)
        if not content:
            return None

        soup = BeautifulSoup(content, 'lxml')

        # Find review links in search results
        for link in soup.select('article a, .entry-title a, h2 a'):
            href = link.get('href', '')
            link_text = link.get_text(strip=True).lower()

            if 'performance-review' in href or 'review' in href:
                if self._matches_shoe(brand, shoe_name, href, link_text):
                    return href

        return None

    def _matches_shoe(self, brand: str, shoe_name: str, href: str, link_text: str) -> bool:
        """Check if a link matches the target shoe."""
        combined = f"{href.lower()} {link_text}"
        name_parts = shoe_name.split()[:2]

        brand_match = brand in combined if brand else True
        name_match = all(part.lower() in combined for part in name_parts)

        return brand_match and name_match

    async def scrape_reviews_async(self, product_url: str) -> List[RawReview]:
        """Scrape the expert review from a WearTesters review page."""
        content = await self.get_page_content(product_url)
        if not content:
            return []

        soup = BeautifulSoup(content, 'lxml')
        review = self._parse_review_page(soup, product_url)

        if review:
            return [review]
        return []

    def _parse_review_page(self, soup: BeautifulSoup, url: str) -> Optional[RawReview]:
        """Parse a WearTesters review page."""
        try:
            # Extract title
            title_elem = soup.select_one('h1.entry-title, h1')
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract performance scores
            scores = self._extract_performance_scores(soup)

            # Extract review content
            review_content = self._extract_review_content(soup)

            # Extract specs
            specs = self._extract_specs(soup)

            # Build full body
            body_parts = []

            if specs:
                body_parts.append(f"[SPECS] {specs}")

            if scores:
                scores_text = ', '.join([f"{k}: {v}/10" for k, v in scores.items()])
                body_parts.append(f"[PERFORMANCE SCORES] {scores_text}")

            body_parts.append(review_content)

            full_body = '\n\n'.join(body_parts)

            # Extract author
            author_elem = soup.select_one('.author-name, .entry-author, [rel="author"]')
            author = author_elem.get_text(strip=True) if author_elem else 'WearTesters'

            # Extract date
            date_elem = soup.select_one('time, .entry-date, .published')
            review_date = date_elem.get('datetime') or date_elem.get_text(strip=True) if date_elem else None

            # Calculate overall rating from scores
            rating = None
            if scores:
                avg_score = sum(scores.values()) / len(scores)
                rating = round(avg_score / 2, 1)  # Convert 10-point to 5-point scale

            review_id = self._url_to_id(url)

            return RawReview(
                source=self.SOURCE_NAME,
                source_review_id=review_id,
                source_url=url,
                reviewer_name=author,
                rating=rating,
                title=title,
                body=full_body,
                review_date=review_date,
                reviewer_foot_width=None,
                reviewer_arch_type=None,
                reviewer_size_purchased=None,
                reviewer_typical_size=None,
            )

        except Exception as e:
            logger.error(f"Failed to parse review page: {e}")
            return None

    def _extract_performance_scores(self, soup: BeautifulSoup) -> Dict[str, int]:
        """Extract performance scores (Traction, Cushion, Materials, Fit, Support, etc.)."""
        scores = {}

        # WearTesters uses a rating scale for each category
        score_categories = ['Traction', 'Cushion', 'Materials', 'Fit', 'Support', 'Outsole Durability']

        content = soup.get_text()

        for category in score_categories:
            # Pattern: "Traction: 9/10" or "Traction – 9"
            patterns = [
                rf'{category}[:\s–-]+(\d+)\s*/?\s*10',
                rf'{category}[:\s–-]+(\d+)',
            ]

            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    try:
                        scores[category] = int(match.group(1))
                        break
                    except ValueError:
                        continue

        return scores

    def _extract_specs(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract shoe specifications."""
        specs = []
        content = soup.get_text()

        spec_patterns = [
            r'Weight[:\s]+([\d.]+\s*(?:oz|g))',
            r'Price[:\s]+\$?([\d.]+)',
            r'Release Date[:\s]+([A-Za-z]+\s+\d+,?\s+\d+)',
        ]

        for pattern in spec_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                specs.append(match.group(0))

        return ' | '.join(specs) if specs else None

    def _extract_review_content(self, soup: BeautifulSoup) -> str:
        """Extract the main review content."""
        content_parts = []

        # Find main content area
        content_area = soup.select_one('.entry-content, article .content, .post-content')
        if not content_area:
            content_area = soup

        # Get paragraphs
        for p in content_area.select('p'):
            text = p.get_text(strip=True)
            if len(text) > 30:  # Filter short fragments
                content_parts.append(text)

        # Also look for specific section headers
        sections = ['TRACTION', 'CUSHION', 'MATERIALS', 'FIT', 'SUPPORT', 'OVERALL']
        for elem in content_area.select('h2, h3, strong'):
            text = elem.get_text(strip=True).upper()
            if any(section in text for section in sections):
                # Get following content
                next_elem = elem.find_next_sibling(['p', 'div'])
                if next_elem:
                    section_content = next_elem.get_text(strip=True)
                    if section_content:
                        content_parts.append(f"[{text}] {section_content}")

        return '\n\n'.join(content_parts)

    def _url_to_id(self, url: str) -> str:
        """Convert URL to unique review ID."""
        match = re.search(r'weartesters\.com/([^/]+)/?$', url)
        if match:
            return f"wt-{match.group(1)}"
        return url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]

    async def get_recent_reviews(self, page: int = 1) -> List[str]:
        """Get review URLs from the basketball reviews archive."""
        url = self.REVIEW_INDEX_URL if page == 1 else f"{self.REVIEW_INDEX_URL}page/{page}/"

        content = await self.get_page_with_scroll(url)
        if not content:
            return []

        soup = BeautifulSoup(content, 'lxml')
        urls = []

        for link in soup.select('article a[href*="review"], .entry-title a'):
            href = link.get('href', '')
            if href and 'weartesters.com' in href and 'review' in href.lower():
                urls.append(href)

        return list(set(urls))
