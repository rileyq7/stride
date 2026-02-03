"""
Nike.com product scraper for tech specs.

Site: https://www.nike.com
Uses Playwright for bot protection bypass.
Discovers ALL running shoes from Nike's catalog pages.
"""

import re
import logging
from typing import Optional, List, Set
from decimal import Decimal
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .base import ProductSpecs
from .playwright_base import PlaywrightBrandScraper

logger = logging.getLogger(__name__)


class NikeScraper(PlaywrightBrandScraper):
    """Scraper for Nike product specifications using Playwright."""

    BRAND_NAME = 'Nike'
    BASE_URL = 'https://www.nike.com'

    # Nike catalog pages to crawl for ALL shoes
    CATALOG_URLS = [
        # Men's Running
        'https://www.nike.com/w/mens-running-shoes-37v7jznik1zy7ok',
        # Women's Running
        'https://www.nike.com/w/womens-running-shoes-37v7jz5e1x6zy7ok',
        # Men's Basketball
        'https://www.nike.com/w/mens-basketball-shoes-3glsmznik1zy7ok',
        # Women's Basketball
        'https://www.nike.com/w/womens-basketball-shoes-3glsmz5e1x6zy7ok',
    ]

    async def discover_all_products(self) -> List[str]:
        """
        Crawl Nike's catalog pages to discover ALL product URLs.
        Handles pagination by scrolling to load more products.
        """
        all_urls: Set[str] = set()

        for catalog_url in self.CATALOG_URLS:
            logger.info(f"Crawling catalog: {catalog_url}")

            try:
                # Fetch catalog page with scrolling to load all products
                html = await self._fetch_catalog_with_scroll(catalog_url)
                if not html:
                    continue

                soup = BeautifulSoup(html, 'lxml')

                # Find all product links
                product_links = soup.select('a[href*="/t/"]')

                for link in product_links:
                    href = link.get('href', '')
                    if '/t/' in href and not '/customize/' in href:
                        # Normalize URL
                        if href.startswith('/'):
                            href = f"{self.BASE_URL}{href}"
                        # Remove query params
                        href = href.split('?')[0]
                        all_urls.add(href)

                logger.info(f"Found {len(all_urls)} unique products so far")

            except Exception as e:
                logger.error(f"Error crawling {catalog_url}: {e}")
                continue

        logger.info(f"Total unique Nike products discovered: {len(all_urls)}")
        return list(all_urls)

    async def _fetch_catalog_with_scroll(self, url: str) -> Optional[str]:
        """
        Fetch a catalog page and scroll to load all lazy-loaded products.
        Nike uses infinite scroll, so we need to scroll multiple times.
        """
        from playwright.async_api import async_playwright
        import asyncio

        await self.rate_limiter.wait()

        playwright = None
        browser = None
        context = None
        page = None
        content = None

        try:
            playwright = await async_playwright().start()
            # Use Firefox - more reliable on macOS
            browser = await playwright.firefox.launch(headless=True)

            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=self._get_random_user_agent(),
                locale='en-US',
                timezone_id='America/New_York',
            )

            # Add stealth scripts
            from .playwright_base import STEALTH_SCRIPT
            await context.add_init_script(STEALTH_SCRIPT)

            page = await context.new_page()

            logger.info(f"Loading catalog: {url}")

            # Navigate with longer timeout and wait for network idle
            try:
                await page.goto(url, wait_until='networkidle', timeout=90000)
            except Exception as nav_err:
                logger.warning(f"Navigation timeout/error, trying domcontentloaded: {nav_err}")
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                except Exception as nav_err2:
                    logger.error(f"Navigation failed completely: {nav_err2}")
                    return None

            await asyncio.sleep(5)  # Give Nike's JS more time to load

            # Dismiss popups
            await self._dismiss_popups(page)
            await asyncio.sleep(1)

            # Scroll to load more products (Nike uses infinite scroll)
            last_height = 0
            scroll_attempts = 0
            max_scrolls = 20  # Limit scrolling

            while scroll_attempts < max_scrolls:
                try:
                    # Scroll down
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await asyncio.sleep(2)

                    # Check if we've reached the end
                    new_height = await page.evaluate('document.body.scrollHeight')
                    if new_height == last_height:
                        # Try one more scroll to be sure
                        await asyncio.sleep(1)
                        new_height = await page.evaluate('document.body.scrollHeight')
                        if new_height == last_height:
                            break

                    last_height = new_height
                    scroll_attempts += 1
                    logger.debug(f"Scroll {scroll_attempts}: page height = {new_height}")
                except Exception as scroll_err:
                    logger.warning(f"Scroll error: {scroll_err}")
                    break

            content = await page.content()
            logger.info(f"Got {len(content)} characters from catalog")

        except Exception as e:
            logger.error(f"Error fetching catalog {url}: {e}")

        finally:
            # Close in reverse order with delays to avoid race conditions
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            await asyncio.sleep(0.1)
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            await asyncio.sleep(0.1)
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            await asyncio.sleep(0.1)
            if playwright:
                try:
                    await playwright.stop()
                except Exception:
                    pass

        return content

    async def get_product_url_async(self, shoe_name: str) -> Optional[str]:
        """Search Nike.com for a product."""
        search_query = shoe_name.replace(' ', '+')
        search_url = f"{self.BASE_URL}/w?q={search_query}"

        html = await self.fetch_page(search_url, wait_selector='[data-testid="product-card"]')
        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')

        # Find product cards
        product_cards = soup.select(
            '[data-testid="product-card"], '
            '.product-card, '
            '[class*="ProductCard"]'
        )

        for card in product_cards:
            link = card.select_one('a[href*="/t/"]')
            if not link:
                link = card.select_one('a[href]')

            if link:
                href = link.get('href', '')
                title = card.get_text(strip=True).lower()

                if self._matches_product(shoe_name, href, title):
                    if not href.startswith('http'):
                        href = f"{self.BASE_URL}{href}"
                    return href

        return None

    def _matches_product(self, shoe_name: str, href: str, title: str) -> bool:
        """Check if product matches search."""
        name_parts = shoe_name.lower().split()[:2]
        combined = f"{href.lower()} {title}"
        return all(part in combined for part in name_parts)

    async def scrape_product_specs_async(self, product_url: str) -> Optional[ProductSpecs]:
        """Scrape Nike product page for specs."""
        html = await self.fetch_page(product_url, wait_selector='h1')
        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')

        try:
            specs = ProductSpecs(brand=self.BRAND_NAME, name='')

            # Extract from JSON-LD first
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
                title_elem = soup.select_one('h1[data-testid="product-title"], h1')
                if title_elem:
                    specs.name = title_elem.get_text(strip=True)

            # Extract price if not found
            if not specs.msrp:
                # Try multiple price selectors
                price_selectors = [
                    '[data-testid="product-price"]',
                    '.product-price',
                    '[id*="price"]',
                    '[class*="product-price"]',
                    '[class*="Price"] span',
                ]
                for selector in price_selectors:
                    price_elem = soup.select_one(selector)
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        specs.msrp = self._parse_price(price_text)
                        if specs.msrp:
                            break

            # Extract images if not found
            if not specs.image_urls:
                specs.image_urls = self._extract_images(soup)
                if specs.image_urls and not specs.primary_image_url:
                    specs.primary_image_url = specs.image_urls[0]

            # Extract specifications from page
            self._extract_product_details(soup, html, specs)

            return specs

        except Exception as e:
            logger.error(f"Error scraping Nike product: {e}")
            return None

    def _extract_images(self, soup) -> List[str]:
        """Extract product images."""
        images = []

        img_elements = soup.select(
            '[data-testid="product-image"] img, '
            '.product-image img, '
            'img[src*="nike.com"]'
        )

        for img in img_elements:
            src = img.get('src') or img.get('data-src')
            if src and src not in images and 'nike' in src.lower():
                images.append(src)

        return images[:10]

    def _extract_product_details(self, soup, html: str, specs: ProductSpecs):
        """Extract specs from product details section."""
        full_text = soup.get_text(strip=True).lower()

        # Look for weight
        weight_patterns = [
            r'weight[:\s]*([\d.]+)\s*(?:oz|ounces)',
            r'approx\.\s*([\d.]+)\s*(?:oz|ounces)',
        ]
        for pattern in weight_patterns:
            match = re.search(pattern, full_text)
            if match:
                specs.weight_oz = Decimal(match.group(1))
                break

        # Look for drop/offset
        drop_patterns = [
            r'(?:drop|offset)[:\s]*([\d.]+)\s*mm',
            r'([\d.]+)\s*mm\s*(?:drop|offset)',
        ]
        for pattern in drop_patterns:
            match = re.search(pattern, full_text)
            if match:
                specs.drop_mm = Decimal(match.group(1))
                break

        # Detect terrain
        if 'trail' in full_text:
            specs.terrain = 'trail'
        elif 'track' in full_text or 'spike' in full_text:
            specs.terrain = 'track'
        else:
            specs.terrain = 'road'

        # Detect cushion type - Nike specific
        if 'zoomx' in full_text:
            specs.cushion_type = 'ZoomX'
            specs.cushion_level = 'max'
        elif 'react' in full_text:
            specs.cushion_type = 'React'
            specs.cushion_level = 'moderate'
        elif 'air zoom' in full_text or 'zoom air' in full_text:
            specs.cushion_type = 'Zoom Air'
            specs.cushion_level = 'moderate'
        elif 'air max' in full_text:
            specs.cushion_type = 'Air Max'
            specs.cushion_level = 'max'

        # Detect carbon plate
        if 'carbon' in full_text and ('plate' in full_text or 'fiber' in full_text):
            specs.has_carbon_plate = True

        # Detect category from shoe name
        name_lower = specs.name.lower() if specs.name else ''

        # Racing shoes
        if any(model in name_lower for model in ['alphafly', 'vaporfly', 'streakfly', 'dragonfly']):
            specs.subcategory = 'racing'
            specs.has_carbon_plate = True
        # Stability
        elif any(model in name_lower for model in ['structure', 'vomero']):
            specs.subcategory = 'stability' if 'structure' in name_lower else 'neutral'
        # Neutral
        elif any(model in name_lower for model in ['pegasus', 'invincible', 'infinity']):
            specs.subcategory = 'neutral'

        # Basketball shoes
        if any(model in name_lower for model in ['lebron', 'kd', 'giannis', 'ja', 'sabrina', 'gt']):
            specs.terrain = None  # Not applicable
            # Detect cut
            if 'low' in name_lower:
                specs.cut = 'low'
            elif 'mid' in name_lower:
                specs.cut = 'mid'
            else:
                specs.cut = 'high'  # Default for basketball
