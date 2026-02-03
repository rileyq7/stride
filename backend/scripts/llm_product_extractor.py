#!/usr/bin/env python
"""
LLM-assisted product data extraction using Ollama with Granite4.

This module provides structured extraction of shoe product data from
raw HTML using a local LLM. Optimized for brand sites (Nike, Brooks, Hoka, etc.)
"""

import json
import re
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from decimal import Decimal


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "granite4:1b-h"  # Best balance of speed (4s) and quality (79%)


@dataclass
class ExtractedProduct:
    """Structured product data extracted by LLM."""
    brand: str = ""
    model_name: str = ""  # e.g., "Pegasus 41" without brand
    full_name: str = ""   # e.g., "Nike Pegasus 41"
    price_usd: Optional[float] = None
    msrp_usd: Optional[float] = None
    colorway: Optional[str] = None
    gender: Optional[str] = None  # mens, womens, unisex
    terrain: Optional[str] = None  # road, trail, track
    category: Optional[str] = None  # daily_trainer, racing, stability, etc.
    weight_oz: Optional[float] = None
    drop_mm: Optional[float] = None
    stack_height_heel_mm: Optional[float] = None
    stack_height_forefoot_mm: Optional[float] = None
    cushion_type: Optional[str] = None
    has_carbon_plate: bool = False
    style_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def clean_html_for_llm(html: str, max_chars: int = 12000, url: str = "") -> str:
    """
    Extract ALL relevant product content from HTML for LLM processing.
    Optimized for brand sites (Nike, Brooks, Hoka, ASICS, etc.)
    """
    from bs4 import BeautifulSoup

    # Remove script and style tags
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

    soup = BeautifulSoup(html, 'lxml')
    relevant_text = []

    # 1. Page title
    if soup.title:
        relevant_text.append(f"TITLE: {soup.title.string}")

    # 2. H1 product name
    h1 = soup.find('h1')
    if h1:
        relevant_text.append(f"PRODUCT NAME: {h1.get_text(strip=True)}")

    # 3. Meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        relevant_text.append(f"META DESCRIPTION: {meta_desc['content']}")

    # 4. JSON-LD structured data (MOST VALUABLE - brands put good data here)
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            # Handle array of items
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('@type') == 'Product':
                        data = item
                        break
            if isinstance(data, dict) and data.get('@type') == 'Product':
                # Extract key fields
                relevant_text.append("JSON-LD PRODUCT DATA:")
                if data.get('name'):
                    relevant_text.append(f"  name: {data['name']}")
                if data.get('brand'):
                    brand = data['brand']
                    if isinstance(brand, dict):
                        relevant_text.append(f"  brand: {brand.get('name', brand)}")
                    else:
                        relevant_text.append(f"  brand: {brand}")
                if data.get('sku'):
                    relevant_text.append(f"  sku: {data['sku']}")
                if data.get('color'):
                    relevant_text.append(f"  color: {data['color']}")
                if data.get('offers'):
                    offers = data['offers']
                    if isinstance(offers, dict):
                        if offers.get('price'):
                            relevant_text.append(f"  price: {offers['price']}")
                    elif isinstance(offers, list) and offers:
                        if offers[0].get('price'):
                            relevant_text.append(f"  price: {offers[0]['price']}")
                if data.get('description'):
                    desc = data['description'][:500] if len(str(data.get('description', ''))) > 500 else data['description']
                    relevant_text.append(f"  description: {desc}")
        except (json.JSONDecodeError, TypeError):
            pass

    # 5. Price elements - multiple selectors for different brand sites
    price_selectors = [
        '.product-price', '.price', '[data-test="product-price"]',
        '.css-1emn094', '.css-b9fpep',  # Nike
        '.product-price__value', '.price-value',  # Brooks
        '[data-testid="ProductPrice"]',  # Hoka
        '.pdp-price', '.offer-price', '.current-price',
        '[itemprop="price"]', '.sale-price', '.original-price'
    ]
    prices_found = set()
    for selector in price_selectors:
        for el in soup.select(selector):
            text = el.get_text(strip=True)
            # Extract price patterns
            price_match = re.search(r'\$[\d,.]+', text)
            if price_match:
                price_val = price_match.group(0)
                # Only add reasonable prices ($50-$400)
                try:
                    val = float(price_val.replace('$', '').replace(',', ''))
                    if 50 <= val <= 400:
                        prices_found.add(price_val)
                except:
                    pass
    if prices_found:
        relevant_text.append(f"PRICE: {list(prices_found)[0]}")

    # 6. Product specs/details - comprehensive selectors (skip nav/header junk)
    spec_selectors = [
        # Generic
        '.product-specs', '.specs', '.specifications', '.product-details',
        '.pdp-details', '.tech-specs', 'dl', '.product-attributes',
        # Nike specific
        '[data-test="product-description"]', '.description-preview',
        '.product-description', '.css-1pbvugb',
        # Brooks specific
        '.pdp-description', '.product-detail__description',
        '.product-features', '.shoe-specs',
        # Hoka specific
        '[data-testid="ProductDescription"]', '.product-info',
        # ASICS specific
        '.product-detail', '.pdp-info',
    ]

    # Skip text that looks like navigation
    nav_keywords = ['new arrivals', 'best sellers', 'shop all', 'sign in', 'join us',
                    'find a store', 'help', 'order status', 'shipping', 'returns',
                    'contact us', 'membership', 'size charts', 'promotions']

    for selector in spec_selectors:
        for el in soup.select(selector):
            text = el.get_text(' | ', strip=True)
            # Skip if it looks like navigation
            text_lower = text.lower()
            if any(nav in text_lower for nav in nav_keywords):
                continue
            if text and len(text) > 30 and len(text) < 2000:
                relevant_text.append(f"DETAILS: {text[:800]}")

    # 7. Look for specific spec patterns in the entire page text
    body_text = soup.get_text(' ', strip=True)

    # Weight patterns (various formats)
    weight_patterns = [
        r'weight[:\s]*(\d+\.?\d*)\s*(?:oz|ounces)',
        r'(\d+\.?\d*)\s*oz\s*(?:weight|\(weight\))',
        r'weight[:\s]*(\d+)\s*g(?:rams)?',
    ]
    for pattern in weight_patterns:
        match = re.search(pattern, body_text, re.IGNORECASE)
        if match:
            relevant_text.append(f"WEIGHT: {match.group(0)}")
            break

    # Drop/offset patterns
    drop_patterns = [
        r'(?:heel[- ]?toe\s*)?(?:drop|offset)[:\s]*(\d+\.?\d*)\s*mm',
        r'(\d+)\s*mm\s*(?:drop|offset)',
    ]
    for pattern in drop_patterns:
        match = re.search(pattern, body_text, re.IGNORECASE)
        if match:
            relevant_text.append(f"DROP: {match.group(0)}")
            break

    # Stack height patterns
    stack_patterns = [
        r'(?:heel|rear)\s*(?:stack|height)[:\s]*(\d+\.?\d*)\s*mm',
        r'forefoot\s*(?:stack|height)[:\s]*(\d+\.?\d*)\s*mm',
        r'stack\s*height[:\s]*(\d+\.?\d*)\s*mm',
        r'(\d+)\s*mm\s*/\s*(\d+)\s*mm',  # e.g., "39mm / 33mm"
    ]
    for pattern in stack_patterns:
        matches = re.findall(pattern, body_text, re.IGNORECASE)
        if matches:
            relevant_text.append(f"STACK: {' | '.join(str(m) for m in matches)}")

    # Foam/cushion technology
    foam_keywords = [
        'ZoomX', 'React', 'Air Zoom', 'Zoom Air',  # Nike
        'DNA LOFT', 'DNA AMP', 'DNA FLASH', 'BioMoGo DNA', 'Nitrogen',  # Brooks
        'PEBA', 'EVA', 'TPU', 'CMEVA',  # Hoka
        'FF BLAST', 'FlyteFoam', 'GEL',  # ASICS
        'PWRRUN', 'PWRRUN PB', 'PWRRUN+',  # Saucony
        'Fresh Foam', 'FuelCell',  # New Balance
        'Helion', 'CloudTec',  # On
        'EGO', 'Altra EGO',  # Altra
    ]
    for foam in foam_keywords:
        if foam.lower() in body_text.lower():
            relevant_text.append(f"FOAM TECH: {foam}")

    # Carbon plate detection
    carbon_keywords = ['carbon plate', 'carbon fiber plate', 'carbon-fiber', 'carbitex']
    for kw in carbon_keywords:
        if kw.lower() in body_text.lower():
            relevant_text.append("HAS CARBON PLATE: yes")
            break

    # Category hints
    category_keywords = {
        'racing': ['racing', 'race day', 'competition', 'marathon', 'speed'],
        'daily_trainer': ['daily trainer', 'everyday', 'daily run', 'training'],
        'stability': ['stability', 'support', 'guide rail', 'pronation'],
        'tempo': ['tempo', 'speed work', 'interval', 'fast'],
        'recovery': ['recovery', 'easy run', 'cushioned'],
        'trail': ['trail', 'off-road', 'mountain', 'terrain'],
    }
    for cat, keywords in category_keywords.items():
        for kw in keywords:
            if kw.lower() in body_text.lower():
                relevant_text.append(f"CATEGORY HINT: {cat}")
                break

    # Gender from URL or text - check URL first, then content
    url_and_text = (url.lower() + ' ' + body_text.lower())
    if '/mens' in url_and_text or '/men/' in url_and_text or 'mens-' in url_and_text or "men's" in soup.get_text()[:500].lower():
        relevant_text.append("GENDER: mens")
    elif '/womens' in url_and_text or '/women/' in url_and_text or 'womens-' in url_and_text or "women's" in soup.get_text()[:500].lower():
        relevant_text.append("GENDER: womens")

    result = '\n'.join(relevant_text)

    # Truncate if too long
    if len(result) > max_chars:
        result = result[:max_chars] + "\n... [truncated]"

    return result


