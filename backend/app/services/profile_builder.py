"""
Service to build ShoeProfile and ReviewSummary from scraped data.

This service processes raw scraped data (ProductSpecs from brand scrapers,
RawReview from review scrapers) and populates the AI-optimized tables.
"""

import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Shoe, ShoeProfile, ReviewSummary, ShoeReview, RunningShoeAttributes
from app.scrapers.brand_scrapers.base import ProductSpecs

logger = logging.getLogger(__name__)


# Constants for normalization
WEIGHT_MIN_OZ = 5.0   # Lightest racing flats
WEIGHT_MAX_OZ = 14.0  # Heavy stability shoes
STACK_MIN_MM = 15.0   # Minimal shoes
STACK_MAX_MM = 45.0   # Max cushioned


def normalize_weight(weight_oz: Optional[Decimal]) -> Optional[Decimal]:
    """Normalize weight to 0-1 scale (0 = lightest, 1 = heaviest)."""
    if weight_oz is None:
        return None
    val = float(weight_oz)
    normalized = (val - WEIGHT_MIN_OZ) / (WEIGHT_MAX_OZ - WEIGHT_MIN_OZ)
    return Decimal(str(max(0.0, min(1.0, normalized)))).quantize(Decimal('0.01'))


def cushion_level_to_score(cushion_level: Optional[str]) -> Optional[Decimal]:
    """Convert cushion level to normalized score."""
    mapping = {
        'minimal': Decimal('0.1'),
        'light': Decimal('0.3'),
        'moderate': Decimal('0.5'),
        'plush': Decimal('0.7'),
        'max': Decimal('0.9'),
    }
    if cushion_level:
        return mapping.get(cushion_level.lower())
    return None


def size_runs_to_fit_value(size_runs: Optional[str]) -> float:
    """Convert size_runs string to fit vector value."""
    mapping = {
        'small': -0.5,
        'slightly_small': -0.25,
        'true': 0.0,
        'true_to_size': 0.0,
        'slightly_large': 0.25,
        'large': 0.5,
    }
    if size_runs:
        return mapping.get(size_runs.lower(), 0.0)
    return 0.0


def width_runs_to_fit_value(width_runs: Optional[str]) -> float:
    """Convert width_runs string to fit vector value."""
    mapping = {
        'narrow': -0.5,
        'slightly_narrow': -0.25,
        'true': 0.0,
        'normal': 0.0,
        'slightly_wide': 0.25,
        'wide': 0.5,
    }
    if width_runs:
        return mapping.get(width_runs.lower(), 0.0)
    return 0.0


