"""
Review-to-Product Matcher Service

Matches scraped reviews to ShoeProduct records in the database.
Uses brand name normalization, fuzzy model matching, and gender inference.
"""

import re
import logging
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import Brand
from app.models.catalog import ShoeModel, ShoeProduct

logger = logging.getLogger(__name__)


# Brand name normalization map
BRAND_ALIASES = {
    # Standard forms
    'adidas': 'adidas',
    'asics': 'asics',
    'brooks': 'brooks',
    'hoka': 'hoka',
    'hoka one one': 'hoka',
    'new balance': 'new-balance',
    'nb': 'new-balance',
    'nike': 'nike',
    'on': 'on',
    'on running': 'on',
    'saucony': 'saucony',
    'altra': 'altra',
    'mizuno': 'mizuno',
    'salomon': 'salomon',
    'la sportiva': 'la-sportiva',
    'topo athletic': 'topo-athletic',
    'topo': 'topo-athletic',
    'the north face': 'the-north-face',
    'north face': 'the-north-face',
    'tnf': 'the-north-face',
    'puma': 'puma',
    'inov-8': 'inov-8',
    'inov8': 'inov-8',
    'craft': 'craft',
    '361 degrees': '361-degrees',
    '361°': '361-degrees',
    'karhu': 'karhu',
    'nnormal': 'nnormal',
    'diadora': 'diadora',
    'merrell': 'merrell',
    'under armour': 'under-armour',
    'ua': 'under-armour',
    'reebok': 'reebok',
    'newton': 'newton',
    'scott': 'scott',
}


def normalize_brand(brand_name: str) -> Optional[str]:
    """Normalize a brand name to its database slug form."""
    if not brand_name:
        return None
    normalized = brand_name.lower().strip()
    return BRAND_ALIASES.get(normalized, normalized.replace(' ', '-'))


def normalize_model_name(name: str) -> str:
    """Normalize a model name for comparison."""
    if not name:
        return ''
    # Lowercase, remove special chars, normalize whitespace
    normalized = name.lower()
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip()


def extract_model_keywords(name: str) -> List[str]:
    """Extract key words from a model name for matching."""
    normalized = normalize_model_name(name)
    # Split into words, filter out common words
    words = normalized.split()
    stopwords = {'mens', 'womens', 'unisex', 'running', 'shoe', 'shoes', 'road', 'trail', 'the', 'and', 'for'}
    return [w for w in words if w not in stopwords and len(w) > 1]


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def fuzzy_match_score(query: str, target: str) -> float:
    """
    Calculate fuzzy match score between query and target.
    Returns 0.0 (no match) to 1.0 (perfect match).
    """
    query_norm = normalize_model_name(query)
    target_norm = normalize_model_name(target)

    if not query_norm or not target_norm:
        return 0.0

    # Exact match
    if query_norm == target_norm:
        return 1.0

    # Substring match
    if query_norm in target_norm or target_norm in query_norm:
        return 0.9

    # Keyword match
    query_keywords = set(extract_model_keywords(query))
    target_keywords = set(extract_model_keywords(target))

    if query_keywords and target_keywords:
        overlap = len(query_keywords & target_keywords)
        total = len(query_keywords | target_keywords)
        keyword_score = overlap / total if total > 0 else 0
        if keyword_score >= 0.6:
            return 0.7 + (keyword_score * 0.2)

    # Levenshtein distance
    max_len = max(len(query_norm), len(target_norm))
    distance = levenshtein_distance(query_norm, target_norm)
    similarity = 1 - (distance / max_len)

    return max(0, similarity)


def infer_gender(text: str) -> Optional[str]:
    """Infer gender from text content or URL."""
    text_lower = text.lower()

    # Check for explicit gender indicators
    womens_patterns = ['/womens', '/women/', 'womens-', '-womens', 'women\'s', 'ladies']
    mens_patterns = ['/mens', '/men/', 'mens-', '-mens', 'men\'s']

    for pattern in womens_patterns:
        if pattern in text_lower:
            return 'womens'

    for pattern in mens_patterns:
        if pattern in text_lower:
            return 'mens'

    return None