def extract_product_with_llm(
    html: str,
    url: str = "",
    timeout: int = 30
) -> Optional[ExtractedProduct]:
    """
    Use Ollama with Granite4 to extract structured product data from HTML.
    """
    # Clean and prepare HTML
    cleaned_content = clean_html_for_llm(html, url=url)

    if not cleaned_content or len(cleaned_content) < 50:
        return None

    # Detect brand from URL for better context
    brand_hint = ""
    url_lower = url.lower()
    if 'nike.com' in url_lower:
        brand_hint = "This is from Nike.com. "
    elif 'brooksrunning.com' in url_lower:
        brand_hint = "This is from Brooks Running. "
    elif 'hoka.com' in url_lower:
        brand_hint = "This is from Hoka. "
    elif 'asics.com' in url_lower:
        brand_hint = "This is from ASICS. "
    elif 'saucony.com' in url_lower:
        brand_hint = "This is from Saucony. "
    elif 'newbalance.com' in url_lower:
        brand_hint = "This is from New Balance. "
    elif 'on-running.com' in url_lower or 'on.com' in url_lower:
        brand_hint = "This is from On Running. "
    elif 'altra' in url_lower:
        brand_hint = "This is from Altra. "

    # Optimized prompt for 1B model
    prompt = f"""{brand_hint}Extract running shoe data from this content:

{cleaned_content}

Return JSON with these exact fields:
- brand: the shoe brand name
- model_name: model name WITHOUT brand (e.g. "Pegasus 41" not "Nike Pegasus 41")
- price_usd: price as number only
- gender: "mens" or "womens" (use GENDER from content above)
- terrain: "road" or "trail"
- weight_oz: weight in ounces as number
- drop_mm: heel-toe drop in mm as number
- cushion_type: foam technology name
- has_carbon_plate: true or false

JSON:"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.05,  # Very low for consistent extraction
                    "num_predict": 400,
                }
            },
            timeout=timeout
        )
        response.raise_for_status()

        result = response.json()
        llm_output = result.get('response', '').strip()

        # Extract JSON - handle nested braces for the full object
        # Find the first { and match to its closing }
        start = llm_output.find('{')
        if start == -1:
            print(f"  No JSON found in LLM response: {llm_output[:200]}")
            return None

        # Count braces to find matching end
        depth = 0
        end = start
        for i, char in enumerate(llm_output[start:], start):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        json_str = llm_output[start:end]

        # Parse JSON
        data = json.loads(json_str)

        # Convert to ExtractedProduct
        product = ExtractedProduct(
            brand=data.get('brand') or "",
            model_name=data.get('model_name') or "",
            full_name=data.get('full_name') or "",
            price_usd=_safe_float(data.get('price_usd')),
            msrp_usd=_safe_float(data.get('msrp_usd')),
            colorway=data.get('colorway'),
            gender=_normalize_gender(data.get('gender')),
            terrain=_normalize_terrain(data.get('terrain')),
            category=data.get('category'),
            weight_oz=_safe_float(data.get('weight_oz')),
            drop_mm=_safe_float(data.get('drop_mm')),
            stack_height_heel_mm=_safe_float(data.get('stack_height_heel_mm')),
            stack_height_forefoot_mm=_safe_float(data.get('stack_height_forefoot_mm')),
            cushion_type=data.get('cushion_type'),
            has_carbon_plate=bool(data.get('has_carbon_plate')),
            style_id=data.get('style_id'),
        )

        return product

    except requests.exceptions.Timeout:
        print(f"  LLM request timed out")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  LLM request error: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  Extraction error: {e}")
        return None


def _safe_float(value) -> Optional[float]:
    """Safely convert value to float."""
    if value is None:
        return None
    if isinstance(value, str):
        # Remove units and currency symbols
        value = re.sub(r'[^0-9.]', '', value)
    try:
        f = float(value)
        return f if f > 0 else None
    except (ValueError, TypeError):
        return None


def _normalize_gender(gender: Optional[str]) -> Optional[str]:
    """Normalize gender string."""
    if not gender:
        return None
    gender = gender.lower().strip()
    if 'women' in gender or 'female' in gender:
        return 'womens'
    elif 'men' in gender or 'male' in gender:
        return 'mens'
    elif 'unisex' in gender:
        return 'unisex'
    return None


def _normalize_terrain(terrain: Optional[str]) -> Optional[str]:
    """Normalize terrain string."""
    if not terrain:
        return None
    terrain = terrain.lower().strip()
    if 'trail' in terrain:
        return 'trail'
    elif 'track' in terrain or 'spike' in terrain:
        return 'track'
    elif 'road' in terrain:
        return 'road'
    return 'road'  # Default to road


def test_extraction():
    """Test the extractor with brand site pages."""
    from playwright.sync_api import sync_playwright
    import time

    test_urls = [
        "https://www.nike.com/t/pegasus-41-mens-road-running-shoes-kKqCqX/FD2722-001",
        "https://www.brooksrunning.com/en_us/ghost-max-2-mens-running-shoe/110419.html",
        "https://www.hoka.com/en/us/mens-road/clifton-10/1148068.html",
    ]

    print("=" * 70)
    print("TESTING IMPROVED LLM EXTRACTOR")
    print(f"Model: {MODEL}")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )

        for url in test_urls:
            print(f"\n{'='*70}")
            print(f"URL: {url}")
            print("=" * 70)

            page = context.new_page()
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=30000)
                time.sleep(3)
                html = page.content()

                print(f"Got {len(html)} bytes of HTML")

                # Show cleaned content preview
                cleaned = clean_html_for_llm(html)
                print(f"\nCleaned content ({len(cleaned)} chars):")
                print("-" * 40)
                print(cleaned[:2000])
                print("-" * 40)

                # Extract
                start = time.time()
                result = extract_product_with_llm(html, url)
                elapsed = time.time() - start

                if result:
                    print(f"\nExtracted in {elapsed:.1f}s:")
                    for key, value in result.to_dict().items():
                        if value is not None and value != "" and value != False:
                            print(f"  {key}: {value}")
                else:
                    print(f"\nExtraction failed after {elapsed:.1f}s")

            except Exception as e:
                print(f"Error: {e}")
            finally:
                page.close()

        browser.close()


if __name__ == '__main__':
    test_extraction()
