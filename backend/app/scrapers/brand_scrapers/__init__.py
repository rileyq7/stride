"""
Brand website scrapers for extracting official product specs.

These scrapers pull authoritative technical specifications directly from
brand websites like Nike, Adidas, Hoka, Brooks, etc.
"""

from .nike import NikeScraper
from .hoka import HokaScraper
from .brooks import BrooksScraper
from .adidas import AdidasScraper
from .new_balance import NewBalanceScraper
from .asics import AsicsScraper
from .saucony import SauconyScraper
from .on_running import OnRunningScraper
from .altra import AltraScraper
from .mizuno import MizunoScraper

__all__ = [
    'NikeScraper',
    'HokaScraper',
    'BrooksScraper',
    'AdidasScraper',
    'NewBalanceScraper',
    'AsicsScraper',
    'SauconyScraper',
    'OnRunningScraper',
    'AltraScraper',
    'MizunoScraper',
]

# Brand to scraper mapping (supports both slug and name formats)
BRAND_SCRAPERS = {
    'nike': NikeScraper,
    'hoka': HokaScraper,
    'brooks': BrooksScraper,
    'adidas': AdidasScraper,
    'new balance': NewBalanceScraper,
    'new-balance': NewBalanceScraper,
    'asics': AsicsScraper,
    'saucony': SauconyScraper,
    'on': OnRunningScraper,
    'on running': OnRunningScraper,
    'on-running': OnRunningScraper,
    'on cloud': OnRunningScraper,
    'altra': AltraScraper,
    'mizuno': MizunoScraper,
}


def get_brand_scraper(brand_name: str):
    """Get the appropriate scraper for a brand."""
    brand_lower = brand_name.lower().strip()
    scraper_class = BRAND_SCRAPERS.get(brand_lower)
    if scraper_class:
        return scraper_class()
    return None
