#!/usr/bin/env python
"""
Industrial-grade sitemap-based product URL discovery.

Features:
- Gzip support (.xml.gz)
- Retry with exponential backoff
- ETag/If-Modified-Since caching
- URL canonicalization (strip query params, normalize slashes)
- Provenance logging (discovered_from, discovered_at, lastmod)
- Plugin-style brand configs with URL classifiers

Usage:
    python sitemap_scraper.py              # Discover URLs for all brands
    python sitemap_scraper.py nike brooks  # Discover URLs for specific brands
    python sitemap_scraper.py --scrape     # Discover + scrape product pages
    python sitemap_scraper.py --report     # Show coverage report only
"""

import sys
import re
import gzip
import json
import time
import hashlib
import requests
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from typing import Optional, List, Set, Dict, Callable, Any
from decimal import Decimal
from dataclasses import dataclass, field
from datetime import datetime, UTC
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bs4 import BeautifulSoup
from sqlalchemy import select, text

from app.core.database import sync_session_maker
from app.models import Brand, Category, Shoe, RunningShoeAttributes, ShoeFitProfile


# ============================================================================
# CONSTANTS
# ============================================================================

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# Cache directory for ETags and sitemap data
CACHE_DIR = Path(__file__).parent / ".sitemap_cache"
CACHE_DIR.mkdir(exist_ok=True)

# Default rate limits (requests per minute)
DEFAULT_RATE_LIMIT = 30
DEFAULT_DELAY = 0.5


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class DiscoveredURL:
    """A URL discovered from a sitemap with provenance."""
    url: str
    canonical_url: str
    discovered_from: str
    discovered_at: datetime
    lastmod: Optional[datetime] = None
    changefreq: Optional[str] = None
    priority: Optional[float] = None


@dataclass
class ProductSpecs:
    """Product specifications extracted from a page."""
    brand: str
    name: str = ''
    msrp: Optional[Decimal] = None
    style_id: Optional[str] = None
    primary_image_url: Optional[str] = None
    image_urls: Optional[List[str]] = field(default_factory=list)
    weight_oz: Optional[Decimal] = None
    drop_mm: Optional[Decimal] = None
    stack_height_heel_mm: Optional[Decimal] = None
    stack_height_forefoot_mm: Optional[Decimal] = None
    terrain: Optional[str] = None
    cushion_type: Optional[str] = None
    cushion_level: Optional[str] = None
    subcategory: Optional[str] = None
    has_carbon_plate: bool = False
    has_rocker: bool = False


@dataclass
class BrandConfig:
    """Configuration for a brand's sitemap discovery."""
    slug: str
    name: str
    sitemap_urls: List[str]  # Can be index or direct sitemaps

    # URL classification
    product_url_patterns: List[str] = field(default_factory=list)  # Allowlist
    non_product_patterns: List[str] = field(default_factory=list)  # Blocklist
    running_patterns: List[str] = field(default_factory=list)  # Category filter

    # Sitemap filtering
    sitemap_patterns: List[str] = field(default_factory=list)  # Which sitemaps to use

    # Rate limiting
    rate_limit: int = DEFAULT_RATE_LIMIT
    delay: float = DEFAULT_DELAY

    # Status
    blocked: bool = False
    notes: str = ''


# ============================================================================
# URL UTILITIES
# ============================================================================

def canonicalize_url(url: str, strip_params: bool = True) -> str:
    """
    Canonicalize a URL:
    - Strip query params (dwvar_, color=, etc.)
    - Normalize trailing slashes
    - Lowercase the path
    """
    parsed = urlparse(url)

    # Lowercase hostname
    netloc = parsed.netloc.lower()

    # Normalize path - strip trailing slash unless root
    path = parsed.path
    if path != '/' and path.endswith('/'):
        path = path.rstrip('/')

    # Optionally strip query params
    query = ''
    if not strip_params and parsed.query:
        # Keep only essential params, remove tracking/variant params
        params = parse_qs(parsed.query)
        keep_params = {k: v for k, v in params.items()
                      if not k.startswith('dwvar_')
                      and k not in ['utm_source', 'utm_medium', 'utm_campaign', 'ref', 'color']}
        if keep_params:
            query = urlencode(keep_params, doseq=True)

    return urlunparse((parsed.scheme, netloc, path, '', query, ''))


