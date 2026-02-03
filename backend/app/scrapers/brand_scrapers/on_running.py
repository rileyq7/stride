"""
On Running (On Cloud) product scraper for tech specs.

Site: https://www.on-running.com
Uses Playwright for bot protection bypass.
Discovers ALL running shoes from On's catalog pages.
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


class OnRunningScraper(PlaywrightBrandScraper):
    """Scraper for On Running product specifications using Playwright."""

    BRAND_NAME = 'On'
    BASE_URL = 'https://www.on-running.com'

    # On Running catalog pages for ALL running shoes
    CATALOG_URLS = [
        # Men's Road Running
        'https://www.on-running.com/en-us/collection/road',
        # Women's Road Running
        'https://www.on-running.com/en-us/collection/road?gender=women',
        # Men's Trail Running
        'https://www.on-running.com/en-us/collection/trail',
        # Women's Trail Running
        'https://www.on-running.com/en-us/collection/trail?gender=women',
        # All Men's Running Shoes
        'https://www.on-running.com/en-us/collection/running-shoes?gender=men',
        # All Women's Running Shoes
        'https://www.on-running.com/en-us/collection/running-shoes?gender=women',
    ]

    async def discover_all_products(self) -> List[str]:
        """Crawl On Running catalog pages to discover ALL product URLs."""
        all_urls: Set[str] = set()

        for catalog_url in self.CATALOG_URLS:
            logger.info(f"Crawling catalog: {catalog_url}")

            try:
                html = await self._fetch_catalog_with_scroll(catalog_url)
                if not html:
                    continue

                soup = BeautifulSoup(html, 'lxml')

                # Find all product links
                product_links = soup.select('a[href*="/products/"]')

                for link in product_links:
                    href = link.get('href', '')
                    if '/products/' in href and 'onetrust' not in href.lower():
                        if href.startswith('/'):
                            href = f"{self.BASE_URL}{href}"
                        href = href.split('?')[0]
                        all_urls.add(href)

                logger.info(f"Found {len(all_urls)} unique products so far")

            except Exception as e:
                logger.error(f"Error crawling {catalog_url}: {e}")
                continue

        logger.info(f"Total unique On Running products discovered: {len(all_urls)}")
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
        """Find the product URL for On Running shoes via search."""
        search_query = shoe_name.replace(' ', '+')
        search_url = f"{self.BASE_URL}/en-us/search?q={search_query}"

        html = await self.fetch_page(search_url, wait_selector='a[href*="/products/"]')
        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')

        # Find product links
        product_links = soup.select('a[href*="/products/"]')

        for link in product_links:
            href = link.get('href', '')
            if '/products/' in href and 'onetrust' not in href.lower():
                if not href.startswith('http'):
                    href = f"{self.BASE_URL}{href}"
                if self._matches_product(shoe_name, href, link.get_text().lower()):
                    return href

        return None

    def _matches_product(self, shoe_name: str, href: str, title: str) -> bool:
        name_parts = shoe_name.lower().replace('on ', '').split()[:2]
        combined = f"{href.lower()} {title}"
        return all(part in combined for part in name_parts)

    async def scrape_product_specs_async(self, product_url: str) -> Optional[ProductSpecs]:
        """Scrape On Running product page for specs."""
        html = await self.fetch_page(product_url, wait_selector='h1')
        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')

        try:
            specs = ProductSpecs(brand=self.BRAND_NAME, name='')

            # Try JSON-LD first
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

            # Extract name from page if not in JSON-LD
            if not specs.name:
                title_elem = soup.select_one('h1')
                if title_elem:
                    specs.name = title_elem.get_text(strip=True)

            # Extract name from URL if still missing or generic
            if not specs.name or specs.name.lower() in ['shop all', 'on running']:
                match = re.search(r'/products/([^/?]+)', product_url)
                if match:
                    slug = match.group(1)
                    specs.name = slug.replace('-', ' ').title()

            # Extract price if not found
            if not specs.msrp:
                price_selectors = [
                    '[data-testid="price"]',
                    '[class*="price"]',
                    '.product-price',
                ]
                for selector in price_selectors:
                    price_elem = soup.select_one(selector)
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        specs.msrp = self._parse_price(price_text)
                        if specs.msrp:
                            break

            # If still no price, search in page text
            if not specs.msrp:
                price_match = re.search(r'\$(\d+(?:\.\d{2})?)', html)
                if price_match:
                    specs.msrp = Decimal(price_match.group(1))

            self._extract_product_details(soup, html, specs)
            self._detect_category(specs)

            return specs

        except Exception as e:
            logger.error(f"Error scraping On Running product: {e}")
            return None

    def _extract_product_details(self, soup, html: str, specs: ProductSpecs):
        full_text = soup.get_text(strip=True).lower()

        weight_match = re.search(r'weight[:\s]*([\d.]+)\s*(?:oz|ounces|g)', full_text)
        if weight_match:
            weight_val = Decimal(weight_match.group(1))
            if 'g' in full_text[weight_match.end():weight_match.end()+5]:
                specs.weight_g = weight_val
                specs.weight_oz = round(weight_val / Decimal('28.35'), 1)
            else:
                specs.weight_oz = weight_val

        drop_match = re.search(r'(?:drop|offset)[:\s]*([\d.]+)\s*mm', full_text)
        if drop_match:
            specs.drop_mm = Decimal(drop_match.group(1))

        # On uses CloudTec cushioning
        if 'cloudtec' in full_text:
            specs.cushion_type = 'CloudTec'
        if 'helion' in full_text:
            specs.cushion_type = 'Helion'
            specs.cushion_level = 'max'

        if 'speedboard' in full_text:
            specs.has_rocker = True

        if 'carbon' in full_text and 'plate' in full_text:
            specs.has_carbon_plate = True

        if 'trail' in full_text:
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

    def _detect_category(self, specs: ProductSpecs):
        name_lower = (specs.name or '').lower()

        # On model detection
        if any(model in name_lower for model in ['cloudmonster', 'cloudstratus', 'cloudsurfer']):
            specs.subcategory = 'neutral'
            specs.cushion_level = 'max'
        elif any(model in name_lower for model in ['cloudboom', 'cloudflash']):
            specs.subcategory = 'racing'
            specs.has_carbon_plate = True
        elif any(model in name_lower for model in ['cloud 5', 'cloud x', 'cloudflow']):
            specs.subcategory = 'neutral'
            specs.cushion_level = 'moderate'
        elif 'cloudventure' in name_lower or 'cloudultra' in name_lower or 'cloudvista' in name_lower:
            specs.terrain = 'trail'

        # Default terrain
        if not specs.terrain:
            specs.terrain = 'road'

        # Default cushion
        if not specs.cushion_type:
            specs.cushion_type = 'CloudTec'
        if not specs.cushion_level:
            specs.cushion_level = 'moderate'
