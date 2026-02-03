import os
import uuid
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models import Category, QuizSession, Recommendation
from app.models.catalog import ShoeProduct, ShoeModel, Terrain, Gender

logger = logging.getLogger(__name__)


@dataclass
class FootProfile:
    width: Optional[str] = None  # 'narrow', 'standard', 'wide'
    arch: Optional[str] = None  # 'flat', 'neutral', 'high'
    pronation: Optional[str] = None  # 'neutral', 'overpronation', 'underpronation'
    issues: list[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


@dataclass
class UserPreferences:
    priorities: list[str] = None
    budget: Optional[str] = None
    experience: Optional[str] = None
    gender: Optional[str] = None  # 'mens', 'womens'
    distances: list[str] = None  # Running
    terrain: Optional[str] = None  # Running
    position: Optional[str] = None  # Basketball
    court_type: Optional[str] = None  # Basketball
    cut_preference: Optional[str] = None  # Basketball

    def __post_init__(self):
        if self.priorities is None:
            self.priorities = []
        if self.distances is None:
            self.distances = []


@dataclass
class UserProfile:
    category: str
    foot: FootProfile
    preferences: UserPreferences
    previous_shoes: list[dict] = None

    def __post_init__(self):
        if self.previous_shoes is None:
            self.previous_shoes = []


# Default algorithm weights
DEFAULT_WEIGHTS = {
    "terrain": 2.0,
    "budget": 2.5,  # Budget is critical - don't recommend shoes people can't afford
    "pronation": 1.8,
    "issues": 1.8,
    "width": 1.5,
    "arch": 1.3,
    "priorities": 1.3,
    "cushion": 1.2,
    "distance": 1.0,
    "position": 1.0,
    "history": 0.8,
    "sentiment": 0.5,
}


class MatchingService:
    """Service for generating shoe recommendations based on quiz answers."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.weights = DEFAULT_WEIGHTS.copy()

    def _extract_user_profile(self, session: QuizSession, category_slug: str = "running") -> UserProfile:
        """Extract user profile from quiz answers."""
        answers = session.answers or {}

        # Extract foot profile
        foot_issues = answers.get("foot_issues", [])
        if isinstance(foot_issues, str):
            foot_issues = [foot_issues]

        # Infer foot characteristics from issues
        width = "standard"
        arch = "neutral"
        pronation = "neutral"

        if "wide_feet" in foot_issues:
            width = "wide"
        elif "narrow_feet" in foot_issues:
            width = "narrow"

        if "flat_feet" in foot_issues:
            arch = "flat"
        elif "high_arches" in foot_issues:
            arch = "high"

        if "overpronation" in foot_issues:
            pronation = "overpronation"
        elif "underpronation" in foot_issues:
            pronation = "underpronation"

        foot = FootProfile(
            width=width,
            arch=arch,
            pronation=pronation,
            issues=[i for i in foot_issues if i != "none"],
        )

        # Extract preferences
        priorities = answers.get("priorities", [])
        if isinstance(priorities, str):
            priorities = [priorities]

        distance = answers.get("distance", "mixed")
        distances = []
        if distance == "short":
            distances = ["5k"]
        elif distance == "mid":
            distances = ["5k", "10k", "half_marathon"]
        elif distance == "long":
            distances = ["marathon", "ultra"]
        else:
            distances = ["5k", "10k", "half_marathon", "marathon"]

        preferences = UserPreferences(
            priorities=priorities,
            budget=answers.get("budget"),
            experience=answers.get("experience"),
            gender=answers.get("gender", "mens"),  # Default to mens if not specified
            distances=distances,
            terrain=answers.get("terrain", "road"),
            position=answers.get("position"),
            court_type=answers.get("court_type"),
            cut_preference=answers.get("cut_preference"),
        )

        previous_shoes = []
        if session.previous_shoes:
            previous_shoes = session.previous_shoes if isinstance(session.previous_shoes, list) else []

        return UserProfile(
            category=category_slug,
            foot=foot,
            preferences=preferences,
            previous_shoes=previous_shoes,
        )

    def _calculate_terrain_match(self, product: ShoeProduct, user_profile: UserProfile) -> float:
        """Calculate terrain compatibility score."""
        model = product.model
        if not model or not model.terrain:
            return 0.5

        shoe_terrain = model.terrain.value if hasattr(model.terrain, 'value') else model.terrain
        user_terrain = user_profile.preferences.terrain

        if user_terrain == "mixed":
            return 0.8  # Any terrain works

        if shoe_terrain == user_terrain:
            return 1.0

        # Cross-terrain compatibility
        compatibility = {
            ("road", "treadmill"): 0.9,
            ("treadmill", "road"): 0.9,
            ("road", "track"): 0.7,
            ("track", "road"): 0.7,
            ("trail", "road"): 0.4,
            ("road", "trail"): 0.4,
        }

        return compatibility.get((shoe_terrain, user_terrain), 0.3)

    def _calculate_width_match(self, product: ShoeProduct, user_profile: UserProfile) -> float:
        """Calculate width compatibility score."""
        # Check if width options are available on the product
        width_options = product.width_options or []
        user_width = user_profile.foot.width or "standard"

        # If product has explicit width options
        if width_options:
            has_wide = any("wide" in w.lower() or "2e" in w.lower() or "4e" in w.lower() for w in width_options)
            has_narrow = any("narrow" in w.lower() or "2a" in w.lower() for w in width_options)

            if user_width == "wide" and has_wide:
                return 1.0
            elif user_width == "narrow" and has_narrow:
                return 1.0
            elif user_width == "standard":
                return 0.9  # Standard width available for most

        # Default scoring based on typical fit
        return 0.6  # Neutral score when width info not available

    def _calculate_arch_match(self, product: ShoeProduct, user_profile: UserProfile) -> float:
        """Calculate arch support compatibility."""
        model = product.model
        user_arch = user_profile.foot.arch or "neutral"

        # Use support type from model if available
        if model and model.support_type:
            support_type = model.support_type.value if hasattr(model.support_type, 'value') else model.support_type

            # Stability shoes are good for flat feet/overpronation
            if support_type == "stability":
                if user_arch == "flat":
                    return 1.0
                elif user_arch == "neutral":
                    return 0.7
                else:  # high
                    return 0.4

            # Neutral shoes work for most
            elif support_type == "neutral":
                if user_arch == "neutral":
                    return 1.0
                elif user_arch == "high":
                    return 0.8
                else:  # flat
                    return 0.5

        # Default neutral score
        return 0.6

    def _calculate_pronation_match(self, product: ShoeProduct, user_profile: UserProfile) -> float:
        """Calculate pronation support match."""
        model = product.model
        user_pronation = user_profile.foot.pronation or "neutral"

        # Use support type from model if available
        support_type = None
        if model and model.support_type:
            support_type = model.support_type.value if hasattr(model.support_type, 'value') else model.support_type

        # INFER stability from shoe name if support_type not populated
        # These are well-known stability shoes
        name_lower = product.name.lower()
        stability_keywords = [
            'gt-2000', 'gt-1000', 'gt 2000', 'gt 1000',  # ASICS GT series
            'kayano', 'gel-kayano',  # ASICS Kayano
            'adrenaline', 'ariel',  # Brooks stability
            'gts',  # Brooks GTS (Go-To-Shoe for support)
            '860', '840', '1540',  # New Balance stability numbers
            'vongo',  # New Balance Vongo
            'guide',  # Saucony Guide
            'hurricane',  # Saucony Hurricane
            'structure',  # Nike Structure
            'support',  # Generic
            'stability',  # Generic
            'motion control',
        ]
        is_stability_shoe = any(kw in name_lower for kw in stability_keywords)

        # Racing/speed shoes are neutral and NOT for overpronation
        racing_keywords = [
            'vaporfly', 'alphafly', 'streakfly',  # Nike racing
            'metaspeed', 'magic speed',  # ASICS racing
            'endorphin pro', 'endorphin elite',  # Saucony racing
            'adios pro', 'prime x',  # Adidas racing
            'hyperion elite', 'hyperion tempo',  # Brooks racing
            'rocket x', 'cielo x', 'mach x',  # Hoka racing
            'fuelcell supercomp', 'fuelcell rc',  # New Balance racing
            'takumi',  # ASICS Takumi
            'spike', 'spikes',  # Track spikes
        ]
        is_racing_shoe = any(kw in name_lower for kw in racing_keywords)

        # Override with inferred support type
        if is_stability_shoe:
            support_type = "stability"
        elif is_racing_shoe:
            support_type = "neutral"  # Racing shoes are always neutral

        # Scoring based on support type
        if support_type == "stability":
            if user_pronation == "overpronation":
                return 1.0  # Perfect match
            elif user_pronation == "neutral":
                return 0.6  # Okay but not ideal
            else:  # underpronation
                return 0.3  # Bad match

        elif support_type == "motion_control":
            if user_pronation == "overpronation":
                return 0.9
            elif user_pronation == "neutral":
                return 0.4
            else:
                return 0.2

        # Neutral shoes (or unknown)
        else:
            if user_pronation == "neutral":
                return 1.0
            elif user_pronation == "underpronation":
                return 0.9  # Cushioned neutral shoes good for supinators
            else:  # overpronation - neutral shoes are NOT good
                return 0.3  # Penalize neutral shoes for overpronators

        return 0.5

    def _calculate_issue_compatibility(self, product: ShoeProduct, user_profile: UserProfile) -> float:
        """Check if shoe works for or should be avoided given foot issues."""
        issues = user_profile.foot.issues
        if not issues:
            return 1.0

        model = product.model
        score = 1.0

        # Use model attributes to infer compatibility
        if model:
            # Wide feet - check width options
            if "wide_feet" in issues:
                width_options = product.width_options or []
                has_wide = any("wide" in w.lower() or "2e" in w.lower() or "4e" in w.lower() for w in width_options)
                if has_wide:
                    score *= 1.2
                else:
                    score *= 0.7

            # Overpronation - stability shoes help
            if "overpronation" in issues:
                support_type = model.support_type.value if model.support_type and hasattr(model.support_type, 'value') else None
                if support_type == "stability":
                    score *= 1.3
                elif support_type == "neutral":
                    score *= 0.6

            # High arches - cushioned neutral shoes
            if "high_arches" in issues:
                cushion_level = model.cushion_level
                if cushion_level in ["max", "high"]:
                    score *= 1.2

            # Plantar fasciitis - need good cushion and arch support
            if "plantar_fasciitis" in issues:
                cushion_level = model.cushion_level
                if cushion_level in ["max", "high"]:
                    score *= 1.2
                else:
                    score *= 0.8

        return min(max(score, 0.1), 1.0)

    def _calculate_cushion_match(self, product: ShoeProduct, user_profile: UserProfile) -> float:
        """Calculate cushioning preference match."""
        if "cushion" not in user_profile.preferences.priorities:
            return 0.5  # Not a priority

        model = product.model
        cushion_level = model.cushion_level if model else None

        # If we have explicit cushion data, use it
        if cushion_level:
            cushion_scores = {
                "max": 1.0,
                "high": 1.0,
                "moderate": 0.7,
                "balanced": 0.7,
                "light": 0.4,
                "minimal": 0.3,
            }
            return cushion_scores.get(cushion_level.lower(), 0.5)

        # INFER cushioning from specs we DO have
        # Heavier shoes with higher stack = more cushioned
        score = 0.5

        if product.weight_oz:
            weight = float(product.weight_oz)
            if weight >= 11:
                score += 0.25  # Heavy = likely well cushioned
            elif weight >= 9.5:
                score += 0.15
            elif weight < 8:
                score -= 0.15  # Light = likely minimal

        if product.stack_height_heel_mm:
            stack = float(product.stack_height_heel_mm)
            if stack >= 35:
                score += 0.25  # High stack = max cushion
            elif stack >= 30:
                score += 0.15
            elif stack < 25:
                score -= 0.1

        return min(max(score, 0.2), 1.0)

    def _calculate_priority_match(self, product: ShoeProduct, user_profile: UserProfile) -> float:
        """Calculate how well shoe matches user priorities."""
        priorities = user_profile.preferences.priorities
        if not priorities:
            return 0.5

        model = product.model
        score = 0.5

        for priority in priorities:
            if priority == "speed":
                # INFER speed from weight - lighter = faster
                if product.weight_oz:
                    weight = float(product.weight_oz)
                    if weight < 7.5:
                        score += 0.3  # Racing weight
                    elif weight < 8.5:
                        score += 0.2  # Lightweight
                    elif weight < 9.5:
                        score += 0.1
                    elif weight > 11:
                        score -= 0.1  # Heavy = not for speed

                # Lower drop often = more responsive
                if product.drop_mm:
                    drop = float(product.drop_mm)
                    if drop <= 6:
                        score += 0.1

            elif priority == "stability" or priority == "support":
                # INFER stability - heavier, higher drop shoes tend to be more stable
                if product.weight_oz:
                    weight = float(product.weight_oz)
                    if weight >= 10:
                        score += 0.15  # Substantial = likely stable

                if product.drop_mm:
                    drop = float(product.drop_mm)
                    if drop >= 8:
                        score += 0.1  # Higher drop = more traditional/stable

                # Check for stability keywords in name
                name_lower = product.name.lower()
                if any(kw in name_lower for kw in ['gt-', 'gts', 'stability', 'guide', 'adrenaline', 'kayano', 'vongo', '860', '1080']):
                    score += 0.25

            elif priority == "durability":
                # Heavier shoes tend to be more durable
                if product.weight_oz and float(product.weight_oz) > 10:
                    score += 0.15
                # Trail shoes are typically more durable
                if model and model.terrain:
                    terrain = model.terrain.value if hasattr(model.terrain, 'value') else model.terrain
                    if terrain == "trail":
                        score += 0.2

            elif priority == "cushion":
                # INFER cushion from weight and stack
                if product.weight_oz:
                    weight = float(product.weight_oz)
                    if weight >= 10.5:
                        score += 0.2
                    elif weight >= 9:
                        score += 0.1

                if product.stack_height_heel_mm:
                    stack = float(product.stack_height_heel_mm)
                    if stack >= 35:
                        score += 0.2
                    elif stack >= 30:
                        score += 0.1

                # Check for cushion keywords in name
                name_lower = product.name.lower()
                if any(kw in name_lower for kw in ['glycerin', 'triumph', 'clifton', 'bondi', 'ghost', 'nimbus', '1080', 'fresh foam', 'invincible']):
                    score += 0.15

        return min(score, 1.0)

    def _calculate_distance_match(self, product: ShoeProduct, user_profile: UserProfile) -> float:
        """Calculate distance compatibility for running shoes."""
        model = product.model
        user_distances = user_profile.preferences.distances or []

        if not user_distances:
            return 0.5

        # Use shoe category if available
        if model and model.category:
            category = model.category.value if hasattr(model.category, 'value') else model.category
            if category == "racing":
                if "5k" in user_distances or "10k" in user_distances:
                    return 0.9
                return 0.6
            elif category == "long_run":
                if "marathon" in user_distances or "ultra" in user_distances:
                    return 1.0
                return 0.7
            elif category == "daily_trainer":
                return 0.8

        # INFER distance suitability from specs
        score = 0.6

        # Short distances (5k) - prefer lighter, lower drop
        if "5k" in user_distances and "marathon" not in user_distances:
            if product.weight_oz:
                weight = float(product.weight_oz)
                if weight < 8:
                    score += 0.2
                elif weight < 9:
                    score += 0.1
                elif weight > 11:
                    score -= 0.1

        # Long distances (marathon/ultra) - prefer cushioned, heavier is ok
        if "marathon" in user_distances or "ultra" in user_distances:
            if product.weight_oz:
                weight = float(product.weight_oz)
                if weight >= 9 and weight <= 11:
                    score += 0.15  # Sweet spot for marathon
                elif weight > 11:
                    score += 0.1  # Max cushion ok for ultras

            if product.stack_height_heel_mm:
                stack = float(product.stack_height_heel_mm)
                if stack >= 30:
                    score += 0.15  # Good cushion for long runs

        # Check for distance keywords in name
        name_lower = product.name.lower()
        if "marathon" in user_distances or "ultra" in user_distances:
            if any(kw in name_lower for kw in ['endorphin', 'vaporfly', 'alphafly', 'metaspeed', 'adios', 'prime x', 'rocket']):
                score += 0.15

        return min(max(score, 0.3), 1.0)

    def _calculate_position_match(self, product: ShoeProduct, user_profile: UserProfile) -> float:
        """Calculate position/playstyle match for basketball shoes."""
        # Basketball not currently in new catalog, return neutral score
        return 0.5

    def _calculate_budget_match(self, product: ShoeProduct, user_profile: UserProfile) -> float:
        """Calculate budget compatibility."""
        budget = user_profile.preferences.budget
        if not budget or budget == "any":
            return 1.0

        # Get best price from offers or fall back to MSRP
        prices = []
        if product.offers:
            prices = [float(o.price) for o in product.offers if o.price and o.in_stock]
        price = min(prices) if prices else (float(product.msrp_usd) if product.msrp_usd else None)

        if not price:
            return 0.5

        budget_ranges = {
            "under_100": (0, 100),
            "100_150": (100, 150),
            "150_200": (150, 200),
            "150_plus": (150, 500),
        }

        min_price, max_price = budget_ranges.get(budget, (0, 500))

        if min_price <= price <= max_price:
            return 1.0
        elif price < min_price:
            return 0.95  # Under budget is great
        else:
            # Over budget - AGGRESSIVE penalty
            # $150 shoe when budget is $100 = 50% over = very low score
            over_amount = price - max_price
            over_percent = over_amount / max_price

            if over_percent > 0.5:
                return 0.1  # Way over budget - nearly disqualify
            elif over_percent > 0.25:
                return 0.2  # Significantly over budget
            else:
                return max(0.3, 0.8 - over_percent * 2)  # Slightly over

    def _calculate_court_match(self, product: ShoeProduct, user_profile: UserProfile) -> float:
        """Calculate court type match for basketball shoes."""
        # Basketball not currently in new catalog
        return 0.5

    def _calculate_cut_match(self, product: ShoeProduct, user_profile: UserProfile) -> float:
        """Calculate cut preference match for basketball shoes."""
        # Basketball not currently in new catalog
        return 0.5

    def calculate_match_score(self, product: ShoeProduct, user_profile: UserProfile) -> tuple[float, dict]:
        """Calculate overall match score for a shoe product."""
        scores = {}

        # Category-specific scoring
        if user_profile.category == "running":
            scores["terrain"] = self._calculate_terrain_match(product, user_profile)
            scores["pronation"] = self._calculate_pronation_match(product, user_profile)
            scores["distance"] = self._calculate_distance_match(product, user_profile)
        else:  # basketball
            scores["position"] = self._calculate_position_match(product, user_profile)
            scores["court"] = self._calculate_court_match(product, user_profile)
            scores["cut"] = self._calculate_cut_match(product, user_profile)

        # Common scoring
        scores["width"] = self._calculate_width_match(product, user_profile)
        scores["arch"] = self._calculate_arch_match(product, user_profile)
        scores["issues"] = self._calculate_issue_compatibility(product, user_profile)
        scores["cushion"] = self._calculate_cushion_match(product, user_profile)
        scores["priorities"] = self._calculate_priority_match(product, user_profile)
        scores["budget"] = self._calculate_budget_match(product, user_profile)

        # Default sentiment score (could be enhanced with review summary data)
        scores["sentiment"] = 0.5

        # Weighted combination
        total_weight = 0
        weighted_sum = 0

        for key, score in scores.items():
            weight = self.weights.get(key, 1.0)
            weighted_sum += score * weight
            total_weight += weight

        final_score = weighted_sum / total_weight if total_weight > 0 else 0.5

        return final_score, scores

    def _generate_reasoning(self, product: ShoeProduct, user_profile: UserProfile, scores: dict) -> str:
        """Generate human-readable explanation for recommendation based on shoe-specific features."""
        reasons = []
        model = product.model
        brand_name = model.brand.name if model and model.brand else ""
        model_name = model.name if model else product.name.split()[-1] if product.name else ""

        # Spec-based reasons first (most reliable data)
        if product.weight_oz:
            weight = float(product.weight_oz)
            if weight < 7.5:
                reasons.append(f"is ultralight at just {weight}oz")
            elif weight < 9:
                reasons.append(f"is lightweight at {weight}oz")
            elif weight > 11:
                reasons.append(f"has substantial cushioning at {weight}oz")

        if product.drop_mm:
            drop = float(product.drop_mm)
            if drop == 0:
                reasons.append("has zero drop for natural foot positioning")
            elif drop <= 4:
                reasons.append(f"features a low {drop}mm drop for midfoot strikers")
            elif drop >= 10:
                reasons.append(f"has a traditional {drop}mm drop for heel strikers")

        # Stack height for cushion inference
        if product.stack_height_heel_mm:
            stack = float(product.stack_height_heel_mm)
            if stack >= 35:
                reasons.append("delivers maximum cushioning with high stack height")
            elif stack >= 28:
                reasons.append("offers well-cushioned landings")

        # Model-level features (only use if data seems reliable)
        if model:
            # Category-specific (more reliable than boolean flags)
            if model.category:
                cat = model.category.value if hasattr(model.category, 'value') else model.category
                if cat == "racing":
                    reasons.append("is built for race day speed")
                elif cat == "daily_trainer":
                    reasons.append("is a versatile everyday trainer")
                elif cat == "long_run":
                    reasons.append("excels on long distance runs")
                elif cat == "tempo":
                    reasons.append("is designed for tempo and speed work")
                elif cat == "recovery":
                    reasons.append("is perfect for easy recovery miles")
                elif cat == "trail":
                    reasons.append("is built to handle technical terrain")

            # Support type
            if model.support_type:
                support = model.support_type.value if hasattr(model.support_type, 'value') else model.support_type
                if support == "stability" and user_profile.foot.pronation == "overpronation":
                    reasons.append("provides stability features you need")

            # Terrain match
            if model.terrain:
                terrain = model.terrain.value if hasattr(model.terrain, 'value') else model.terrain
                if terrain == "trail":
                    reasons.append("has aggressive traction for trails")

        # Width options
        width_options = product.width_options or []
        if len(width_options) > 2:
            reasons.append(f"comes in {len(width_options)} width options")
        elif any("wide" in w.lower() or "2e" in w.lower() or "4e" in w.lower() for w in width_options):
            if user_profile.foot.width == "wide":
                reasons.append("offers the wide width you need")

        # Price-based reasons as fallback
        if len(reasons) < 2:
            if product.msrp_usd:
                price = float(product.msrp_usd)
                if price < 130:
                    reasons.append("offers great value for the price")
                elif price > 200:
                    reasons.append("is a premium performance option")

            # Match score based
            if scores.get("budget", 0) > 0.95:
                reasons.append("fits perfectly within your budget")

        # Build final reasoning - use first 2 unique reasons
        reasons = reasons[:2]
        if len(reasons) >= 2:
            return f"The {brand_name} {model_name} {reasons[0]} and {reasons[1]}."
        elif reasons:
            return f"The {brand_name} {model_name} {reasons[0]}."
        else:
            return f"A solid choice from {brand_name} that matches your running profile."

    def _format_merchant_name(self, merchant: str) -> str:
        """Format merchant slug to display name."""
        merchant_names = {
            "running_warehouse": "Running Warehouse",
            "runningwarehouse": "Running Warehouse",
            "fleet_feet": "Fleet Feet",
            "jackrabbit": "JackRabbit",
            "roadrunnersports": "Road Runner Sports",
            "zappos": "Zappos",
            "amazon": "Amazon",
            "rei": "REI",
            "dickssportinggoods": "Dick's Sporting Goods",
        }
        return merchant_names.get(merchant.lower().replace(" ", "_"), merchant.replace("_", " ").title())

    def _generate_fit_notes(self, product: ShoeProduct, user_profile: UserProfile) -> dict:
        """Generate fit notes for a shoe recommendation."""
        model = product.model
        fit_notes = {
            "sizing": "True to size for most",
            "width": "Standard width",
            "highlights": [],
            "considerations": [],
        }

        # Width options
        width_options = product.width_options or []
        if width_options:
            if len(width_options) > 1:
                fit_notes["width"] = f"Available in {len(width_options)} widths"
            elif any("wide" in w.lower() for w in width_options):
                fit_notes["width"] = "Wide width available"

        # Highlights from model attributes
        if model:
            if model.has_carbon_plate:
                fit_notes["highlights"].append("Carbon fiber plate for energy return")

            if model.has_rocker:
                fit_notes["highlights"].append("Rocker geometry for smooth transitions")

            if model.cushion_level and model.cushion_level.lower() in ["max", "high"]:
                fit_notes["highlights"].append("Maximum cushioning")

            if model.key_features:
                for feature in model.key_features[:2]:
                    if feature not in fit_notes["highlights"]:
                        fit_notes["highlights"].append(feature)

        # Specs as highlights
        if product.weight_oz:
            weight = float(product.weight_oz)
            if weight < 8:
                fit_notes["highlights"].append(f"Lightweight at {weight}oz")
            elif weight > 11:
                fit_notes["considerations"].append(f"Heavier at {weight}oz")

        if product.drop_mm:
            drop = float(product.drop_mm)
            if drop <= 4:
                fit_notes["considerations"].append(f"Low drop ({drop}mm)")
            elif drop >= 10:
                fit_notes["highlights"].append(f"Traditional drop ({drop}mm)")

        return fit_notes

    def _build_llm_rerank_prompt(self, user_profile: UserProfile, candidates: list[dict]) -> str:
        """Build prompt for LLM to re-rank shoe candidates."""
        profile_text = f"""
USER PROFILE:
- Pronation: {user_profile.foot.pronation or 'neutral'}
- Foot width: {user_profile.foot.width or 'standard'}
- Arch type: {user_profile.foot.arch or 'neutral'}
- Foot issues: {', '.join(user_profile.foot.issues) if user_profile.foot.issues else 'None'}
- Budget: {user_profile.preferences.budget or 'any'}
- Terrain: {user_profile.preferences.terrain or 'road'}
- Priorities: {', '.join(user_profile.preferences.priorities) if user_profile.preferences.priorities else 'None'}
"""

        candidates_text = ""
        for i, shoe in enumerate(candidates, 1):
            candidates_text += f"""
SHOE {i}: {shoe['brand']} {shoe['name']}
- Price: ${shoe.get('price', 'Unknown')}
- Weight: {shoe.get('weight_oz', 'Unknown')}oz
- Drop: {shoe.get('drop_mm', 'Unknown')}mm
- Heuristic score: {shoe.get('score', 0):.0%}
"""

        return f"""You are a running shoe expert. Re-rank these candidate shoes for this user.

CRITICAL RULES:
1. NEVER recommend shoes over the user's budget as top picks
2. Overpronators NEED stability shoes (GTS, Kayano, Guide, GT-2000, Vongo, 860)
3. Match terrain and distance preferences

{profile_text}

CANDIDATES:
{candidates_text}

Return JSON only:
{{"rankings": [{{"rank": 1, "shoe_index": <1-10>, "shoe_name": "Brand Model", "score": 0.95, "reasoning": "Brief why"}}], "disqualified": [{{"shoe_index": <n>, "shoe_name": "Brand Model", "reason": "Why not recommended"}}]}}
"""

    async def _llm_refine_candidates(
        self,
        candidates: list[tuple[ShoeProduct, float, dict]],
        user_profile: UserProfile
    ) -> list[tuple[ShoeProduct, float, dict, Optional[str]]]:
        """Use LLM to refine/re-rank the top candidates."""
        # Check if LLM is enabled
        llm_provider_name = os.getenv("LLM_PROVIDER", "none").lower()
        if llm_provider_name == "none":
            # Return candidates unchanged with no LLM reasoning
            return [(p, s, c, None) for p, s, c in candidates]

        try:
            from app.services.llm_provider import get_llm_provider, extract_json_from_response

            provider = get_llm_provider()

            # Format candidates for LLM
            candidate_data = []
            for product, score, component_scores in candidates:
                model = product.model
                prices = [float(o.price) for o in (product.offers or []) if o.price and o.in_stock]
                price = min(prices) if prices else (float(product.msrp_usd) if product.msrp_usd else None)

                candidate_data.append({
                    "brand": model.brand.name if model and model.brand else "Unknown",
                    "name": product.name,
                    "price": price,
                    "weight_oz": float(product.weight_oz) if product.weight_oz else None,
                    "drop_mm": float(product.drop_mm) if product.drop_mm else None,
                    "score": score,
                })

            prompt = self._build_llm_rerank_prompt(user_profile, candidate_data)
            response = await provider.generate(prompt, max_tokens=1000)

            if not response:
                logger.warning("LLM returned empty response, using heuristic ranking")
                return [(p, s, c, None) for p, s, c in candidates]

            parsed = extract_json_from_response(response)
            if not parsed or "rankings" not in parsed:
                logger.warning("Could not parse LLM response, using heuristic ranking")
                return [(p, s, c, None) for p, s, c in candidates]

            # Re-order based on LLM rankings
            rankings = parsed.get("rankings", [])
            disqualified_indices = {d.get("shoe_index") for d in parsed.get("disqualified", [])}

            reordered = []
            used_indices = set()

            # First, add LLM-ranked shoes in order
            for item in rankings:
                idx = item.get("shoe_index")
                if idx and 1 <= idx <= len(candidates) and idx not in used_indices:
                    actual_idx = idx - 1  # Convert to 0-indexed
                    if actual_idx not in disqualified_indices:
                        product, score, component_scores = candidates[actual_idx]
                        llm_reasoning = item.get("reasoning")
                        # Use LLM's score if provided, otherwise keep heuristic
                        llm_score = item.get("score", score)
                        reordered.append((product, llm_score, component_scores, llm_reasoning))
                        used_indices.add(idx)

            # Fill remaining slots with heuristic-ranked shoes not yet included
            for i, (product, score, component_scores) in enumerate(candidates):
                if (i + 1) not in used_indices and (i + 1) not in disqualified_indices:
                    reordered.append((product, score, component_scores, None))

            logger.info(f"LLM refined {len(candidates)} candidates, {len(disqualified_indices)} disqualified")
            return reordered[:5]  # Return top 5

        except Exception as e:
            logger.error(f"LLM refinement failed: {e}, using heuristic ranking")
            return [(p, s, c, None) for p, s, c in candidates]

    async def generate_recommendations(self, session: QuizSession) -> dict:
        """Generate shoe recommendations for a quiz session."""
        # Get category slug first (before extracting user profile)
        category_result = await self.db.execute(
            select(Category).where(Category.id == session.category_id)
        )
        category = category_result.scalar_one_or_none()
        category_slug = category.slug if category else "running"

        # Extract user profile with category slug
        user_profile = self._extract_user_profile(session, category_slug)

        # Get all active shoe products with their models
        # Filter by terrain and gender that matches user preferences
        query = select(ShoeProduct).where(
            ShoeProduct.is_active == True,
        ).join(ShoeModel).options(
            selectinload(ShoeProduct.model).selectinload(ShoeModel.brand),
            selectinload(ShoeProduct.offers),
        )

        # Filter by gender - include unisex for both mens and womens
        user_gender = user_profile.preferences.gender
        if user_gender:
            gender_map = {
                "mens": Gender.MENS,
                "womens": Gender.WOMENS,
            }
            gender_enum = gender_map.get(user_gender)
            if gender_enum:
                # Include the specified gender OR unisex shoes
                query = query.where(
                    (ShoeModel.gender == gender_enum) | (ShoeModel.gender == Gender.UNISEX)
                )

        # Filter by terrain based on user preference
        user_terrain = user_profile.preferences.terrain
        if user_terrain and user_terrain != "mixed":
            # Map string terrain to enum
            terrain_map = {
                "road": Terrain.ROAD,
                "trail": Terrain.TRAIL,
                "track": Terrain.TRACK,
                "treadmill": Terrain.ROAD,  # Treadmill users can use road shoes
            }
            terrain_enum = terrain_map.get(user_terrain)
            if terrain_enum:
                query = query.where(ShoeModel.terrain == terrain_enum)

        result = await self.db.execute(query)
        products = result.scalars().all()

        # Score all products
        scored_products = []
        for product in products:
            score, component_scores = self.calculate_match_score(product, user_profile)
            scored_products.append((product, score, component_scores))

        # Sort by score
        scored_products.sort(key=lambda x: x[1], reverse=True)

        # Take top 10 for LLM refinement (will narrow to 5)
        top_candidates = scored_products[:10]

        # Optional LLM refinement - re-ranks and may disqualify some
        refined_products = await self._llm_refine_candidates(top_candidates, user_profile)

        # Build response
        recommended_shoes = []
        for rank, (product, score, component_scores, llm_reasoning) in enumerate(refined_products[:5], 1):
            # Use LLM reasoning if available, otherwise generate heuristic reasoning
            reasoning = llm_reasoning or self._generate_reasoning(product, user_profile, component_scores)
            fit_notes = self._generate_fit_notes(product, user_profile)

            # Get retailer links from offers (sorted by price)
            offer_list = sorted(
                [o for o in (product.offers or []) if o.in_stock and (o.price or o.sale_price)],
                key=lambda o: float(o.sale_price or o.price or 999)
            )

            retailer_links = [
                {
                    "retailer": self._format_merchant_name(offer.merchant),
                    "url": offer.affiliate_url or offer.url,
                    "price": float(offer.sale_price or offer.price) if (offer.sale_price or offer.price) else None,
                    "on_sale": offer.sale_price is not None and offer.sale_price < (offer.price or offer.sale_price),
                }
                for offer in offer_list[:5]  # Limit to top 5 retailers
            ]

            # Get best price from offers
            prices = [float(o.sale_price or o.price) for o in offer_list if (o.sale_price or o.price)]
            current_price_min = min(prices) if prices else None
            current_price_max = max(prices) if prices else None

            model = product.model
            brand_name = model.brand.name if model and model.brand else "Unknown"

            # Get the best link (lowest price or first available)
            best_link = retailer_links[0]["url"] if retailer_links else product.canonical_url

            recommended_shoes.append({
                "rank": rank,
                "shoe": {
                    "id": str(product.id),
                    "brand": brand_name,
                    "name": product.name,
                    "full_name": f"{brand_name} {model.name if model else ''}" if model else product.name,
                    "primary_image_url": product.primary_image_url,
                    "image_urls": product.image_urls[:4] if product.image_urls else [],  # Up to 4 images
                    "msrp_usd": float(product.msrp_usd) if product.msrp_usd else None,
                    "current_price_min": current_price_min,
                    "current_price_max": current_price_max,
                    "best_deal_url": best_link,
                    "colorway": product.colorway,
                    # Key specs for display
                    "specs": {
                        "weight_oz": float(product.weight_oz) if product.weight_oz else None,
                        "drop_mm": float(product.drop_mm) if product.drop_mm else None,
                        "stack_heel_mm": float(product.stack_height_heel_mm) if product.stack_height_heel_mm else None,
                        "stack_forefoot_mm": float(product.stack_height_forefoot_mm) if product.stack_height_forefoot_mm else None,
                    },
                },
                "match_score": round(score, 2),
                "match_percentage": round(score * 100),
                "reasoning": reasoning,
                "fit_notes": fit_notes,
                "buy_links": retailer_links,
            })

        # Create recommendation record
        recommendation = Recommendation(
            quiz_session_id=session.id,
            recommended_shoes=recommended_shoes,
            algorithm_version="2.0",  # New version using ShoeProduct
            model_weights=self.weights,
        )

        self.db.add(recommendation)
        await self.db.commit()
        await self.db.refresh(recommendation)

        return {
            "recommendation_id": recommendation.id,
            "shoes": recommended_shoes,
            "not_recommended": [],
        }
