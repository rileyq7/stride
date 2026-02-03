"""
Scraper for Believe in the Run expert shoe reviews.

Site: https://believeintherun.com
Type: WordPress
Content: Expert reviews with 15-point scoring system (Form, Fit, Function)
"""

import re
import logging
from typing import List, Optional, Dict
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from .base import BaseScraper, RawReview
from .utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class BelieveInTheRunScraper(BaseScraper):
    """Scraper for Believe in the Run expert reviews."""

    SOURCE_NAME = 'believe_in_the_run'
    BASE_URL = 'https://believeintherun.com'
    REVIEW_INDEX_URL = 'https://believeintherun.com/shoe-reviews/'

    def __init__(self, config: dict):
        super().__init__(config)
        self.rate_limiter = RateLimiter(self.SOURCE_NAME)

    def get_product_url(self, shoe) -> Optional[str]:
        """Find the review URL for a given shoe on Believe in the Run."""
        shoe_name = shoe.name.lower()
        brand_name = shoe.brand.name.lower() if hasattr(shoe, 'brand') and shoe.brand else ''

        # Try direct URL pattern first (most reviews follow this pattern)
        slug = self._create_slug(brand_name, shoe_name)
        direct_url = f"{self.BASE_URL}/{slug}-review/"

        self.rate_limiter.wait_sync()
        try:
            response = self.client.head(direct_url, follow_redirects=True)
            if response.status_code == 200:
                return direct_url
        except Exception:
            pass

        # Fall back to searching the archive
        return self._search_archive(brand_name, shoe_name)

    def _create_slug(self, brand: str, name: str) -> str:
        """Create URL slug from brand and shoe name."""
        combined = f"{brand} {name}".lower()
        # Remove special characters and replace spaces with hyphens
        slug = re.sub(r'[^a-z0-9\s-]', '', combined)
        slug = re.sub(r'\s+', '-', slug)
        return slug

    def _search_archive(self, brand: str, shoe_name: str) -> Optional[str]:
        """Search the review archive for a matching shoe."""
        page = 1
        max_pages = 10  # Limit search depth

        while page <= max_pages:
            self.rate_limiter.wait_sync()

            try:
                url = self.REVIEW_INDEX_URL if page == 1 else f"{self.REVIEW_INDEX_URL}page/{page}/"
                response = self.client.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'lxml')

                # Find review links
                review_links = soup.select('article a[href*="-review"], a[href*="/shoe-reviews/"][href$="-review/"]')

                for link in review_links:
                    href = link.get('href', '')
                    link_text = link.get_text(strip=True).lower()

                    if self._matches_shoe(brand, shoe_name, href, link_text):
                        return href

                # Check for more pages
                next_link = soup.select_one('a.next, a[rel="next"], a:contains("Next")')
                if not next_link:
                    break

                page += 1

            except Exception as e:
                logger.error(f"Error searching archive page {page}: {e}")
                break

        return None

    def _matches_shoe(self, brand: str, shoe_name: str, href: str, link_text: str) -> bool:
        """Check if a link matches the target shoe."""
        combined = f"{href.lower()} {link_text}"

        # Extract key parts of shoe name
        name_parts = shoe_name.split()[:2]  # First two words

        brand_match = brand in combined if brand else True
        name_match = all(part.lower() in combined for part in name_parts)

        return brand_match and name_match

    def scrape_reviews(self, product_url: str) -> List[RawReview]:
        """Scrape the expert review from a Believe in the Run review page."""
        self.rate_limiter.wait_sync()

        try:
            response = self.client.get(product_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')

            review = self._parse_review_page(soup, product_url)
            if review:
                return [review]
            return []

        except Exception as e:
            logger.error(f"Error scraping review page {product_url}: {e}")
            return []

    def _parse_review_page(self, soup: BeautifulSoup, url: str) -> Optional[RawReview]:
        """Parse a single review page into a RawReview."""
        try:
            # Extract title
            title_elem = soup.select_one('h1')
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract scores
            scores = self._extract_scores(soup)

            # Extract specs
            specs = self._extract_specs(soup)

            # Extract review content from multiple reviewers
            review_content = self._extract_review_content(soup)

            # Build full review body
            body_parts = []

            if specs:
                body_parts.append(f"[SPECS] {specs}")

            if scores:
                scores_text = ', '.join([f"{k}: {v}" for k, v in scores.items()])
                body_parts.append(f"[SCORES] {scores_text}")

            body_parts.append(review_content)

            full_body = '\n\n'.join(body_parts)

            # Extract author(s)
            authors = self._extract_authors(soup)
            author_str = ', '.join(authors) if authors else 'Believe in the Run'

            # Extract date
            date_elem = soup.select_one('time, .date, .published')
            review_date = date_elem.get('datetime') or date_elem.get_text(strip=True) if date_elem else None

            # Generate unique ID
            review_id = self._url_to_id(url)

            # Extract overall rating if available
            rating = None
            if scores and 'Overall' in scores:
                try:
                    # Convert X/15 to a 5-point scale
                    overall = float(scores['Overall'].split('/')[0])
                    rating = round((overall / 15) * 5, 1)
                except (ValueError, IndexError):
                    pass

            return RawReview(
                source=self.SOURCE_NAME,
                source_review_id=review_id,
                source_url=url,
                reviewer_name=author_str,
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

    def _extract_scores(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract Form, Fit, Function scores."""
        scores = {}

        # Look for score patterns in the content
        content = soup.get_text()

        # Pattern: "Form: 4/5" or "Form 4/5"
        score_patterns = [
            (r'Form[:\s]+(\d+(?:\.\d+)?)\s*/\s*5', 'Form'),
            (r'Fit[:\s]+(\d+(?:\.\d+)?)\s*/\s*5', 'Fit'),
            (r'Function[:\s]+(\d+(?:\.\d+)?)\s*/\s*5', 'Function'),
            (r'Overall[:\s]+(\d+(?:\.\d+)?)\s*/\s*15', 'Overall'),
        ]

        for pattern, name in score_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                max_score = '5' if name != 'Overall' else '15'
                scores[name] = f"{match.group(1)}/{max_score}"

        # Also look for visual score indicators (yellow icons)
        score_sections = soup.select('.score-icon-yellow')
        # Count consecutive yellow icons for each score type

        return scores

    def _extract_specs(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract shoe specifications."""
        specs = []

        # Look for spec labels and their values
        spec_keywords = ['weight', 'stack height', 'drop', 'price', 'msrp']

        # Try finding a specs table or section
        for elem in soup.select('strong, b'):
            text = elem.get_text(strip=True).lower()
            if any(keyword in text for keyword in spec_keywords):
                # Get the next sibling or parent text
                parent = elem.parent
                if parent:
                    full_text = parent.get_text(strip=True)
                    if full_text and len(full_text) < 200:
                        specs.append(full_text)

        # Also check for structured spec sections
        content = soup.get_text()
        spec_patterns = [
            r'Weight[:\s]+([\d.]+\s*(?:oz|g))',
            r'Stack Height[:\s]+([\d./]+\s*mm)',
            r'Drop[:\s]+([\d.]+\s*mm)',
            r'Price[:\s]+\$?([\d.]+)',
        ]

        for pattern in spec_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                specs.append(match.group(0))

        return ' | '.join(specs) if specs else None

    def _extract_review_content(self, soup: BeautifulSoup) -> str:
        """Extract the main review content from multiple reviewers."""
        content_parts = []

        # Look for reviewer sections (marked by reviewer names in bold)
        reviewer_markers = ['CHAD:', 'RENALDO:', 'JARRETT:', 'THOMAS:', 'WIDE-FOOT']

        # Get all paragraphs
        paragraphs = soup.select('article p, .entry-content p, .post-content p')

        current_reviewer = None
        reviewer_content = []

        for p in paragraphs:
            text = p.get_text(strip=True)
            if len(text) < 10:
                continue

            # Check if this is a new reviewer section
            for marker in reviewer_markers:
                if marker in text.upper():
                    if current_reviewer and reviewer_content:
                        content_parts.append(f"[{current_reviewer}]\n" + '\n'.join(reviewer_content))
                    current_reviewer = marker.replace(':', '')
                    reviewer_content = [text]
                    break
            else:
                if current_reviewer:
                    reviewer_content.append(text)
                else:
                    content_parts.append(text)

        # Don't forget the last reviewer
        if current_reviewer and reviewer_content:
            content_parts.append(f"[{current_reviewer}]\n" + '\n'.join(reviewer_content))

        return '\n\n'.join(content_parts)

    def _extract_authors(self, soup: BeautifulSoup) -> List[str]:
        """Extract author names from the review."""
        authors = []

        # Look for author names in h5 tags
        for h5 in soup.select('h5'):
            text = h5.get_text(strip=True)
            if text and len(text) < 50 and not any(c.isdigit() for c in text):
                authors.append(text)

        # Also check for author bio sections
        for elem in soup.select('.author-name, .reviewer-name'):
            text = elem.get_text(strip=True)
            if text and text not in authors:
                authors.append(text)

        return authors[:5]  # Limit to 5 authors

    def _url_to_id(self, url: str) -> str:
        """Convert a URL to a unique review ID."""
        # Extract the slug from the URL
        match = re.search(r'believeintherun\.com/([^/]+)-review/?', url)
        if match:
            return f"bitr-{match.group(1)}"
        return url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]

    def get_reviews_by_page(self, page: int = 1) -> List[str]:
        """Get all review URLs from a specific archive page (for bulk scraping)."""
        self.rate_limiter.wait_sync()

        url = self.REVIEW_INDEX_URL if page == 1 else f"{self.REVIEW_INDEX_URL}page/{page}/"

        try:
            response = self.client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')

            urls = []
            # Try multiple selectors for review links
            selectors = [
                'a[href*="/shoe-reviews/"][href$="-review/"]',
                'a[href*="/shoe-reviews/"]',
                'a[href*="-review/"]',
                '.tribe-events-calendar-list__event-title-link',
            ]

            for selector in selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href', '')
                    # Filter out category/type pages, pagination, and ensure it's an actual review
                    if (href and 'believeintherun.com' in href and
                        '-review/' in href and
                        '/type/' not in href and
                        '/page/' not in href):
                        urls.append(href)

            return list(set(urls))  # Deduplicate

        except Exception as e:
            logger.error(f"Error fetching archive page {page}: {e}")
            return []

    def get_total_pages(self) -> int:
        """Get the total number of archive pages."""
        self.rate_limiter.wait_sync()

        try:
            response = self.client.get(self.REVIEW_INDEX_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')

            # Look for pagination numbers
            page_links = soup.select('a[href*="/page/"]')
            max_page = 1

            for link in page_links:
                href = link.get('href', '')
                match = re.search(r'/page/(\d+)/', href)
                if match:
                    page_num = int(match.group(1))
                    max_page = max(max_page, page_num)

            return max_page

        except Exception as e:
            logger.error(f"Error getting total pages: {e}")
            return 1