class ReviewMatcher:
    """
    Service for matching scraped reviews to ShoeProduct records.
    """

    def __init__(self, session: Session):
        self.session = session
        self._brand_cache: dict = {}
        self._model_cache: dict = {}

    def _get_brand(self, brand_slug: str) -> Optional[Brand]:
        """Get brand by slug with caching."""
        if brand_slug not in self._brand_cache:
            brand = self.session.execute(
                select(Brand).where(Brand.slug == brand_slug)
            ).scalar_one_or_none()
            self._brand_cache[brand_slug] = brand
        return self._brand_cache.get(brand_slug)

    def match_product(
        self,
        brand_name: str,
        model_name: str,
        url: str = '',
        min_score: float = 0.6
    ) -> Optional[Tuple[ShoeProduct, float]]:
        """
        Match a review to a ShoeProduct.

        Args:
            brand_name: Brand name from the review
            model_name: Model name from the review
            url: Optional URL to help infer gender
            min_score: Minimum fuzzy match score required

        Returns:
            Tuple of (ShoeProduct, score) if found, None otherwise
        """
        # Normalize brand
        brand_slug = normalize_brand(brand_name)
        if not brand_slug:
            logger.debug(f"Could not normalize brand: {brand_name}")
            return None

        brand = self._get_brand(brand_slug)
        if not brand:
            logger.debug(f"Brand not found in DB: {brand_slug}")
            return None

        # Infer gender from URL or model name
        combined_text = f"{url} {model_name}"
        gender = infer_gender(combined_text)

        # Get all models for this brand
        query = select(ShoeModel).where(ShoeModel.brand_id == brand.id)
        if gender:
            query = query.where(ShoeModel.gender == gender)

        models = self.session.execute(query).scalars().all()

        if not models:
            logger.debug(f"No models found for brand {brand_slug} (gender={gender})")
            return None

        # Find best matching model
        best_model = None
        best_model_score = 0.0

        for model in models:
            score = fuzzy_match_score(model_name, model.name)
            if score > best_model_score:
                best_model_score = score
                best_model = model

        if best_model_score < min_score or not best_model:
            logger.debug(f"No good model match for '{model_name}' (best: {best_model_score:.2f})")
            return None

        # Get products for this model
        products = self.session.execute(
            select(ShoeProduct).where(ShoeProduct.model_id == best_model.id)
        ).scalars().all()

        if not products:
            logger.debug(f"No products found for model {best_model.name}")
            return None

        # Return the first/primary product (could enhance to match colorway)
        return (products[0], best_model_score)

    def match_model(
        self,
        brand_name: str,
        model_name: str,
        min_score: float = 0.6
    ) -> Optional[Tuple[ShoeModel, float]]:
        """
        Match a review to a ShoeModel (if no specific product match needed).

        Args:
            brand_name: Brand name from the review
            model_name: Model name from the review
            min_score: Minimum fuzzy match score required

        Returns:
            Tuple of (ShoeModel, score) if found, None otherwise
        """
        brand_slug = normalize_brand(brand_name)
        if not brand_slug:
            return None

        brand = self._get_brand(brand_slug)
        if not brand:
            return None

        # Get all models for this brand
        models = self.session.execute(
            select(ShoeModel).where(ShoeModel.brand_id == brand.id)
        ).scalars().all()

        best_model = None
        best_score = 0.0

        for model in models:
            score = fuzzy_match_score(model_name, model.name)
            if score > best_score:
                best_score = score
                best_model = model

        if best_score >= min_score and best_model:
            return (best_model, best_score)

        return None

    def bulk_match(
        self,
        items: List[dict],
        min_score: float = 0.6
    ) -> List[Tuple[dict, Optional[ShoeProduct], float]]:
        """
        Match multiple items in bulk.

        Args:
            items: List of dicts with 'brand', 'model', and optionally 'url' keys
            min_score: Minimum match score

        Returns:
            List of tuples (original_item, matched_product, score)
        """
        results = []

        for item in items:
            brand = item.get('brand', '')
            model = item.get('model', '')
            url = item.get('url', '')

            match = self.match_product(brand, model, url, min_score)
            if match:
                product, score = match
                results.append((item, product, score))
            else:
                results.append((item, None, 0.0))

        return results


def extract_brand_model_from_title(title: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract brand and model name from a review title.

    Example: "Brooks Ghost 16 Review: Great Daily Trainer"
    Returns: ("Brooks", "Ghost 16")
    """
    if not title:
        return None, None

    # Common review title patterns
    patterns = [
        # "Brand Model Review: ..."
        r'^([A-Za-z\s]+?)\s+(.+?)\s+Review[:\s]',
        # "Brand Model - Review"
        r'^([A-Za-z\s]+?)\s+(.+?)\s+-\s+Review',
        # "Brand Model Review"
        r'^([A-Za-z\s]+?)\s+(.+?)\s+Review$',
    ]

    for pattern in patterns:
        match = re.match(pattern, title, re.IGNORECASE)
        if match:
            potential_brand = match.group(1).strip()
            model = match.group(2).strip()

            # Check if potential_brand is a known brand
            if normalize_brand(potential_brand) in BRAND_ALIASES.values():
                return potential_brand, model

    # Fallback: Check if title starts with a known brand
    title_lower = title.lower()
    for brand_key in BRAND_ALIASES.keys():
        if title_lower.startswith(brand_key):
            # Extract model name after brand
            remaining = title[len(brand_key):].strip()
            # Remove common suffixes
            remaining = re.sub(r'\s+review[:\s].*$', '', remaining, flags=re.IGNORECASE)
            if remaining:
                return brand_key.title(), remaining.strip()

    return None, None
