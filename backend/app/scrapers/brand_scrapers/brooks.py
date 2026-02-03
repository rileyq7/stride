"""
Brooks Running product scraper for tech specs.

Site: https://www.brooksrunning.com
Uses Playwright for bot protection bypass.
Discovers ALL running shoes from Brooks catalog pages.
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


class BrooksScraper(PlaywrightBrandScraper):
    """Scraper for Brooks Running product specifications using Playwright."""

    BRAND_NAME = 'Brooks'
    BASE_URL = 'https://www.brooksrunning.com'

    # Brooks catalog pages for ALL running shoes
    CATALOG_URLS = [
        # Men's Road Running
        'https://www.brooksrunning.com/en_us/mens-running-shoes/',
        # Women's Road Running
        'https://www.brooksrunning.com/en_us/womens-running-shoes/',
        # Men's Trail Running
        'https://www.brooksrunning.com/en_us/mens-trail-running-shoes/',
        # Women's Trail Running
        'https://www.brooksrunning.com/en_us/womens-trail-running-shoes/',
    ]

    async def discover_all_products(self) -> List[str]:
        """Crawl Brooks catalog pages to discover ALL product URLs."""
        all_urls: Set[str] = set()

        for catalog_url in self.CATALOG_URLS:
            logger.info(f"Crawling catalog: {catalog_url}")

            try:
                html = await self._fetch_catalog_with_scroll(catalog_url)
                if not html:
                    continue

                soup = BeautifulSoup(html, 'lxml')

                # Find all product links
                product_links = soup.select('.product-tile a[href], a[href*="/product/"], a[href*="/running-shoes/"]')

                for link in product_links:
                    href = link.get('href', '')
                    # Filter to product pages only
                    if '/product/' in href or (href.count('/') >= 4 and 'shoes' in href):
                        if href.startswith('/'):
                            href = f"{self.BASE_URL}{href}"
                        href = href.split('?')[0]
                        all_urls.add(href)

                logger.info(f"Found {len(all_urls)} unique products so far")

            except Exception as e:
                logger.error(f"Error crawling {catalog_url}: {e}")
                continue

        logger.info(f"Total unique Brooks products discovered: {len(all_urls)}")
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
        """Find the product URL for Brooks shoes."""
        name_lower = shoe_name.lower().strip()
        name_lower = name_lower.replace('brooks ', '')

        # Try search
        search_query = shoe_name.replace(' ', '+')
        search_url = f"{self.BASE_URL}/en_us/search?q={search_query}"

        html = await self.fetch_page(search_url, wait_selector='.product-tile')
        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')

        product_tiles = soup.select('.product-tile, .product-card, [data-product-id]')

        for tile in product_tiles:
            link = tile.select_one('a[href]')
            if link:
                href = link.get('href', '')
                title = tile.get_text(strip=True).lower()

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
        """Scrape Brooks product page for specs."""
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
                title_elem = soup.select_one('h1.product-name, h1')
                if title_elem:
                    specs.name = title_elem.get_text(strip=True)

            if not specs.msrp:
                price_elem = soup.select_one('.price-sales, .product-price')
                if price_elem:
                    specs.msrp = self._parse_price(price_elem.get_text())

            if not specs.image_urls:
                specs.image_urls = self._extract_images(soup)
                if specs.image_urls:
                    specs.primary_image_url = specs.image_urls[0]

            self._extract_product_details(soup, html, specs)
            self._detect_category(specs)

            return specs

        except Exception as e:
            logger.error(f"Error scraping Brooks product: {e}")
            return None

    def _extract_images(self, soup) -> List[str]:
        images = []

        img_elements = soup.select(
            '.product-image img, '
            '.primary-image img, '
            'img[src*="brooks"]'
        )

        for img in img_elements:
            src = img.get('src') or img.get('data-src')
            if src and src not in images:
                images.append(src)

        return images[:10]

    def _extract_product_details(self, soup, html: str, specs: ProductSpecs):
        full_text = soup.get_text(strip=True).lower()

        weight_match = re.search(r'weight[:\s]*([\d.]+)\s*(?:oz|ounces)', full_text)
        if weight_match:
            specs.weight_oz = Decimal(weight_match.group(1))

        heel_match = re.search(r'heel[:\s]*([\d.]+)\s*mm', full_text)
        if heel_match:
            specs.stack_height_heel_mm = Decimal(heel_match.group(1))

        forefoot_match = re.search(r'forefoot[:\s]*([\d.]+)\s*mm', full_text)
        if forefoot_match:
            specs.stack_height_forefoot_mm = Decimal(forefoot_match.group(1))

        drop_match = re.search(r'(?:drop|offset)[:\s]*([\d.]+)\s*mm', full_text)
        if drop_match:
            specs.drop_mm = Decimal(drop_match.group(1))

        if 'dna loft' in full_text:
            specs.cushion_type = 'DNA Loft'
            specs.cushion_level = 'max'
        elif 'dna flash' in full_text:
            specs.cushion_type = 'DNA Flash'
            specs.cushion_level = 'moderate'
        elif 'dna amp' in full_text:
            specs.cushion_type = 'DNA Amp'
            specs.cushion_level = 'moderate'

        if 'guiderails' in full_text:
            specs.subcategory = 'stability'

        if 'carbon' in full_text and 'plate' in full_text:
            specs.has_carbon_plate = True

        if 'trail' in full_text:
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

    def _detect_category(self, specs: ProductSpecs):
        name_lower = specs.name.lower() if specs.name else ''

        if any(model in name_lower for model in ['catamount', 'cascadia', 'caldera']):
            specs.terrain = 'trail'
        else:
            specs.terrain = 'road'

        if any(model in name_lower for model in ['adrenaline', 'beast', 'ariel', 'addiction']):
            specs.subcategory = 'stability'
        elif any(model in name_lower for model in ['ghost', 'glycerin', 'launch', 'revel']):
            specs.subcategory = 'neutral'
        elif any(model in name_lower for model in ['hyperion']):
            specs.subcategory = 'racing'
            if 'elite' in name_lower or 'max' in name_lower:
                specs.has_carbon_plate = True
