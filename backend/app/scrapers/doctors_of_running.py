"""
Scraper for Doctors of Running expert shoe reviews.

Site: https://www.doctorsofrunning.com
Type: Blogger platform
Content: Expert reviews from physical therapists
"""

import re
import logging
from typing import List, Optional
from bs4 import BeautifulSoup

from .base import BaseScraper, RawReview
from .utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class DoctorsOfRunningScraper(BaseScraper):
    """Scraper for Doctors of Running expert reviews."""

    SOURCE_NAME = 'doctors_of_running'
    REVIEW_INDEX_URL = 'https://www.doctorsofrunning.com/p/reviews.html'

    def __init__(self, config: dict):
        super().__init__(config)
        self.rate_limiter = RateLimiter(self.SOURCE_NAME)

    def get_product_url(self, shoe) -> Optional[str]:
        """Find the review URL for a given shoe on Doctors of Running."""
        self.rate_limiter.wait_sync()

        try:
            response = self.client.get(self.REVIEW_INDEX_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')

            # Build search terms from shoe name
            shoe_name = shoe.name.lower()
            brand_name = shoe.brand.name.lower() if hasattr(shoe, 'brand') and shoe.brand else ''

            # Find all review links
            all_links = soup.select('a[href*="-review-"]')

            for link in all_links:
                href = link.get('href', '')
                link_text = link.get_text(strip=True).lower()

                # Check if this link matches our shoe
                if self._matches_shoe(shoe_name, brand_name, href, link_text):
                    return href

            # Also try searching in the content
            content_links = soup.select('.post-body a')
            for link in content_links:
                href = link.get('href', '')
                link_text = link.get_text(strip=True).lower()

                if '-review-' in href and self._matches_shoe(shoe_name, brand_name, href, link_text):
                    return href

            logger.info(f"No review found for {brand_name} {shoe_name} on Doctors of Running")
            return None

        except Exception as e:
            logger.error(f"Error searching Doctors of Running: {e}")
            return None

    def _matches_shoe(self, shoe_name: str, brand_name: str, href: str, link_text: str) -> bool:
        """Check if a link matches the target shoe."""
        href_lower = href.lower()
        combined_text = f"{link_text} {href_lower}"

        # Extract key parts of shoe name (e.g., "Ghost 15" -> ["ghost", "15"])
        shoe_parts = shoe_name.split()

        # Check if brand and main shoe identifier are present
        brand_match = brand_name in combined_text if brand_name else True
        name_match = all(part.lower() in combined_text for part in shoe_parts[:2])  # First two words

        return brand_match and name_match

    def scrape_reviews(self, product_url: str) -> List[RawReview]:
        """Scrape the expert review from a Doctors of Running review page."""
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
            title_elem = soup.select_one('h1.post-title, .posttitle h1, h1')
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract author(s)
            author_elem = soup.select_one('.mino-post-author, .author-content h5 a, .post-author')
            author = author_elem.get_text(strip=True) if author_elem else 'Doctors of Running'

            # Extract specs from blockquote
            specs = self._extract_specs(soup)

            # Extract main review content
            review_body = self._extract_review_content(soup)

            # Extract fit-specific content
            fit_content = self._extract_fit_section(soup)

            # Combine content with fit section highlighted
            full_body = review_body
            if fit_content:
                full_body = f"{review_body}\n\n[FIT ANALYSIS]\n{fit_content}"

            # Add specs to body for AI extraction
            if specs:
                specs_text = f"\n[SPECS] {specs}"
                full_body = f"{specs_text}\n\n{full_body}"

            # Extract review date
            date_elem = soup.select_one('time, .date-header, .published')
            review_date = date_elem.get('datetime') or date_elem.get_text(strip=True) if date_elem else None

            # Generate a unique ID from the URL
            review_id = self._url_to_id(url)

            return RawReview(
                source=self.SOURCE_NAME,
                source_review_id=review_id,
                source_url=url,
                reviewer_name=author,
                rating=None,  # No numeric rating on this site
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

    def _extract_specs(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract shoe specifications from the review page."""
        # Specs are typically in a blockquote at the top
        blockquote = soup.select_one('.post-body blockquote')
        if blockquote:
            text = blockquote.get_text(strip=True)
            # Check if it contains spec keywords
            if any(keyword in text.lower() for keyword in ['price', 'weight', 'stack', 'drop', 'msrp']):
                return text

        # Alternative: look for specs in the first few paragraphs
        paragraphs = soup.select('.post-body > p')[:5]
        for p in paragraphs:
            text = p.get_text(strip=True)
            if any(keyword in text.lower() for keyword in ['price:', 'weight:', 'stack height:', 'drop:']):
                return text

        return None

    def _extract_review_content(self, soup: BeautifulSoup) -> str:
        """Extract the main review content."""
        post_body = soup.select_one('.post-body')
        if not post_body:
            return ''

        # Get all paragraphs
        paragraphs = []
        for elem in post_body.find_all(['p', 'li']):
            text = elem.get_text(strip=True)
            if text and len(text) > 20:  # Filter out short fragments
                paragraphs.append(text)

        return '\n\n'.join(paragraphs)

    def _extract_fit_section(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the FIT section specifically."""
        post_body = soup.select_one('.post-body')
        if not post_body:
            return None

        content = str(post_body)

        # Look for FIT section markers
        fit_patterns = [
            r'<strong>\s*FIT\s*</strong>(.*?)(?=<strong>|$)',
            r'<b>\s*FIT\s*</b>(.*?)(?=<b>|$)',
            r'\*\*FIT\*\*(.*?)(?=\*\*|$)',
        ]

        for pattern in fit_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                fit_html = match.group(1)
                fit_soup = BeautifulSoup(fit_html, 'lxml')
                fit_text = fit_soup.get_text(strip=True)
                if len(fit_text) > 50:  # Ensure we have substantial content
                    return fit_text

        # Fallback: search for fit-related keywords in paragraphs
        paragraphs = post_body.find_all('p')
        fit_paragraphs = []
        for p in paragraphs:
            text = p.get_text(strip=True).lower()
            if any(keyword in text for keyword in ['fit', 'sizing', 'runs true', 'runs small', 'runs large', 'width', 'toe box']):
                fit_paragraphs.append(p.get_text(strip=True))

        if fit_paragraphs:
            return '\n'.join(fit_paragraphs[:5])  # Limit to 5 most relevant

        return None

    def _url_to_id(self, url: str) -> str:
        """Convert a URL to a unique review ID."""
        # Extract the path portion after the domain
        match = re.search(r'doctorsofrunning\.com/(.+)\.html', url)
        if match:
            return match.group(1).replace('/', '-')
        return url.split('/')[-1].replace('.html', '')

    def get_all_review_urls(self) -> List[str]:
        """Get all review URLs from the index page (for bulk scraping)."""
        self.rate_limiter.wait_sync()

        try:
            response = self.client.get(self.REVIEW_INDEX_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')

            urls = set()
            for link in soup.select('a[href*="-review-"]'):
                href = link.get('href', '')
                if href and 'doctorsofrunning.com' in href:
                    urls.add(href)

            return list(urls)

        except Exception as e:
            logger.error(f"Error fetching review index: {e}")
            return []
