"""
Base class for brand website product scrapers.

Extracts official tech specs (weight, stack height, drop, etc.) from brand sites.
"""

import re
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup

from ..utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


@dataclass
class ProductSpecs:
    """Standardized product specifications scraped from brand sites."""
    # Identifiers
    brand: str
    name: str
    style_id: Optional[str] = None
    colorway: Optional[str] = None

    # Pricing
    msrp: Optional[Decimal] = None
    current_price: Optional[Decimal] = None

    # Physical specs (running)
    weight_oz: Optional[Decimal] = None
    weight_g: Optional[Decimal] = None
    stack_height_heel_mm: Optional[Decimal] = None
    stack_height_forefoot_mm: Optional[Decimal] = None
    drop_mm: Optional[Decimal] = None

    # Running features
    cushion_type: Optional[str] = None
    cushion_level: Optional[str] = None
    has_carbon_plate: bool = False
    has_rocker: bool = False
    terrain: Optional[str] = None  # road, trail, track
    subcategory: Optional[str] = None  # neutral, stability, etc.

    # Basketball features
    cut: Optional[str] = None  # low, mid, high
    traction_pattern: Optional[str] = None
    ankle_support_level: Optional[str] = None

    # Media
    primary_image_url: Optional[str] = None
    image_urls: List[str] = field(default_factory=list)

    # Availability
    width_options: List[str] = field(default_factory=list)
    available_sizes: List[str] = field(default_factory=list)

    # Raw data for debugging
    raw_specs: Dict[str, Any] = field(default_factory=dict)

    def to_running_attributes(self) -> Dict[str, Any]:
        """Convert to RunningShoeAttributes format."""
        return {
            'weight_oz': self.weight_oz,
            'stack_height_heel_mm': self.stack_height_heel_mm,
            'stack_height_forefoot_mm': self.stack_height_forefoot_mm,
            'drop_mm': self.drop_mm,
            'cushion_type': self.cushion_type,
            'cushion_level': self.cushion_level,
            'has_carbon_plate': self.has_carbon_plate,
            'has_rocker': self.has_rocker,
            'terrain': self.terrain or 'road',
            'subcategory': self.subcategory,
        }

    def to_basketball_attributes(self) -> Dict[str, Any]:
        """Convert to BasketballShoeAttributes format."""
        return {
            'weight_oz': self.weight_oz,
            'cut': self.cut,
            'cushion_type': self.cushion_type,
            'cushion_level': self.cushion_level,
            'traction_pattern': self.traction_pattern,
            'ankle_support_level': self.ankle_support_level,
        }

    def to_shoe_data(self) -> Dict[str, Any]:
        """Convert to Shoe model format."""
        return {
            'msrp_usd': self.msrp,
            'current_price_min': self.current_price,
            'current_price_max': self.current_price,
            'primary_image_url': self.primary_image_url,
            'image_urls': self.image_urls,
            'width_options': self.width_options,
        }


class BaseBrandScraper(ABC):
    """Base class for brand website scrapers."""

    BRAND_NAME: str = ''
    BASE_URL: str = ''

    def __init__(self):
        self.client = httpx.Client(
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            },
            timeout=30.0,
            follow_redirects=True,
        )
        self.rate_limiter = RateLimiter(self.BRAND_NAME.lower().replace(' ', '_'))

    def __del__(self):
        try:
            self.client.close()
        except Exception:
            pass

    @abstractmethod
    def get_product_url(self, shoe_name: str) -> Optional[str]:
        """Find the product page URL for a shoe."""
        pass

    @abstractmethod
    def scrape_product_specs(self, product_url: str) -> Optional[ProductSpecs]:
        """Scrape specifications from a product page."""
        pass

    def scrape_shoe(self, shoe_name: str) -> Optional[ProductSpecs]:
        """Main entry point: find product and scrape specs."""
        url = self.get_product_url(shoe_name)
        if not url:
            logger.warning(f"Could not find {shoe_name} on {self.BRAND_NAME}")
            return None
        return self.scrape_product_specs(url)

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a page and return parsed BeautifulSoup."""
        self.rate_limiter.wait_sync()

        try:
            response = self.client.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'lxml')
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _parse_price(self, text: str) -> Optional[Decimal]:
        """Parse a price string to Decimal."""
        if not text:
            return None
        match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', text)
        if match:
            price_str = match.group(1).replace(',', '')
            try:
                return Decimal(price_str)
            except Exception:
                pass
        return None

    def _parse_weight(self, text: str) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """Parse weight text, return (oz, grams)."""
        if not text:
            return None, None

        oz_match = re.search(r'([\d.]+)\s*(?:oz|ounces?)', text, re.IGNORECASE)
        g_match = re.search(r'([\d.]+)\s*(?:g|grams?)', text, re.IGNORECASE)

        weight_oz = Decimal(oz_match.group(1)) if oz_match else None
        weight_g = Decimal(g_match.group(1)) if g_match else None

        # Convert if we only have one
        if weight_g and not weight_oz:
            weight_oz = round(weight_g / Decimal('28.35'), 1)
        elif weight_oz and not weight_g:
            weight_g = round(weight_oz * Decimal('28.35'), 0)

        return weight_oz, weight_g

    def _parse_measurement_mm(self, text: str) -> Optional[Decimal]:
        """Parse a measurement in mm."""
        if not text:
            return None
        match = re.search(r'([\d.]+)\s*mm', text, re.IGNORECASE)
        if match:
            try:
                return Decimal(match.group(1))
            except Exception:
                pass
        return None

    def _safe_text(self, element, selector: str) -> Optional[str]:
        """Safely extract text from a selector."""
        if element is None:
            return None
        found = element.select_one(selector)
        return found.get_text(strip=True) if found else None
