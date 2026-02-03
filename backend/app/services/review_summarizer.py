"""
Review Summarizer Service

Uses LLM (Granite4 via Ollama) to generate consensus summaries from shoe reviews.
Extracts sizing recommendations, pros/cons, and fit information.
"""

import json
import re
import logging
import requests
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Ollama configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "granite4:1b-h"  # Best balance of speed (4s) and quality (79%)


@dataclass
class ReviewSummaryResult:
    """Result from LLM summarization."""
    sizing_verdict: str  # 'true_to_size', 'size_up', 'size_down', 'unknown'
    sizing_confidence: float  # 0.0 to 1.0
    sizing_notes: Optional[str]

    width_forefoot: str  # 'narrow', 'normal', 'wide', 'unknown'
    width_midfoot: str
    width_heel: str

    pros: List[str]  # Top 3-5 pros
    cons: List[str]  # Top 3-5 cons

    best_for: List[str]  # Who this shoe is ideal for
    avoid_if: List[str]  # Who should avoid this shoe

    notable_quotes: List[Dict[str, str]]  # {"quote": "...", "source": "..."}

    overall_sentiment: float  # 0.0 (negative) to 1.0 (positive)


SUMMARIZATION_PROMPT = """You are analyzing running shoe reviews to extract a consensus summary.

REVIEWS FOR: {shoe_name}
Number of reviews: {num_reviews}

REVIEWS:
{reviews_text}

Based on these reviews, extract the following information. Be concise and accurate.
Return ONLY valid JSON with no explanation.

{{
  "sizing": {{
    "verdict": "true_to_size" or "size_up_half" or "size_up_full" or "size_down_half" or "unknown",
    "confidence": 0.0 to 1.0 (how confident based on reviewer consensus),
    "notes": "brief note if sizing is conditional or varies"
  }},
  "width": {{
    "forefoot": "narrow" or "normal" or "wide" or "unknown",
    "midfoot": "narrow" or "normal" or "wide" or "unknown",
    "heel": "narrow" or "normal" or "wide" or "unknown"
  }},
  "pros": ["top pro 1", "top pro 2", "top pro 3"],
  "cons": ["top con 1", "top con 2", "top con 3"],
  "best_for": ["type of runner this shoe is ideal for"],
  "avoid_if": ["who should avoid this shoe"],
  "notable_quotes": [
    {{"quote": "a memorable quote from review", "reviewer": "reviewer name or source"}}
  ],
  "overall_sentiment": 0.0 to 1.0 (0=negative, 1=positive)
}}

JSON only:"""


def format_reviews_for_prompt(reviews: List[Dict[str, Any]], max_chars: int = 6000) -> str:
    """Format reviews for the LLM prompt."""
    formatted = []
    total_chars = 0

    for i, review in enumerate(reviews):
        reviewer = review.get('reviewer_name', 'Anonymous')
        rating = review.get('rating', 'N/A')
        body = review.get('body', '')[:1500]  # Limit individual review length

        # Add source type if available
        source = review.get('source', '')
        if 'believe_in_the_run' in source or 'doctors_of_running' in source:
            review_type = "[EXPERT]"
        else:
            review_type = "[USER]"

        text = f"""
---
{review_type} Review by {reviewer} (Rating: {rating})
{body}
---
"""
        if total_chars + len(text) > max_chars:
            break

        formatted.append(text)
        total_chars += len(text)

    return '\n'.join(formatted)


def _ensure_list(value: Any) -> List[str]:
    """Ensure value is a list of strings (handle LLM returning string instead of list)."""
    if isinstance(value, list):
        return [str(v) for v in value if v]
    elif isinstance(value, str) and value:
        return [value]  # Wrap string in list
    return []


