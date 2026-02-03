#!/usr/bin/env python
"""
Benchmark Granite4 models for shoe data extraction.
Compares extraction quality and speed across model sizes.
"""

import sys
import time
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.sync_api import sync_playwright


OLLAMA_URL = "http://localhost:11434/api/generate"
MODELS = ["granite4:350m-h", "granite4:1b-h", "granite4:latest"]

# Test URLs - brand sites directly
TEST_URLS = [
    "https://www.nike.com/t/pegasus-41-mens-road-running-shoes-kKqCqX/FD2722-001",
    "https://www.brooksrunning.com/en_us/ghost-max-2-mens-running-shoe/110419.html",
    "https://www.hoka.com/en/us/mens-road/clifton-10/1148068.html",
]

EXTRACTION_PROMPT = """Extract product information from this running shoe page content. Return ONLY valid JSON with no explanation.

Content:
{content}

Extract these fields (use null if not found):
{{
  "brand": "brand name",
  "model_name": "model without brand",
  "full_name": "complete product name",
  "price_usd": numeric price or null,
  "gender": "mens" or "womens" or "unisex",
  "terrain": "road" or "trail",
  "weight_oz": numeric weight in ounces or null,
  "drop_mm": heel-to-toe drop in mm or null,
  "stack_height_heel_mm": heel stack height or null,
  "colorway": "color description",
  "has_carbon_plate": true or false
}}

JSON only:"""


def clean_html(html: str, max_chars: int = 8000) -> str:
    """Extract relevant text from HTML using improved extractor."""
    from llm_product_extractor import clean_html_for_llm
    return clean_html_for_llm(html, max_chars)


def extract_with_model(model: str, content: str, timeout: int = 60) -> tuple[Optional[dict], float]:
    """Run extraction with a specific model. Returns (result, time_seconds)."""
    prompt = EXTRACTION_PROMPT.format(content=content)

    start = time.time()
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 400}
            },
            timeout=timeout
        )
        response.raise_for_status()
        elapsed = time.time() - start

        llm_output = response.json().get('response', '').strip()

        # Extract JSON
        import re
        json_match = re.search(r'\{[^{}]*\}', llm_output, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0)), elapsed
        return None, elapsed

    except Exception as e:
        return {"error": str(e)}, time.time() - start


def score_extraction(result: Optional[dict]) -> dict:
    """Score extraction quality."""
    if not result or "error" in result:
        return {"score": 0, "fields": 0, "total_fields": 8, "issues": [], "details": "extraction_failed"}

    expected_fields = [
        "brand", "model_name", "price_usd", "weight_oz",
        "drop_mm", "stack_height_heel_mm", "gender", "terrain"
    ]

    found = sum(1 for f in expected_fields if result.get(f) is not None)

    # Quality checks
    issues = []
    if result.get("brand") and len(result["brand"]) > 30:
        issues.append("brand_too_long")
    if result.get("model_name") and result.get("brand") in str(result.get("model_name", "")):
        issues.append("model_includes_brand")
    price = result.get("price_usd")
    if price and isinstance(price, (int, float)) and (price < 50 or price > 500):
        issues.append("price_suspicious")

    score = (found / len(expected_fields)) * 100 - len(issues) * 10

    return {
        "score": max(0, score),
        "fields": found,
        "total_fields": len(expected_fields),
        "issues": issues
    }


def main():
    print("=" * 70)
    print("GRANITE4 MODEL BENCHMARK")
    print("Comparing extraction quality and speed")
    print("=" * 70)

    # Fetch test pages
    print("\nFetching test pages...")
    pages = {}

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            locale='en-US',
            timezone_id='America/New_York',
        )

        for url in TEST_URLS:
            print(f"  Fetching: {url.split('/')[-1]}")
            page = context.new_page()
            try:
                # Block images for faster load
                page.route('**/*.{png,jpg,jpeg,gif,webp}', lambda route: route.abort())
                page.goto(url, wait_until='networkidle', timeout=60000)

                # Dismiss popups
                for _ in range(2):
                    try:
                        stay = page.locator('button:has-text("Stay")').first
                        if stay.is_visible(timeout=1000):
                            stay.click()
                            time.sleep(1)
                    except:
                        pass

                time.sleep(2)
                html = page.content()
                pages[url] = clean_html(html)
            except Exception as e:
                print(f"    Error: {e}")
            finally:
                page.close()

        browser.close()

    print(f"\nFetched {len(pages)} pages")

    # Benchmark each model
    results = {model: {"times": [], "scores": [], "extractions": []} for model in MODELS}

    print("\n" + "=" * 70)
    print("RUNNING BENCHMARKS")
    print("=" * 70)

    for model in MODELS:
        print(f"\n--- {model} ---")

        for url, content in pages.items():
            product_name = url.split('/')[-1].replace('.html', '')
            print(f"  {product_name}: ", end="", flush=True)

            extracted, elapsed = extract_with_model(model, content)
            score_info = score_extraction(extracted)

            results[model]["times"].append(elapsed)
            results[model]["scores"].append(score_info["score"])
            results[model]["extractions"].append(extracted)

            print(f"{elapsed:.1f}s, score={score_info['score']:.0f}, fields={score_info['fields']}/{score_info['total_fields']}")

            if extracted and "error" not in extracted:
                print(f"    -> {extracted.get('brand')} {extracted.get('model_name')}: ${extracted.get('price_usd')}, {extracted.get('weight_oz')}oz")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n{'Model':<25} {'Avg Time':>10} {'Avg Score':>12} {'Est. 2000 products':>20}")
    print("-" * 70)

    for model in MODELS:
        avg_time = sum(results[model]["times"]) / len(results[model]["times"])
        avg_score = sum(results[model]["scores"]) / len(results[model]["scores"])
        est_total = (avg_time * 2000) / 3600  # hours

        print(f"{model:<25} {avg_time:>8.1f}s {avg_score:>10.0f}% {est_total:>17.1f} hrs")

    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)

    # Find best balance
    best_model = None
    best_value = 0

    for model in MODELS:
        avg_time = sum(results[model]["times"]) / len(results[model]["times"])
        avg_score = sum(results[model]["scores"]) / len(results[model]["scores"])
        # Value = score / log(time) - prefer fast + accurate
        import math
        value = avg_score / math.log(avg_time + 1)
        if value > best_value:
            best_value = value
            best_model = model

    print(f"\nBest balance of speed + quality: {best_model}")


if __name__ == '__main__':
    main()
