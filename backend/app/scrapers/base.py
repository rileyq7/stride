from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


@dataclass
class RawReview:
    """Represents a raw review scraped from a source."""
    source: str
    source_review_id: str
    source_url: str
    reviewer_name: Optional[str]
    rating: Optional[float]
    title: Optional[str]
    body: str
    review_date: Optional[str]
    reviewer_foot_width: Optional[str] = None
    reviewer_arch_type: Optional[str] = None
    reviewer_size_purchased: Optional[str] = None
    reviewer_typical_size: Optional[str] = None

    # Expert review fields
    review_type: str = 'user'  # 'user' or 'expert'
    expert_credentials: Optional[str] = None  # e.g., "PT DPT PhD"
    miles_tested: Optional[int] = None
    testing_methodology: Optional[str] = None

    # Structured scores (for sites like Believe in the Run)
    form_score: Optional[float] = None
    fit_score: Optional[float] = None
    function_score: Optional[float] = None
    overall_score: Optional[float] = None

    # Additional fit recommendations
    sizing_recommendation: Optional[str] = None  # 'true_to_size', 'size_up', 'size_down'
    width_recommendation: Optional[str] = None  # 'narrow', 'normal', 'wide'


class BaseScraper(ABC):
    """Base class for all review scrapers."""

    def __init__(self, config: dict):
        self.config = config
        self.client = httpx.Client(
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            },
            timeout=30.0,
            follow_redirects=True,
        )

    def __del__(self):
        try:
            self.client.close()
        except Exception:
            pass

    @abstractmethod
    def get_product_url(self, shoe) -> Optional[str]:
        """Find the product page URL for a given shoe."""
        pass

    @abstractmethod
    def scrape_reviews(self, product_url: str) -> List[RawReview]:
        """Scrape all reviews from a product page."""
        pass

    def scrape_shoe(self, shoe) -> List[RawReview]:
        """Main entry point: find product and scrape reviews."""
        url = self.get_product_url(shoe)
        if not url:
            logger.warning(f"Could not find product URL for {shoe.name}")
            return []
        return self.scrape_reviews(url)

    def _safe_text(self, element, selector: str) -> Optional[str]:
        """Safely extract text from an element."""
        if element is None:
            return None
        found = element.select_one(selector)
        return found.get_text(strip=True) if found else None

    def _parse_rating(self, element) -> Optional[float]:
        """Parse rating from an element. Override in subclasses."""
        return None


class RunningWarehouseScraper(BaseScraper):
    """Scraper for Running Warehouse reviews."""

    def get_product_url(self, shoe) -> Optional[str]:
        """Search for the shoe on Running Warehouse."""
        search_url = f"{self.config['base_url']}/searchresults.html"
        query = f"{shoe.brand.name} {shoe.name}"

        try:
            response = self.client.get(search_url, params={'searchtext': query})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')

            # Find matching product
            results = soup.select('.product-card, .product-item')
            for result in results:
                title_elem = result.select_one('.product-name, .product-title, h3 a')
                if title_elem:
                    title = title_elem.get_text(strip=True).lower()
                    if shoe.name.lower() in title:
                        link = title_elem.get('href') or result.select_one('a').get('href')
                        if link:
                            if not link.startswith('http'):
                                link = f"{self.config['base_url']}{link}"
                            return link

            return None
        except Exception as e:
            logger.error(f"Error searching Running Warehouse: {e}")
            return None

    def scrape_reviews(self, product_url: str) -> List[RawReview]:
        """Scrape reviews from a Running Warehouse product page."""
        reviews = []
        page = 1
        max_pages = 50  # Safety limit

        while page <= max_pages:
            try:
                url = f"{product_url}/reviews" if page == 1 else f"{product_url}/reviews?page={page}"
                response = self.client.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'lxml')

                review_elements = soup.select('.review-item, .review-container, .bv-content-item')
                if not review_elements:
                    break

                for elem in review_elements:
                    review = self._parse_review_element(elem, product_url)
                    if review:
                        reviews.append(review)

                # Check for next page
                next_btn = soup.select_one('.pagination .next, .load-more')
                if not next_btn:
                    break

                page += 1

            except Exception as e:
                logger.error(f"Error scraping reviews page {page}: {e}")
                break

        return reviews

    def _parse_review_element(self, elem, source_url: str) -> Optional[RawReview]:
        """Parse a single review element."""
        try:
            # Extract basic info
            body = self._safe_text(elem, '.review-body, .review-text, .bv-content-summary-body')
            if not body:
                return None

            # Get review ID
            review_id = elem.get('data-review-id', '') or elem.get('id', '')

            # Parse rating (look for star rating)
            rating = None
            rating_elem = elem.select_one('.rating, .stars, .bv-rating')
            if rating_elem:
                rating_text = rating_elem.get('title', '') or rating_elem.get_text(strip=True)
                try:
                    rating = float(''.join(c for c in rating_text if c.isdigit() or c == '.'))
                except ValueError:
                    pass

            # Try to extract reviewer stats
            stats_elem = elem.select_one('.reviewer-info, .reviewer-stats, .bv-content-author-badges')
            width = None
            arch = None
            size = None

            if stats_elem:
                stats_text = stats_elem.get_text(strip=True).lower()
                if 'wide' in stats_text:
                    width = 'wide'
                elif 'narrow' in stats_text:
                    width = 'narrow'

                if 'high arch' in stats_text:
                    arch = 'high'
                elif 'flat' in stats_text or 'low arch' in stats_text:
                    arch = 'flat'

                # Extract size purchased
                size_match = elem.select_one('[data-size], .size-purchased')
                if size_match:
                    size = size_match.get_text(strip=True)

            return RawReview(
                source='running_warehouse',
                source_review_id=review_id,
                source_url=source_url,
                reviewer_name=self._safe_text(elem, '.reviewer-name, .author-name, .bv-author'),
                rating=rating,
                title=self._safe_text(elem, '.review-title, .bv-content-title'),
                body=body,
                review_date=self._safe_text(elem, '.review-date, .bv-content-datetime-stamp'),
                reviewer_foot_width=width,
                reviewer_arch_type=arch,
                reviewer_size_purchased=size,
            )

        except Exception as e:
            logger.error(f"Failed to parse review: {e}")
            return None