class ProfileBuilderService:
    """Service to build and update shoe profiles from scraped data."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def build_profile_from_specs(
        self,
        shoe_id: UUID,
        specs: ProductSpecs
    ) -> ShoeProfile:
        """
        Build or update a ShoeProfile from brand website specs.

        Args:
            shoe_id: The shoe's database ID
            specs: ProductSpecs from a brand scraper

        Returns:
            The created/updated ShoeProfile
        """
        # Get or create profile
        result = await self.session.execute(
            select(ShoeProfile).where(ShoeProfile.shoe_id == shoe_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            profile = ShoeProfile(shoe_id=shoe_id)
            self.session.add(profile)

        # Normalize weight
        if specs.weight_oz:
            profile.weight_normalized = normalize_weight(specs.weight_oz)

        # Cushion score
        if specs.cushion_level:
            profile.cushion_normalized = cushion_level_to_score(specs.cushion_level)

        # Stability (based on subcategory)
        if specs.subcategory:
            stability_mapping = {
                'neutral': Decimal('0.2'),
                'stability': Decimal('0.6'),
                'motion_control': Decimal('0.9'),
                'racing': Decimal('0.1'),
            }
            profile.stability_normalized = stability_mapping.get(
                specs.subcategory.lower(), Decimal('0.3')
            )

        # Terrain scores
        terrain_scores = {
            'road': 0.0,
            'light_trail': 0.0,
            'technical_trail': 0.0,
            'track': 0.0,
        }
        if specs.terrain:
            terrain = specs.terrain.lower()
            if terrain == 'road':
                terrain_scores['road'] = 1.0
                terrain_scores['light_trail'] = 0.2
            elif terrain == 'trail':
                terrain_scores['road'] = 0.3
                terrain_scores['light_trail'] = 0.8
                terrain_scores['technical_trail'] = 0.6
            elif terrain == 'track':
                terrain_scores['track'] = 1.0
                terrain_scores['road'] = 0.5
        profile.terrain_scores = terrain_scores

        # Use case scores based on shoe characteristics
        use_cases = ShoeProfile.default_use_case_scores()
        if specs.subcategory:
            subcat = specs.subcategory.lower()
            if subcat == 'racing' or specs.has_carbon_plate:
                use_cases['racing'] = 0.9
                use_cases['tempo'] = 0.8
                use_cases['intervals'] = 0.7
                use_cases['easy_runs'] = 0.3
            elif subcat == 'daily_trainer':
                use_cases['easy_runs'] = 0.9
                use_cases['long_runs'] = 0.8
            elif specs.cushion_level == 'max':
                use_cases['long_runs'] = 0.9
                use_cases['easy_runs'] = 0.85
                use_cases['walking'] = 0.8
                use_cases['standing'] = 0.75
        profile.use_case_scores = use_cases

        # Build search text
        search_parts = [
            specs.brand or '',
            specs.name or '',
            specs.cushion_type or '',
            specs.subcategory or '',
            specs.terrain or '',
        ]
        profile.search_text = ' '.join(filter(None, search_parts)).lower()

        profile.last_analyzed_at = datetime.utcnow()

        await self.session.flush()
        return profile

    async def build_summary_from_reviews(
        self,
        shoe_id: UUID,
        reviews: List[ShoeReview]
    ) -> ReviewSummary:
        """
        Build or update a ReviewSummary from aggregated reviews.

        Args:
            shoe_id: The shoe's database ID
            reviews: List of ShoeReview records

        Returns:
            The created/updated ReviewSummary
        """
        # Get or create summary
        result = await self.session.execute(
            select(ReviewSummary).where(ReviewSummary.shoe_id == shoe_id)
        )
        summary = result.scalar_one_or_none()

        if not summary:
            summary = ReviewSummary(shoe_id=shoe_id)
            self.session.add(summary)

        if not reviews:
            return summary

        # Count reviews
        summary.total_reviews = len(reviews)
        # Note: We don't have review_type in ShoeReview yet, using source as proxy
        expert_sources = {'doctors_of_running', 'believe_in_the_run', 'weartesters'}
        summary.expert_reviews = sum(
            1 for r in reviews if r.source.lower() in expert_sources
        )
        summary.user_reviews = summary.total_reviews - summary.expert_reviews

        # Average rating
        ratings = [float(r.rating) for r in reviews if r.rating is not None]
        if ratings:
            summary.average_rating = Decimal(str(sum(ratings) / len(ratings))).quantize(Decimal('0.1'))

        # Analyze sizing consensus
        sizing_votes = Counter()
        for review in reviews:
            if review.reviewer_size_purchased and review.reviewer_typical_size:
                purchased = self._parse_size(review.reviewer_size_purchased)
                typical = self._parse_size(review.reviewer_typical_size)
                if purchased and typical:
                    diff = purchased - typical
                    if diff < -0.3:
                        sizing_votes['small'] += 1
                    elif diff > 0.3:
                        sizing_votes['large'] += 1
                    else:
                        sizing_votes['true_to_size'] += 1

        # Build consensus
        consensus = ReviewSummary.default_consensus()
        if sizing_votes:
            verdict = sizing_votes.most_common(1)[0][0]
            total = sum(sizing_votes.values())
            confidence = sizing_votes[verdict] / total
            consensus['sizing'] = {
                'verdict': verdict,
                'confidence': round(confidence, 2),
                'notes': f"Based on {total} reviews",
            }

        # Analyze width from reviewer data
        width_votes = {'forefoot': Counter(), 'midfoot': Counter(), 'heel': Counter()}
        for review in reviews:
            if review.reviewer_foot_width:
                # Map foot width mentions to width fit
                width = review.reviewer_foot_width.lower()
                if 'wide' in width and review.rating and float(review.rating) >= 4:
                    width_votes['forefoot']['wide_friendly'] += 1
                elif 'narrow' in width and review.rating and float(review.rating) >= 4:
                    width_votes['forefoot']['narrow_friendly'] += 1

        summary.consensus = consensus

        # Extract pros and cons from review text
        pros, cons = self._extract_pros_cons(reviews)
        summary.pros = pros[:5]  # Top 5
        summary.cons = cons[:5]

        # Build recommendations by foot type
        recommendations = ReviewSummary.default_recommendations()
        # Logic would analyze review text for specific foot type mentions
        # For now, set based on ratings from reviewers with that foot type
        summary.recommendations = recommendations

        # Sentiment analysis (simplified - would use NLP in production)
        sentiment = {
            'overall': round(sum(ratings) / len(ratings) / 5, 2) if ratings else 0.5,
        }
        summary.sentiment = sentiment

        # Extract notable quotes
        notable_quotes = []
        for review in reviews[:3]:  # Top 3 reviews
            if review.body and len(review.body) > 50:
                # Extract first sentence as quote
                quote = review.body.split('.')[0].strip()
                if len(quote) > 20:
                    notable_quotes.append({
                        'quote': quote[:200],
                        'source': review.source,
                        'reviewer': review.reviewer_name,
                    })
        summary.notable_quotes = notable_quotes

        await self.session.flush()
        return summary

    def _parse_size(self, size_str: str) -> Optional[float]:
        """Parse size string to numeric value."""
        try:
            # Handle "9.5" or "9 1/2" or "9"
            size_str = size_str.strip().lower()
            size_str = size_str.replace('us', '').replace('m', '').replace('w', '').strip()

            if '/' in size_str:
                parts = size_str.split()
                if len(parts) == 2:
                    whole = float(parts[0])
                    fraction = parts[1]
                    if fraction == '1/2':
                        return whole + 0.5
            return float(size_str)
        except (ValueError, IndexError):
            return None

    def _extract_pros_cons(self, reviews: List[ShoeReview]) -> tuple[List[str], List[str]]:
        """Extract common pros and cons from review text."""
        # Simplified keyword extraction
        # In production, would use NLP/LLM
        pro_keywords = {
            'comfortable': 'Comfortable',
            'lightweight': 'Lightweight',
            'responsive': 'Responsive',
            'cushioned': 'Well cushioned',
            'breathable': 'Breathable',
            'durable': 'Durable',
            'stable': 'Good stability',
            'great fit': 'Great fit',
        }
        con_keywords = {
            'narrow': 'Runs narrow',
            'heavy': 'On the heavy side',
            'expensive': 'Expensive',
            'durability': 'Durability concerns',
            'hot': 'Runs hot',
            'stiff': 'Initially stiff',
            'slippery': 'Slippery on wet surfaces',
        }

        pro_counts = Counter()
        con_counts = Counter()

        for review in reviews:
            text = (review.body or '').lower()
            rating = float(review.rating) if review.rating else 3.0

            for keyword, label in pro_keywords.items():
                if keyword in text and rating >= 3.5:
                    pro_counts[label] += 1

            for keyword, label in con_keywords.items():
                if keyword in text:
                    con_counts[label] += 1

        pros = [label for label, _ in pro_counts.most_common(5)]
        cons = [label for label, _ in con_counts.most_common(5)]

        return pros, cons

    async def process_shoe(self, shoe_id: UUID) -> Dict[str, Any]:
        """
        Process a shoe: build profile and summary from all available data.

        Args:
            shoe_id: The shoe's database ID

        Returns:
            Dict with processing results
        """
        # Load shoe with all related data
        result = await self.session.execute(
            select(Shoe)
            .options(
                selectinload(Shoe.running_attributes),
                selectinload(Shoe.reviews),
                selectinload(Shoe.fit_profile),
            )
            .where(Shoe.id == shoe_id)
        )
        shoe = result.scalar_one_or_none()

        if not shoe:
            return {'success': False, 'error': 'Shoe not found'}

        processed = {'shoe_id': str(shoe_id), 'shoe_name': shoe.name}

        # Build profile from attributes
        if shoe.running_attributes:
            attrs = shoe.running_attributes
            # Convert attributes to ProductSpecs-like object
            specs = ProductSpecs(
                brand='',
                name=shoe.name,
                weight_oz=attrs.weight_oz,
                drop_mm=attrs.drop_mm,
                cushion_type=attrs.cushion_type,
                cushion_level=attrs.cushion_level,
                terrain=attrs.terrain,
                subcategory=attrs.subcategory,
                has_carbon_plate=attrs.has_carbon_plate,
                has_rocker=attrs.has_rocker,
            )
            profile = await self.build_profile_from_specs(shoe_id, specs)
            processed['profile_updated'] = True

        # Build summary from reviews
        if shoe.reviews:
            summary = await self.build_summary_from_reviews(shoe_id, list(shoe.reviews))
            processed['summary_updated'] = True
            processed['review_count'] = len(shoe.reviews)

        await self.session.commit()
        processed['success'] = True
        return processed


async def process_all_shoes(session: AsyncSession) -> List[Dict[str, Any]]:
    """Process all shoes in the database."""
    service = ProfileBuilderService(session)

    result = await session.execute(select(Shoe.id))
    shoe_ids = [row[0] for row in result.fetchall()]

    results = []
    for shoe_id in shoe_ids:
        try:
            result = await service.process_shoe(shoe_id)
            results.append(result)
            logger.info(f"Processed shoe: {result.get('shoe_name')}")
        except Exception as e:
            logger.error(f"Error processing shoe {shoe_id}: {e}")
            results.append({'shoe_id': str(shoe_id), 'success': False, 'error': str(e)})

    return results