def extract_json_from_response(text: str) -> Optional[dict]:
    """Extract JSON object from LLM response."""
    # Try to find JSON block
    patterns = [
        r'```json\s*(.*?)\s*```',
        r'```\s*(.*?)\s*```',
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Nested JSON
    ]

    for pattern in patterns[:2]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    # Try last pattern (greedy JSON match)
    match = re.search(patterns[2], text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Try parsing the entire response
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    return None


def summarize_reviews(
    shoe_name: str,
    reviews: List[Dict[str, Any]],
    timeout: int = 60
) -> Optional[ReviewSummaryResult]:
    """
    Generate a consensus summary from multiple reviews using LLM.

    Args:
        shoe_name: Name of the shoe being reviewed
        reviews: List of review dicts with 'reviewer_name', 'rating', 'body', 'source' keys
        timeout: Request timeout in seconds

    Returns:
        ReviewSummaryResult or None if summarization failed
    """
    if not reviews:
        return None

    # Format reviews for prompt
    reviews_text = format_reviews_for_prompt(reviews)

    # Build prompt
    prompt = SUMMARIZATION_PROMPT.format(
        shoe_name=shoe_name,
        num_reviews=len(reviews),
        reviews_text=reviews_text
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 800}
            },
            timeout=timeout
        )
        response.raise_for_status()

        llm_output = response.json().get('response', '').strip()
        parsed = extract_json_from_response(llm_output)

        if not parsed:
            logger.error(f"Failed to parse LLM response: {llm_output[:200]}")
            return None

        # Convert to result object
        sizing = parsed.get('sizing', {})
        width = parsed.get('width', {})

        return ReviewSummaryResult(
            sizing_verdict=sizing.get('verdict', 'unknown'),
            sizing_confidence=float(sizing.get('confidence', 0.5)),
            sizing_notes=sizing.get('notes'),

            width_forefoot=width.get('forefoot', 'unknown'),
            width_midfoot=width.get('midfoot', 'unknown'),
            width_heel=width.get('heel', 'unknown'),

            pros=_ensure_list(parsed.get('pros', []))[:5],
            cons=_ensure_list(parsed.get('cons', []))[:5],

            best_for=_ensure_list(parsed.get('best_for', [])),
            avoid_if=_ensure_list(parsed.get('avoid_if', [])),

            notable_quotes=parsed.get('notable_quotes', [])[:3],

            overall_sentiment=float(parsed.get('overall_sentiment', 0.5))
        )

    except requests.RequestException as e:
        logger.error(f"LLM request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Error in summarize_reviews: {e}")
        return None


def result_to_consensus_dict(result: ReviewSummaryResult) -> Dict[str, Any]:
    """Convert ReviewSummaryResult to the consensus JSONB format used in ReviewSummary model."""
    return {
        "sizing": {
            "verdict": result.sizing_verdict,
            "confidence": result.sizing_confidence,
            "notes": result.sizing_notes,
        },
        "width": {
            "forefoot": result.width_forefoot,
            "midfoot": result.width_midfoot,
            "heel": result.width_heel,
        },
        "comfort": {
            "break_in_miles": None,  # Not extracted by LLM yet
            "all_day_wearable": None,
        },
        "durability": {
            "expected_miles_min": None,
            "expected_miles_max": None,
            "weak_points": [],
        },
    }


def result_to_recommendations_dict(result: ReviewSummaryResult) -> Dict[str, Any]:
    """Convert ReviewSummaryResult to recommendations JSONB format."""
    recommendations = {}

    # Infer recommendations from best_for/avoid_if
    for item in result.best_for:
        item_lower = item.lower()
        if 'wide' in item_lower:
            recommendations['wide_feet'] = {'suitable': True, 'notes': item}
        if 'narrow' in item_lower:
            recommendations['narrow_feet'] = {'suitable': True, 'notes': item}
        if 'high arch' in item_lower:
            recommendations['high_arches'] = {'suitable': True, 'notes': item}
        if 'flat' in item_lower:
            recommendations['flat_feet'] = {'suitable': True, 'notes': item}

    for item in result.avoid_if:
        item_lower = item.lower()
        if 'wide' in item_lower:
            recommendations['wide_feet'] = {'suitable': False, 'notes': item}
        if 'narrow' in item_lower:
            recommendations['narrow_feet'] = {'suitable': False, 'notes': item}
        if 'high arch' in item_lower:
            recommendations['high_arches'] = {'suitable': False, 'notes': item}
        if 'flat' in item_lower:
            recommendations['flat_feet'] = {'suitable': False, 'notes': item}

    return recommendations