# Import additional scrapers (lazy imports to avoid circular dependencies)
def _get_scraper_class(name: str):
    """Lazy import scraper classes to avoid circular imports."""
    if name == 'DoctorsOfRunningScraper':
        from .doctors_of_running import DoctorsOfRunningScraper
        return DoctorsOfRunningScraper
    elif name == 'BelieveInTheRunScraper':
        from .believe_in_the_run import BelieveInTheRunScraper
        return BelieveInTheRunScraper
    elif name == 'WearTestersScraper':
        from .weartesters import WearTestersScraper
        return WearTestersScraper
    elif name == 'FleetFeetScraper':
        from .fleet_feet import FleetFeetScraper
        return FleetFeetScraper
    elif name == 'RoadRunnerSportsScraper':
        from .road_runner_sports import RoadRunnerSportsScraper
        return RoadRunnerSportsScraper
    return None


# Scraper configuration for different sources
SCRAPER_CONFIGS = {
    'running': {
        'running_warehouse': {
            'base_url': 'https://www.runningwarehouse.com',
            'scraper_class': RunningWarehouseScraper,
            'review_type': 'user',
        },
        'doctors_of_running': {
            'base_url': 'https://www.doctorsofrunning.com',
            'scraper_class_name': 'DoctorsOfRunningScraper',
            'review_type': 'expert',
        },
        'believe_in_the_run': {
            'base_url': 'https://believeintherun.com',
            'scraper_class_name': 'BelieveInTheRunScraper',
            'review_type': 'expert',
        },
        'fleet_feet': {
            'base_url': 'https://www.fleetfeet.com',
            'scraper_class_name': 'FleetFeetScraper',
            'review_type': 'user',
            'requires_browser': True,
        },
        'road_runner_sports': {
            'base_url': 'https://www.roadrunnersports.com',
            'scraper_class_name': 'RoadRunnerSportsScraper',
            'review_type': 'user',
            'requires_browser': True,
        },
    },
    'basketball': {
        'weartesters': {
            'base_url': 'https://weartesters.com',
            'scraper_class_name': 'WearTestersScraper',
            'review_type': 'expert',
            'requires_browser': True,
        },
    }
}


def get_scraper_for_source(source: str, category: str = 'running') -> Optional[BaseScraper]:
    """Factory function to get the appropriate scraper for a source."""
    category_config = SCRAPER_CONFIGS.get(category, {})
    source_config = category_config.get(source)

    if not source_config:
        logger.warning(f"No scraper configured for source: {source} in category: {category}")
        return None

    # Try direct class reference first
    scraper_class = source_config.get('scraper_class')

    # Fall back to lazy import via class name
    if not scraper_class:
        class_name = source_config.get('scraper_class_name')
        if class_name:
            scraper_class = _get_scraper_class(class_name)

    if not scraper_class:
        logger.warning(f"No scraper class for source: {source}")
        return None

    return scraper_class(source_config)


def get_default_sources(category: str) -> List[str]:
    """Get the default list of sources for a category."""
    return list(SCRAPER_CONFIGS.get(category, {}).keys())
