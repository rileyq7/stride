from app.scrapers.base import (
    BaseScraper,
    RawReview,
    SCRAPER_CONFIGS,
    get_scraper_for_source,
    get_default_sources,
)
from app.scrapers.ai_parser import ReviewFitExtractor

# Review scrapers
from app.scrapers.doctors_of_running import DoctorsOfRunningScraper
from app.scrapers.believe_in_the_run import BelieveInTheRunScraper
from app.scrapers.weartesters import WearTestersScraper
from app.scrapers.fleet_feet import FleetFeetScraper
from app.scrapers.road_runner_sports import RoadRunnerSportsScraper
from app.scrapers.playwright_base import PlaywrightBaseScraper

# Brand scrapers for tech specs
from app.scrapers.brand_scrapers import (
    get_brand_scraper,
    BRAND_SCRAPERS,
    NikeScraper,
    HokaScraper,
    BrooksScraper,
    AdidasScraper,
    NewBalanceScraper,
    AsicsScraper,
    SauconyScraper,
    OnRunningScraper,
    AltraScraper,
    MizunoScraper,
)
from app.scrapers.brand_scrapers.base import BaseBrandScraper, ProductSpecs

__all__ = [
    # Base classes and utilities
    "BaseScraper",
    "RawReview",
    "SCRAPER_CONFIGS",
    "get_scraper_for_source",
    "get_default_sources",
    "ReviewFitExtractor",
    "PlaywrightBaseScraper",

    # Review scrapers
    "DoctorsOfRunningScraper",
    "BelieveInTheRunScraper",
    "WearTestersScraper",
    "FleetFeetScraper",
    "RoadRunnerSportsScraper",

    # Brand scrapers
    "BaseBrandScraper",
    "ProductSpecs",
    "get_brand_scraper",
    "BRAND_SCRAPERS",
    "NikeScraper",
    "HokaScraper",
    "BrooksScraper",
    "AdidasScraper",
    "NewBalanceScraper",
    "AsicsScraper",
    "SauconyScraper",
    "OnRunningScraper",
    "AltraScraper",
    "MizunoScraper",
]
