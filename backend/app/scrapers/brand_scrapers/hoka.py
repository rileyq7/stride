"""
Hoka.com product scraper for tech specs.

Site: https://www.hoka.com
Uses Playwright with search-based product discovery.
Discovers ALL running shoes from Hoka's catalog pages.
"""

import re
import asyncio
import logging
from typing import Optional, List, Set
from decimal import Decimal
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus

from .base import ProductSpecs
from .playwright_base import PlaywrightBrandScraper

logger = logging.getLogger(__name__)


class HokaScraper(PlaywrightBrandScraper):
    """Scraper for Hoka product specifications using Playwright."""

    BRAND_NAME = 'Hoka'
    BASE_URL = 'https://www.hoka.com'
    SEARCH_URL = 'https://www.hoka.com/en/us/search?q={query}'

    # Hoka catalog pages for ALL running shoes
    CATALOG_URLS = [
        # Men's Road Running
        'https://www.hoka.com/en/us/mens-road',
        # Women's Road Running
        'https://www.hoka.com/en/us/womens-road',
        # Men's Trail Running
        'https://www.hoka.com/en/us/mens-trail',
        # Women's Trail Running
        'https://www.hoka.com/en/us/womens-trail',
        # Men's All Shoes
        'https://www.hoka.com/en/us/mens-shoes',
        # Women's All Shoes
        'https://www.hoka.com/en/us/womens-shoes',
    ]

    async def discover_all_products(self) -> List[str]:
        """
        Crawl Hoka's catalog pages to discover ALL product URLs.
        """
        all_urls: Set[str] = set()

        for catalog_url in self.CATALOG_URLS:
            logger.info(f"Crawling catalog: {catalog_url}")

            try:
                html = await self._fetch_catalog_with_scroll(catalog_url)
                if not html:
                    continue

                soup = BeautifulSoup(html, 'lxml')

                # Find all product links
                product_links = soup.select('a[href*="/product/"], a[href*="/mens-"], a[href*="/womens-"]')

                for link in product_links:
                    href = link.get('href', '')
                    # Filter to only product pages (not category pages)
                    if '/product/' in href or (('/mens-' in href or '/womens-' in href) and href.count('/') >= 5):
                        if href.startswith('/'):
                            href = f"{self.BASE_URL}{href}"
                        # Remove query params and color codes
                        href = href.split('?')[0]
                        all_urls.add(href)

                logger.info(f"Found {len(all_urls)} unique products so far")

            except Exception as e:
                logger.error(f"Error crawling {catalog_url}: {e}")
                continue

        logger.info(f"Total unique Hoka products discovered: {len(all_urls)}")
        return list(all_urls)

    async def _fetch_catalog_with_scroll(self, url: str) -> Optional[str]:
        """Fetch a catalog page with scrolling to load all products."""
        from playwright.async_api import async_playwright

        await self.rate_limiter.wait()

        playwright = None
        browser = None
        context = None
        page = None

        try:
            playwright = await async_playwright().start()
            browser = await playwright.firefox.launch(headless=True)

            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=self._get_random_user_agent(),
            )

            from .playwright_base import STEALTH_SCRIPT
            await context.add_init_script(STEALTH_SCRIPT)

            page = await context.new_page()

            logger.info(f"Loading catalog: {url}")
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)

            await self._dismiss_popups(page)

            # Scroll to load all products
            last_height = 0
            scroll_attempts = 0
            max_scrolls = 15

            while scroll_attempts < max_scrolls:
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(2)

                new_height = await page.evaluate('document.body.scrollHeight')
                if new_height == last_height:
                    break

                last_height = new_height
                scroll_attempts += 1

            return await page.content()

        except Exception as e:
            logger.error(f"Error fetching catalog {url}: {e}")
            return None

        finally:
            for obj in [page, context, browser]:
                if obj:
                    try:
                        await obj.close()
                    except Exception:
                        pass
            if playwright:
                try:
                    await playwright.stop()
                except Exception:
                    pass

    async def get_product_url_async(self, shoe_name: str) -> Optional[str]:
        """Find the product URL for Hoka shoes via search."""
        name_lower = shoe_name.lower().strip()
        name_lower = name_lower.replace('hoka ', '')

        # Try search-based discovery
        search_html = await self.search_and_find_product(shoe_name, self.SEARCH_URL)
        if search_html:
            soup = BeautifulSoup(search_html, 'lxml')

            # Look for product links in search results
            product_links = soup.select('a[href*="/product/"], a[href*="/mens-"], a[href*="/womens-"]')
            for link in product_links:
                href = link.get('href', '')
                title = link.get_text(strip=True).lower()

                # Check if this matches our shoe
                if self._matches_product(shoe_name, href, title):
                    full_url = urljoin(self.BASE_URL, href)
                    logger.info(f"Found product URL: {full_url}")
                    return full_url

        # Fallback: Try direct URL patterns
        slug = self._create_slug(shoe_name)
        direct_patterns = [
            f"{self.BASE_URL}/en/us/mens-road/{slug}/",
            f"{self.BASE_URL}/en/us/womens-road/{slug}/",
            f"{self.BASE_URL}/en/us/mens-trail/{slug}/",
            f"{self.BASE_URL}/en/us/womens-trail/{slug}/",
            f"{self.BASE_URL}/en/us/product/{slug}/",
        ]

        for url in direct_patterns:
            html = await self.fetch_page(url)
            if html and len(html) > 5000:
                soup = BeautifulSoup(html, 'lxml')
                h1 = soup.select_one('h1')
                if h1 and self._matches_product(shoe_name, '', h1.get_text().lower()):
                    logger.info(f"Found via direct URL: {url}")
                    return url

        logger.warning(f"Could not find Hoka {shoe_name}")
        return None

    def _create_slug(self, shoe_name: str) -> str:
        """Create URL slug from shoe name."""
        slug = shoe_name.lower().replace(' ', '-')
        return re.sub(r'[^a-z0-9-]', '', slug)

    def _matches_product(self, shoe_name: str, href: str, title: str) -> bool:
        """Check if product matches search."""
        name_parts = shoe_name.lower().split()[:2]
        combined = f"{href.lower()} {title}"
        return all(part in combined for part in name_parts)

    async def scrape_product_specs_async(self, product_url: str) -> Optional[ProductSpecs]:
        """Scrape Hoka product page for specs."""
        html = await self.fetch_page(product_url, wait_selector='h1')
        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')

        try:
            specs = ProductSpecs(brand=self.BRAND_NAME, name='')

            # Extract from JSON-LD first (most reliable)
            json_ld = self._extract_json_ld(html)
            if json_ld:
                specs.name = json_ld.get('name', '')
                specs.style_id = json_ld.get('sku')

                offers = json_ld.get('offers', {})
                if isinstance(offers, dict):
                    specs.msrp = self._parse_price(str(offers.get('price', '')))
                elif isinstance(offers, list) and offers:
                    specs.msrp = self._parse_price(str(offers[0].get('price', '')))

                image = json_ld.get('image')
                if isinstance(image, str):
                    specs.primary_image_url = image
                elif isinstance(image, list) and image:
                    specs.primary_image_url = image[0]
                    specs.image_urls = image[:10]

            # Extract product name from page if not in JSON-LD
            if not specs.name:
                title_elem = soup.select_one('h1, [data-testid="product-title"]')
                if title_elem:
                    specs.name = title_elem.get_text(strip=True)

            # Extract price if not found
            if not specs.msrp:
                price_selectors = [
                    '[data-testid="price"]',
                    '.product-price',
                    '.price',
                    '[class*="price"]',
                    'span:has-text("$")',
                ]
                for sel in price_selectors:
                    price_elem = soup.select_one(sel)
                    if price_elem:
                        specs.msrp = self._parse_price(price_elem.get_text())
                        if specs.msrp:
                            break

            # Extract images if not found
            if not specs.image_urls:
                specs.image_urls = self._extract_images(soup)
                if specs.image_urls and not specs.primary_image_url:
                    specs.primary_image_url = specs.image_urls[0]

            # Extract specifications from page
            self._extract_product_details(soup, html, specs)

            # Hoka-specific defaults
            if not specs.cushion_level:
                specs.cushion_level = 'max'
            if not specs.terrain:
                specs.terrain = 'road'
            specs.has_rocker = True  # Most Hokas have Meta-Rocker

            if specs.name:
                logger.info(f"Scraped: {specs.name} - ${specs.msrp or '?'}")
                return specs
            return None

        except Exception as e:
            logger.error(f"Error scraping Hoka product: {e}")
            return None

    def _extract_images(self, soup) -> List[str]:
        """Extract product images."""
        images = []

        img_elements = soup.select(
            '[data-testid="product-image"] img, '
            '.product-image img, '
            '.gallery img, '
            'img[src*="hoka"], '
            'img[data-src*="hoka"]'
        )

        for img in img_elements:
            src = img.get('src') or img.get('data-src')
            if src and src not in images:
                if 'hoka' in src.lower() or 'cdn' in src.lower():
                    src = re.sub(r'\?.*$', '', src)
                    if src.startswith('//'):
                        src = 'https:' + src
                    images.append(src)

        return images[:10]

    def _extract_product_details(self, soup, html: str, specs: ProductSpecs):
        """Extract specs from product details section."""
        full_text = soup.get_text(' ', strip=True).lower()

        # Look for weight
        weight_patterns = [
            r'weight[:\s]*([\d.]+)\s*(?:oz|ounces)',
            r'([\d.]+)\s*(?:oz|ounces?).*weight',
            r'weight.*?([\d.]+)\s*(?:oz|ounces?)',
            r'mens?.*?([\d.]+)\s*oz',
        ]
        for pattern in weight_patterns:
            match = re.search(pattern, full_text)
            if match:
                try:
                    specs.weight_oz = Decimal(match.group(1))
                    break
                except Exception:
                    pass

        # Look for stack heights
        heel_patterns = [
            r'heel[:\s]*([\d.]+)\s*mm',
            r'heel.*?([\d.]+)\s*mm',
            r'stack.*?heel[:\s]*([\d.]+)',
        ]
        for pattern in heel_patterns:
            match = re.search(pattern, full_text)
            if match:
                try:
                    specs.stack_height_heel_mm = Decimal(match.group(1))
                    break
                except Exception:
                    pass

        forefoot_patterns = [
            r'forefoot[:\s]*([\d.]+)\s*mm',
            r'forefoot.*?([\d.]+)\s*mm',
            r'stack.*?forefoot[:\s]*([\d.]+)',
        ]
        for pattern in forefoot_patterns:
            match = re.search(pattern, full_text)
            if match:
                try:
                    specs.stack_height_forefoot_mm = Decimal(match.group(1))
                    break
                except Exception:
                    pass

        # Look for drop/offset
        drop_patterns = [
            r'drop[:\s]*([\d.]+)\s*mm',
            r'offset[:\s]*([\d.]+)\s*mm',
            r'([\d.]+)\s*mm\s*(?:drop|offset)',
            r'heel.to.toe.*?([\d.]+)\s*mm',
        ]
        for pattern in drop_patterns:
            match = re.search(pattern, full_text)
            if match:
                try:
                    specs.drop_mm = Decimal(match.group(1))
                    break
                except Exception:
                    pass

        # Calculate drop if we have stack heights
        if specs.stack_height_heel_mm and specs.stack_height_forefoot_mm and not specs.drop_mm:
            specs.drop_mm = specs.stack_height_heel_mm - specs.stack_height_forefoot_mm

        # Detect terrain
        if 'trail' in full_text:
            specs.terrain = 'trail'
        elif 'road' in full_text:
            specs.terrain = 'road'

        # Detect carbon plate
        if 'carbon' in full_text and ('plate' in full_text or 'fiber' in full_text):
            specs.has_carbon_plate = True

        # Detect cushion type
        if 'peba' in full_text:
            specs.cushion_type = 'PEBA'
        elif 'eva' in full_text:
            specs.cushion_type = 'EVA'

        # Detect category from shoe name
        name_lower = specs.name.lower() if specs.name else ''
        if any(model in name_lower for model in ['speedgoat', 'challenger', 'torrent', 'tecton', 'zinal']):
            specs.terrain = 'trail'
        if any(model in name_lower for model in ['rocket', 'cielo', 'mach x']):
            specs.subcategory = 'racing'
            specs.has_carbon_plate = True
        elif any(model in name_lower for model in ['bondi', 'clifton', 'mach', 'rincon', 'kawana']):
            specs.subcategory = 'neutral'
        elif any(model in name_lower for model in ['arahi', 'gaviota']):
            specs.subcategory = 'stability'
