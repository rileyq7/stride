import json
import logging
from typing import List, Optional
from app.scrapers.base import RawReview
from app.core.config import settings

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Analyze these shoe reviews and extract structured fit information.

Reviews:
{reviews_text}

Extract the following information based on consensus across reviews. Respond with valid JSON only, no additional text:
{{
    "size_runs": "small" | "true" | "large",
    "size_offset": <float between -1.0 and +1.0, e.g., 0.5 means runs half size large>,
    "width_runs": "narrow" | "true" | "wide",
    "toe_box_room": "cramped" | "snug" | "roomy" | "spacious",
    "heel_fit": "loose" | "secure" | "tight",
    "midfoot_fit": "loose" | "secure" | "tight",
    "arch_support": "flat" | "neutral" | "high",
    "arch_support_level": "minimal" | "moderate" | "substantial",
    "break_in_period": "none" | "short" | "moderate" | "long",
    "break_in_miles": <integer or null>,
    "durability_rating": "poor" | "average" | "good" | "excellent",
    "expected_miles_min": <integer>,
    "expected_miles_max": <integer>,
    "common_complaints": [<list of common issues mentioned>],
    "works_well_for": [<list: "wide_feet", "narrow_feet", "high_arches", "flat_feet", "plantar_fasciitis", "bunions", "overpronation", etc.>],
    "avoid_if": [<list of conditions this shoe is bad for>],
    "overall_sentiment": <float between 0.0 and 1.0, where 1.0 is very positive>
}}

Base your analysis on consensus across multiple reviews. If information isn't clearly available, use null. Focus on fit-related details, not general preferences."""


class ReviewFitExtractor:
    """Extract structured fit data from raw reviews using Claude."""

    def __init__(self):
        self.client = None
        if settings.ANTHROPIC_API_KEY:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            except ImportError:
                logger.warning("Anthropic library not installed")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {e}")

    def extract_fit_profile(self, reviews: List[RawReview]) -> Optional[dict]:
        """Extract fit profile from a list of reviews."""
        if not self.client:
            logger.warning("AI client not available, using fallback extraction")
            return self._fallback_extraction(reviews)

        if not reviews:
            return None

        # Prepare reviews text (limit to avoid context length issues)
        reviews_text = self._format_reviews_for_prompt(reviews[:30])

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{
                    "role": "user",
                    "content": EXTRACTION_PROMPT.format(reviews_text=reviews_text)
                }]
            )

            # Extract JSON from response
            response_text = response.content[0].text.strip()

            # Try to parse JSON
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract JSON from response if it has extra text
                import re
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    logger.error(f"Could not parse AI response as JSON: {response_text[:200]}")
                    return self._fallback_extraction(reviews)

            # Add metadata
            result['review_count'] = len(reviews)
            result['extraction_model'] = 'claude-sonnet-4-20250514'

            return result

        except Exception as e:
            logger.error(f"AI extraction failed: {e}")
            return self._fallback_extraction(reviews)

    def _format_reviews_for_prompt(self, reviews: List[RawReview]) -> str:
        """Format reviews into a text block for the prompt."""
        formatted = []
        for r in reviews:
            parts = []
            if r.rating:
                parts.append(f"Rating: {r.rating}/5")
            if r.reviewer_foot_width:
                parts.append(f"Reviewer width: {r.reviewer_foot_width}")
            if r.reviewer_arch_type:
                parts.append(f"Reviewer arch: {r.reviewer_arch_type}")
            if r.reviewer_size_purchased:
                parts.append(f"Size purchased: {r.reviewer_size_purchased}")

            # Truncate long reviews
            body = r.body[:600] if r.body else ""
            parts.append(f"Review: {body}")

            formatted.append("\n".join(parts))

        return "\n\n---\n\n".join(formatted)

    def _fallback_extraction(self, reviews: List[RawReview]) -> dict:
        """Simple heuristic-based extraction when AI is not available."""
        if not reviews:
            return {}

        result = {
            'size_runs': 'true',
            'width_runs': 'true',
            'review_count': len(reviews),
            'extraction_model': 'heuristic',
            'needs_review': True,
        }

        # Simple keyword analysis
        all_text = ' '.join(r.body.lower() for r in reviews if r.body)

        # Size analysis
        if 'runs small' in all_text or 'size up' in all_text:
            result['size_runs'] = 'small'
            result['size_offset'] = 0.5
        elif 'runs large' in all_text or 'size down' in all_text:
            result['size_runs'] = 'large'
            result['size_offset'] = -0.5

        # Width analysis
        if 'narrow' in all_text and 'wide' not in all_text:
            result['width_runs'] = 'narrow'
        elif 'wide' in all_text and 'narrow' not in all_text:
            result['width_runs'] = 'wide'

        # Toe box
        if 'roomy toe' in all_text or 'spacious toe' in all_text:
            result['toe_box_room'] = 'roomy'
        elif 'tight toe' in all_text or 'cramped' in all_text:
            result['toe_box_room'] = 'cramped'
        else:
            result['toe_box_room'] = 'snug'

        # Sentiment from ratings
        ratings = [r.rating for r in reviews if r.rating is not None]
        if ratings:
            avg_rating = sum(ratings) / len(ratings)
            result['overall_sentiment'] = round(avg_rating / 5.0, 2)

        return result