def get_cache_key(url: str) -> str:
    """Generate a cache key for a URL."""
    return hashlib.md5(url.encode()).hexdigest()


# ============================================================================
# HTTP UTILITIES WITH RETRY & CACHING
# ============================================================================

class SitemapFetcher:
    """Fetches sitemaps with retry, caching, and gzip support."""

    def __init__(self, rate_limit: int = DEFAULT_RATE_LIMIT, delay: float = DEFAULT_DELAY):
        self.rate_limit = rate_limit
        self.delay = delay
        self.last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; ShoeMatchBot/1.0; +https://shoematch.com/bot)",
            "Accept": "application/xml, text/xml, */*",
            "Accept-Encoding": "gzip, deflate",
        })

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request_time = time.time()

    def _get_cached_etag(self, url: str) -> Optional[str]:
        """Get cached ETag for a URL."""
        cache_file = CACHE_DIR / f"{get_cache_key(url)}.etag"
        if cache_file.exists():
            return cache_file.read_text().strip()
        return None

    def _save_etag(self, url: str, etag: str):
        """Save ETag for a URL."""
        cache_file = CACHE_DIR / f"{get_cache_key(url)}.etag"
        cache_file.write_text(etag)

    def fetch(self, url: str, max_retries: int = 3) -> Optional[str]:
        """
        Fetch a URL with retry and gzip support.
        Returns the text content or None on failure.
        """
        self._rate_limit()

        headers = {}
        etag = self._get_cached_etag(url)
        if etag:
            headers['If-None-Match'] = etag

        for attempt in range(max_retries):
            try:
                print(f"    Fetching: {url}" + (f" (attempt {attempt+1})" if attempt > 0 else ""))

                response = self.session.get(url, timeout=30, headers=headers)

                # Handle 304 Not Modified
                if response.status_code == 304:
                    print(f"    Not modified (cached)")
                    # Load from cache
                    cache_file = CACHE_DIR / f"{get_cache_key(url)}.xml"
                    if cache_file.exists():
                        return cache_file.read_text()
                    return None

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    print(f"    Rate limited, waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue

                # Handle server errors with backoff
                if response.status_code >= 500:
                    wait = (2 ** attempt) * 2
                    print(f"    Server error {response.status_code}, waiting {wait}s...")
                    time.sleep(wait)
                    continue

                response.raise_for_status()

                # Save ETag if present
                if 'ETag' in response.headers:
                    self._save_etag(url, response.headers['ETag'])

                # Handle gzip content
                content = response.content
                if url.endswith('.gz') or response.headers.get('Content-Encoding') == 'gzip':
                    try:
                        content = gzip.decompress(content)
                    except gzip.BadGzipFile:
                        pass  # Not actually gzipped

                text = content.decode('utf-8')

                # Cache the content
                cache_file = CACHE_DIR / f"{get_cache_key(url)}.xml"
                cache_file.write_text(text)

                return text

            except requests.exceptions.Timeout:
                print(f"    Timeout, retrying...")
                time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                print(f"    ERROR: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None

        return None


# ============================================================================
# SITEMAP PARSING
# ============================================================================

def parse_sitemap_index(xml_text: str) -> List[str]:
    """Parse a sitemap index and return list of sitemap URLs."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"    XML parse error: {e}")
        return []

    sitemaps = []
    # Try with namespace
    for sitemap in root.findall(".//sm:sitemap/sm:loc", SITEMAP_NS):
        if sitemap.text:
            sitemaps.append(sitemap.text.strip())

    # Try without namespace (some sites don't use it)
    if not sitemaps:
        for sitemap in root.findall(".//sitemap/loc"):
            if sitemap.text:
                sitemaps.append(sitemap.text.strip())

    return sitemaps


def parse_sitemap_urls(xml_text: str, source_url: str) -> List[DiscoveredURL]:
    """Parse a sitemap and return list of discovered URLs with metadata."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"    XML parse error: {e}")
        return []

    discovered = []
    now = datetime.now(UTC)

    # Try with namespace
    url_elements = root.findall(".//sm:url", SITEMAP_NS)

    # Try without namespace
    if not url_elements:
        url_elements = root.findall(".//url")

    for url_elem in url_elements:
        # Get location
        loc = url_elem.find("sm:loc", SITEMAP_NS)
        if loc is None:
            loc = url_elem.find("loc")
        if loc is None or not loc.text:
            continue

        url = loc.text.strip()

        # Get lastmod
        lastmod = None
        lastmod_elem = url_elem.find("sm:lastmod", SITEMAP_NS)
        if lastmod_elem is None:
            lastmod_elem = url_elem.find("lastmod")
        if lastmod_elem is not None and lastmod_elem.text:
            try:
                # Handle various date formats
                text = lastmod_elem.text.strip()
                if 'T' in text:
                    lastmod = datetime.fromisoformat(text.replace('Z', '+00:00'))
                else:
                    lastmod = datetime.strptime(text[:10], '%Y-%m-%d').replace(tzinfo=UTC)
            except ValueError:
                pass

        # Get changefreq
        changefreq = None
        cf_elem = url_elem.find("sm:changefreq", SITEMAP_NS)
        if cf_elem is None:
            cf_elem = url_elem.find("changefreq")
        if cf_elem is not None and cf_elem.text:
            changefreq = cf_elem.text.strip()

        # Get priority
        priority = None
        pri_elem = url_elem.find("sm:priority", SITEMAP_NS)
        if pri_elem is None:
            pri_elem = url_elem.find("priority")
        if pri_elem is not None and pri_elem.text:
            try:
                priority = float(pri_elem.text.strip())
            except ValueError:
                pass

        discovered.append(DiscoveredURL(
            url=url,
            canonical_url=canonicalize_url(url),
            discovered_from=source_url,
            discovered_at=now,
            lastmod=lastmod,
            changefreq=changefreq,
            priority=priority,
        ))

    return discovered


# ============================================================================
# URL CLASSIFIERS
# ============================================================================

def classify_url(url: str, config: BrandConfig) -> Dict[str, Any]:
    """
    Classify a URL as product/non-product using brand config.
    Returns dict with 'is_product', 'is_running', 'blocked_by' keys.
    """
    result = {
        'is_product': False,
        'is_running': False,
        'blocked_by': None,
        'matched_by': None,
    }

    # Check blocklist first
    for pattern in config.non_product_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            result['blocked_by'] = pattern
            return result

    # Check allowlist
    for pattern in config.product_url_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            result['is_product'] = True
            result['matched_by'] = pattern
            break

    # Check running patterns
    if result['is_product'] and config.running_patterns:
        for pattern in config.running_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                result['is_running'] = True
                break

    return result


# Common non-product URL patterns (shared blocklist)
COMMON_NON_PRODUCT_PATTERNS = [
    r'/help/',
    r'/faq/',
    r'/contact/',
    r'/about/',
    r'/stores?/',
    r'/store-locator/',
    r'/blog/',
    r'/news/',
    r'/search',
    r'/cart',
    r'/checkout',
    r'/account',
    r'/login',
    r'/register',
    r'/wishlist',
    r'/privacy',
    r'/terms',
    r'/returns',
    r'/shipping',
    r'/size-guide',
    r'/gift-card',
    r'/careers',
    r'/press',
    r'/sustainability',
    r'/newsletter',
    r'\?.*dwvar_',  # Variant URLs
    r'\?.*color=',
    r'/collections?/',  # Category pages, not PDPs
    r'/categories/',
]


# ============================================================================
# BRAND CONFIGURATIONS
# ============================================================================

BRAND_CONFIGS: Dict[str, BrandConfig] = {
    'nike': BrandConfig(
        slug='nike',
        name='Nike',
        sitemap_urls=['https://www.nike.com/sitemap-v2-pdp-index.xml'],
        sitemap_patterns=['en-us'],  # Only US English sitemap
        product_url_patterns=[
            r'nike\.com/t/',  # All Nike PDPs use /t/ path
        ],
        non_product_patterns=COMMON_NON_PRODUCT_PATTERNS + [
            r'-apparel-',
            r'-clothing-',
            r'-shorts-',
            r'-pants-',
            r'-jacket-',
            r'-top-',
            r'-shirt-',
            r'-bra-',
            r'-socks?-',
            r'-bag-',
            r'-cap-',
            r'-hat-',
            r'-headband-',
            r'-gloves?-',
            r'-equipment-',
        ],
        running_patterns=[
            r'running-shoes',
            r'road-running-shoes',
            r'trail-running-shoes',
            r'racing-shoes',
            r'pegasus',
            r'vaporfly',
            r'alphafly',
            r'invincible',
            r'vomero',
            r'structure',
            r'zoom-fly',
            r'streakfly',
            r'wildhorse',
            r'zegama',
            r'ultrafly',
            r'infinity',
            r'winflo',
        ],
    ),

    'on': BrandConfig(
        slug='on',
        name='On',
        sitemap_urls=['https://www.on-running.com/en-us/sitemap.xml'],
        sitemap_patterns=['product'],
        product_url_patterns=[
            r'/products/',
        ],
        non_product_patterns=COMMON_NON_PRODUCT_PATTERNS + [
            r'/apparel/',
            r'/accessories/',
        ],
        running_patterns=[
            r'cloud',
            r'running',
        ],
    ),

    'brooks': BrandConfig(
        slug='brooks',
        name='Brooks',
        sitemap_urls=['https://www.brooksrunning.com/sitemap_index.xml'],
        sitemap_patterns=['product'],
        product_url_patterns=[
            r'/en_us/[^/]+/[^/]+/',
        ],
        non_product_patterns=COMMON_NON_PRODUCT_PATTERNS + [
            r'/apparel/',
            r'/gear/',
            r'/socks/',
        ],
        running_patterns=[
            r'running',
            r'ghost',
            r'glycerin',
            r'adrenaline',
            r'launch',
            r'hyperion',
            r'cascadia',
            r'catamount',
        ],
    ),

    'saucony': BrandConfig(
        slug='saucony',
        name='Saucony',
        sitemap_urls=['https://www.saucony.com/sitemap_0.xml'],
        sitemap_patterns=[],  # Direct sitemap
        product_url_patterns=[
            r'saucony\.com/en/.*\.html$',
        ],
        non_product_patterns=COMMON_NON_PRODUCT_PATTERNS + [
            r'/apparel/',
            r'/accessories/',
            r'-sock',
            r'-bag',
            r'-hat',
            r'-jacket',
            r'-short',
            r'-tight',
            r'-pant',
            r'-shirt',
            r'-bra',
            r'kids?/',
            r'baby',
            r'jazz',  # Lifestyle shoes
            r'shadow',  # Lifestyle shoes
        ],
        running_patterns=[
            r'ride',
            r'triumph',
            r'kinvara',
            r'endorphin',
            r'guide',
            r'hurricane',
            r'peregrine',
            r'xodus',
            r'tempus',
            r'freedom',
        ],
    ),

    'asics': BrandConfig(
        slug='asics',
        name='ASICS',
        sitemap_urls=[
            'https://www.asics.com/us/en-us/sitemap_index.xml',
            'https://www.asics.com/sitemap_0.xml',
        ],
        sitemap_patterns=[],  # Try all sitemaps
        product_url_patterns=[
            r'asics\.com/us/en-us/.*\.html$',
            r'/p/',  # Product pages
        ],
        non_product_patterns=COMMON_NON_PRODUCT_PATTERNS + [
            r'/apparel/',
            r'/accessories/',
            r'/kids/',
            r'/tiger/',  # ASICS Tiger lifestyle
        ],
        running_patterns=[
            r'running',
            r'trail',
            r'gel-',
            r'nimbus',
            r'kayano',
            r'novablast',
            r'gt-\d',
            r'cumulus',
            r'trabuco',
            r'fuji',
            r'metaspeed',
            r'magic-speed',
            r'superblast',
        ],
        notes='Sitemap structure may require exploration',
    ),

    'hoka': BrandConfig(
        slug='hoka',
        name='Hoka',
        sitemap_urls=['https://www.hoka.com/en/us/sitemap_index.xml'],
        sitemap_patterns=['product'],
        product_url_patterns=[
            r'/en/us/[^/]+/[^/]+\.html$',
        ],
        non_product_patterns=COMMON_NON_PRODUCT_PATTERNS,
        running_patterns=[
            r'running',
            r'trail',
            r'road',
            r'race',
        ],
        blocked=True,
        notes='403 Forbidden - uses DataDome bot protection',
    ),

    'new-balance': BrandConfig(
        slug='new-balance',
        name='New Balance',
        sitemap_urls=['https://www.newbalance.com/sitemap_index.xml'],
        sitemap_patterns=['product', 'pdp'],
        product_url_patterns=[
            r'/pd/',
            r'/product/',
        ],
        non_product_patterns=COMMON_NON_PRODUCT_PATTERNS,
        running_patterns=[
            r'running',
            r'fresh-foam',
            r'fuelcell',
            r'1080',
            r'880',
            r'860',
            r'840',
        ],
        blocked=True,
        notes='Access denied - uses Akamai bot protection',
    ),

    'adidas': BrandConfig(
        slug='adidas',
        name='Adidas',
        sitemap_urls=['https://www.adidas.com/us/sitemap_index.xml'],
        sitemap_patterns=['product'],
        product_url_patterns=[
            r'/us/[A-Z0-9]+\.html$',
        ],
        non_product_patterns=COMMON_NON_PRODUCT_PATTERNS,
        running_patterns=[
            r'running',
            r'ultraboost',
            r'adizero',
            r'supernova',
            r'solarglide',
            r'solarboost',
        ],
        blocked=True,
        notes='Access denied',
    ),

    'altra': BrandConfig(
        slug='altra',
        name='Altra',
        sitemap_urls=['https://www.altrarunning.com/sitemap.xml'],
        sitemap_patterns=['product'],
        product_url_patterns=[
            r'/shop/[^/]+/[^/]+/',
        ],
        non_product_patterns=COMMON_NON_PRODUCT_PATTERNS,
        running_patterns=[
            r'running',
            r'trail',
            r'road',
        ],
        blocked=True,
        notes='Bot protection blocks sitemap access',
    ),

    'mizuno': BrandConfig(
        slug='mizuno',
        name='Mizuno',
        sitemap_urls=['https://www.mizunousa.com/sitemap.xml'],
        sitemap_patterns=['product'],
        product_url_patterns=[
            r'/product/',
        ],
        non_product_patterns=COMMON_NON_PRODUCT_PATTERNS,
        running_patterns=[
            r'running',
            r'wave-',
        ],
        blocked=True,
        notes='No accessible sitemap found',
    ),
}


# ============================================================================
# DISCOVERY ENGINE
# ============================================================================

class SitemapDiscovery:
    """Discovers product URLs from brand sitemaps."""

    def __init__(self):
        self.fetcher = SitemapFetcher()

    def discover_brand(self, config: BrandConfig) -> List[DiscoveredURL]:
        """Discover all product URLs for a brand."""
        print(f"\n{'='*60}")
        print(f"Discovering products for: {config.name}")
        print(f"{'='*60}")

        if config.blocked:
            print(f"\n  WARNING: {config.name} is known to block access.")
            if config.notes:
                print(f"  Notes: {config.notes}")
            print(f"  Attempting anyway...")

        all_discovered: List[DiscoveredURL] = []
        seen_urls: Set[str] = set()

        for sitemap_url in config.sitemap_urls:
            print(f"\n  Processing: {sitemap_url}")

            xml_text = self.fetcher.fetch(sitemap_url)
            if not xml_text:
                continue

            # Check if this is a sitemap index
            if '<sitemapindex' in xml_text:
                sitemaps = parse_sitemap_index(xml_text)
                print(f"  Found sitemap index with {len(sitemaps)} sitemaps")

                # Filter sitemaps if patterns specified
                if config.sitemap_patterns:
                    filtered = []
                    for sm in sitemaps:
                        for pattern in config.sitemap_patterns:
                            if pattern.lower() in sm.lower():
                                filtered.append(sm)
                                break
                    sitemaps = filtered
                    print(f"  Filtered to {len(sitemaps)} matching sitemaps")

                # Fetch each sitemap
                for sm_url in sitemaps:
                    sm_xml = self.fetcher.fetch(sm_url)
                    if sm_xml:
                        urls = parse_sitemap_urls(sm_xml, sm_url)
                        for u in urls:
                            if u.canonical_url not in seen_urls:
                                seen_urls.add(u.canonical_url)
                                all_discovered.append(u)
                        print(f"    {sm_url}: {len(urls)} URLs")
            else:
                # Direct sitemap
                urls = parse_sitemap_urls(xml_text, sitemap_url)
                for u in urls:
                    if u.canonical_url not in seen_urls:
                        seen_urls.add(u.canonical_url)
                        all_discovered.append(u)
                print(f"  Found {len(urls)} URLs in sitemap")

        print(f"\n  Total unique URLs: {len(all_discovered)}")

        # Classify URLs
        products = []
        running = []
        blocked_count = 0

        for discovered in all_discovered:
            classification = classify_url(discovered.canonical_url, config)
            if classification['blocked_by']:
                blocked_count += 1
            elif classification['is_product']:
                products.append(discovered)
                if classification['is_running']:
                    running.append(discovered)

        print(f"  Product URLs: {len(products)}")
        print(f"  Running shoe URLs: {len(running)}")
        print(f"  Blocked (non-product): {blocked_count}")

        # Return running shoes if patterns specified, otherwise all products
        return running if config.running_patterns else products

    def discover_all(self, brand_keys: Optional[List[str]] = None) -> Dict[str, List[DiscoveredURL]]:
        """Discover products for multiple brands."""
        if brand_keys is None:
            brand_keys = list(BRAND_CONFIGS.keys())

        results = {}
        for key in brand_keys:
            if key not in BRAND_CONFIGS:
                print(f"\nUnknown brand: {key}")
                continue

            config = BRAND_CONFIGS[key]
            results[key] = self.discover_brand(config)

        return results


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def save_discovered_urls(brand_slug: str, discovered: List[DiscoveredURL], scrape: bool = False):
    """Save discovered URLs to database."""
    print(f"\n{'='*60}")
    print(f"Saving to database: {brand_slug}")
    print(f"{'='*60}")

    with sync_session_maker() as session:
        # Get brand
        result = session.execute(select(Brand).where(Brand.slug == brand_slug))
        brand = result.scalar_one_or_none()
        if not brand:
            print(f"  ERROR: Brand '{brand_slug}' not found!")
            return 0

        # Get running category
        result = session.execute(select(Category).where(Category.slug == 'running'))
        running_cat = result.scalar_one_or_none()
        if not running_cat:
            print(f"  ERROR: Running category not found!")
            return 0

        added = 0
        skipped = 0
        errors = 0

        for i, disc in enumerate(discovered):
            # Create a slug from canonical URL
            url_slug = urlparse(disc.canonical_url).path.strip('/').replace('/', '-').lower()
            if len(url_slug) > 100:
                url_slug = url_slug[:100]

            # Check if exists
            existing = session.execute(
                select(Shoe).where(Shoe.brand_id == brand.id, Shoe.slug == url_slug)
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            # Optionally scrape the page for details
            specs = None
            if scrape:
                print(f"  [{i+1}/{len(discovered)}] Scraping: {disc.url[:60]}...", end=" ")
                time.sleep(1)
                specs = scrape_product_page(disc.url, brand.name)

            if specs and specs.name:
                name = specs.name
                slug = specs.name.lower().replace(' ', '-').replace("'", "").replace('"', '')[:100]
            else:
                name = f"[URL] {url_slug}"
                slug = url_slug

            try:
                shoe = Shoe(
                    brand_id=brand.id,
                    category_id=running_cat.id,
                    name=name,
                    slug=slug,
                    msrp_usd=specs.msrp if specs else None,
                    primary_image_url=specs.primary_image_url if specs else None,
                    is_active=True,
                    needs_review=True,
                    last_scraped_at=datetime.now(UTC),
                )
                session.add(shoe)
                session.flush()

                # Create running attributes
                attrs = RunningShoeAttributes(
                    shoe_id=shoe.id,
                    terrain=specs.terrain if specs else 'road',
                    subcategory=specs.subcategory if specs else None,
                )
                session.add(attrs)

                # Create fit profile placeholder
                fit = ShoeFitProfile(
                    shoe_id=shoe.id,
                    size_runs='true_to_size',
                    needs_review=True,
                )
                session.add(fit)

                if scrape:
                    print(f"ADDED: {name[:40]}")
                added += 1

                if added % 20 == 0:
                    session.commit()
                    if not scrape:
                        print(f"  Progress: {added} added, {skipped} skipped")

            except Exception as e:
                print(f"  ERROR: {e}")
                errors += 1

        session.commit()

        print(f"\n  Summary:")
        print(f"    Added: {added}")
        print(f"    Skipped (existing): {skipped}")
        print(f"    Errors: {errors}")

        return added


def scrape_product_page(url: str, brand_name: str) -> Optional[ProductSpecs]:
    """Try to scrape a product page using simple HTTP requests."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        r = requests.get(url, timeout=30, headers=headers)
        if r.status_code != 200:
            return None

        html = r.text
        soup = BeautifulSoup(html, 'lxml')
        specs = ProductSpecs(brand=brand_name)

        # Try JSON-LD extraction
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    specs.name = data.get('name', '')
                    specs.style_id = data.get('sku')
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        price = offers.get('price')
                        if price:
                            specs.msrp = Decimal(str(price))
                    image = data.get('image')
                    if isinstance(image, str):
                        specs.primary_image_url = image
                    elif isinstance(image, list) and image:
                        specs.primary_image_url = image[0]
                    break
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Product':
                            specs.name = item.get('name', '')
                            specs.style_id = item.get('sku')
                            break
            except json.JSONDecodeError:
                continue

        # Fallback to H1
        if not specs.name:
            h1 = soup.find('h1')
            if h1:
                specs.name = h1.get_text(strip=True)

        # Basic terrain detection
        full_text = soup.get_text().lower()
        if 'trail' in full_text:
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

        return specs if specs.name else None

    except Exception as e:
        print(f"    Error scraping {url}: {e}")
        return None


def print_coverage_report():
    """Print a coverage report of shoes in the database."""
    print("\n" + "=" * 70)
    print("COVERAGE REPORT")
    print("=" * 70)

    with sync_session_maker() as session:
        # Count by brand
        result = session.execute(text('''
            SELECT b.name, b.slug, COUNT(s.id) as count,
                   SUM(CASE WHEN s.name LIKE '[URL]%%' THEN 1 ELSE 0 END) as url_only,
                   SUM(CASE WHEN s.msrp_usd IS NOT NULL THEN 1 ELSE 0 END) as has_price
            FROM shoes s
            JOIN brands b ON s.brand_id = b.id
            GROUP BY b.name, b.slug
            ORDER BY count DESC
        '''))

        print("\nShoes by Brand:")
        print("-" * 60)
        total = 0
        total_url_only = 0
        total_has_price = 0
        for row in result:
            name, slug, count, url_only, has_price = row
            config = BRAND_CONFIGS.get(slug)
            status = "blocked" if config and config.blocked else "accessible"
            print(f"  {name:15} {count:5} shoes  ({url_only} URL-only, {has_price} with price) [{status}]")
            total += count
            total_url_only += url_only or 0
            total_has_price += has_price or 0

        print("-" * 60)
        print(f"  {'TOTAL':15} {total:5} shoes  ({total_url_only} URL-only, {total_has_price} with price)")

        # Count by terrain
        result = session.execute(text('''
            SELECT rsa.terrain, COUNT(*) as count
            FROM running_shoe_attributes rsa
            GROUP BY rsa.terrain
            ORDER BY count DESC
        '''))

        print("\nBy Terrain:")
        for row in result:
            print(f"  {row[0] or 'unknown':15} {row[1]:5}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    args = sys.argv[1:]

    # Check for flags
    scrape = '--scrape' in args
    report_only = '--report' in args
    args = [a for a in args if not a.startswith('--')]

    # Report only mode
    if report_only:
        print_coverage_report()
        return

    # Determine brands to process
    brands_to_process = args if args else [k for k, v in BRAND_CONFIGS.items() if not v.blocked]

    print("=" * 70)
    print("SITEMAP-BASED PRODUCT DISCOVERY (v2)")
    print("=" * 70)
    print(f"Brands: {', '.join(brands_to_process)}")
    print(f"Scrape pages: {scrape}")
    print(f"Cache dir: {CACHE_DIR}")

    # Discover products
    discovery = SitemapDiscovery()
    results = discovery.discover_all(brands_to_process)

    # Save to database
    total_found = 0
    total_added = 0

    for brand_key, discovered in results.items():
        total_found += len(discovered)
        if discovered:
            config = BRAND_CONFIGS[brand_key]
            added = save_discovered_urls(config.slug, discovered, scrape=scrape)
            total_added += added

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    for brand_key, discovered in results.items():
        print(f"  {brand_key}: {len(discovered)} found")
    print(f"\nTOTAL: {total_found} found, {total_added} added to database")

    # Print coverage report
    print_coverage_report()


if __name__ == '__main__':
    main()
