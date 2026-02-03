"""
Adidas.com product scraper for tech specs.

Site: https://www.adidas.com
Uses Playwright for bot protection bypass.
Discovers ALL running/basketball shoes from Adidas catalog pages.
"""

import re
import asyncio
import logging
from typing import Optional, List, Set
from decimal import Decimal
from bs4 import BeautifulSoup

from .base import ProductSpecs
from .playwright_base import PlaywrightBrandScraper

logger = logging.getLogger(__name__)


class AdidasScraper(PlaywrightBrandScraper):
    """Scraper for Adidas product specifications using Playwright."""

    BRAND_NAME = 'Adidas'
    BASE_URL = 'https://www.adidas.com'

    # Adidas catalog pages for running and basketball shoes
    CATALOG_URLS = [
        # Men's Running
        'https://www.adidas.com/us/men-running-shoes',
        # Women's Running
        'https://www.adidas.com/us/women-running-shoes',
        # Men's Basketball
        'https://www.adidas.com/us/men-basketball-shoes',
        # Women's Basketball
        'https://www.adidas.com/us/women-basketball-shoes',
    ]

    async def discover_all_products(self) -> List[str]:
        """Crawl Adidas catalog pages to discover ALL product URLs."""
        all_urls: Set[str] = set()

        for catalog_url in self.CATALOG_URLS:
            logger.info(f"Crawling catalog: {catalog_url}")

            try:
                html = await self._fetch_catalog_with_scroll(catalog_url)
                if not html:
                    continue

                soup = BeautifulSoup(html, 'lxml')

                # Find all product links
                product_links = soup.select('[data-testid="product-card"] a[href], .gl-product-card a[href], a[href*="/products/"]')

                for link in product_links:
                    href = link.get('href', '')
                    if '/products/' in href or (href.startswith('/') and len(href) > 20):
                        if href.startswith('/'):
                            href = f"{self.BASE_URL}{href}"
                        href = href.split('?')[0]
                        all_urls.add(href)

                logger.info(f"Found {len(all_urls)} unique products so far")

            except Exception as e:
                logger.error(f"Error crawling {catalog_url}: {e}")
                continue

        logger.info(f"Total unique Adidas products discovered: {len(all_urls)}")
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
            max_scrolls = 20

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
        """Search Adidas for a product."""
        name_lower = shoe_name.lower().strip()
        name_lower = name_lower.replace('adidas ', '')

        search_query = shoe_name.replace(' ', '%20')
        search_url = f"{self.BASE_URL}/us/search?q={search_query}"

        html = await self.fetch_page(search_url, wait_selector='[data-testid="product-card"]')
        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')

        product_cards = soup.select(
            '[data-testid="product-card"], '
            '.product-card, '
            '.gl-product-card'
        )

        for card in product_cards:
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
        name_parts = shoe_name.lower().split()[:2]
        combined = f"{href.lower()} {title}"
        return all(part in combined for part in name_parts)

    async def scrape_product_specs_async(self, product_url: str) -> Optional[ProductSpecs]:
        """Scrape Adidas product page for specs."""
        html = await self.fetch_page(product_url, wait_selector='h1')
        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')

        try:
            specs = ProductSpecs(brand=self.BRAND_NAME, name='')

            json_ld = self._extract_json_ld(html)
            if json_ld:
                specs.name = json_ld.get('name', '')
                specs.style_id = json_ld.get('sku')
                offers = json_ld.get('offers', {})
                if isinstance(offers, dict):
                    specs.msrp = self._parse_price(str(offers.get('price', '')))
                image = json_ld.get('image')
                if isinstance(image, str):
                    specs.primary_image_url = image

            if not specs.name:
                title_elem = soup.select_one('h1[data-testid="product-title"], h1')
                if title_elem:
                    specs.name = title_elem.get_text(strip=True)

            if not specs.msrp:
                price_elem = soup.select_one('[data-testid="product-price"], .gl-price')
                if price_elem:
                    specs.msrp = self._parse_price(price_elem.get_text())

            self._extract_product_details(soup, html, specs)

            return specs

        except Exception as e:
            logger.error(f"Error scraping Adidas product: {e}")
            return None

    def _extract_product_details(self, soup, html: str, specs: ProductSpecs):
        full_text = soup.get_text(strip=True).lower()

        # Weight
        weight_match = re.search(r'weight[:\s]*([\d.]+)\s*(?:oz|ounces)', full_text)
        if weight_match:
            specs.weight_oz = Decimal(weight_match.group(1))

        # Drop
        drop_match = re.search(r'(?:drop|offset)[:\s]*([\d.]+)\s*mm', full_text)
        if drop_match:
            specs.drop_mm = Decimal(drop_match.group(1))

        # Cushion
        if 'lightstrike pro' in full_text:
            specs.cushion_type = 'Lightstrike Pro'
            specs.cushion_level = 'max'
        elif 'lightstrike' in full_text:
            specs.cushion_type = 'Lightstrike'
            specs.cushion_level = 'moderate'
        elif 'boost' in full_text:
            specs.cushion_type = 'Boost'
            specs.cushion_level = 'max'

        # Carbon
        if 'energyrods' in full_text or 'carbon' in full_text:
            specs.has_carbon_plate = True

        # Terrain
        if 'trail' in full_text or 'terrex' in (specs.name or '').lower():
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

        # Category
        name_lower = (specs.name or '').lower()
        if 'adizero' in name_lower:
            specs.subcategory = 'racing'
        elif 'supernova' in name_lower or 'solar' in name_lower:
            specs.subcategory = 'neutral'
