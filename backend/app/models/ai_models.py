"""
AI-friendly models for shoe matching and chatbot integration.

These models store processed/normalized data optimized for:
1. Matching algorithms (normalized scores, fit vectors)
2. AI/Chatbot queries (JSONB for flexible retrieval)
3. UI display (pre-computed summaries)
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ShoeProfile(Base):
    """
    Normalized shoe data optimized for matching algorithms and AI queries.

    This table contains pre-computed scores and vectors that make it easy to:
    - Find similar shoes
    - Match shoes to user preferences
    - Power chatbot recommendations
    """
    __tablename__ = "shoe_profiles"

    shoe_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shoes.id", ondelete="CASCADE"),
        primary_key=True
    )

    # Normalized scores (0-1 scale) for matching algorithms
    # These allow easy comparison across different shoes
    weight_normalized: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    cushion_normalized: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    stability_normalized: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    responsiveness_normalized: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    flexibility_normalized: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))

    # Fit vector for matching to user foot profiles
    # Values: -1 (runs small/narrow) to +1 (runs large/wide), 0 = true to size
    # Example: {"length": 0, "width_forefoot": 0.5, "width_midfoot": 0, "width_heel": -0.5}
    fit_vector: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Use case scores (0-1) for different running activities
    # Example: {"easy_runs": 0.9, "long_runs": 0.85, "tempo": 0.6, "racing": 0.3}
    use_case_scores: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Terrain compatibility scores (0-1)
    # Example: {"road": 1.0, "light_trail": 0.3, "technical_trail": 0}
    terrain_scores: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Concatenated text for full-text search
    search_text: Mapped[str | None] = mapped_column(Text)

    # Metadata
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    review_count: Mapped[int | None] = mapped_column(Integer, default=0)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationship
    shoe: Mapped["Shoe"] = relationship("Shoe", back_populates="profile")

    @classmethod
    def default_fit_vector(cls) -> Dict[str, float]:
        """Default fit vector (all true to size)."""
        return {
            "length": 0.0,
            "width_forefoot": 0.0,
            "width_midfoot": 0.0,
            "width_heel": 0.0,
            "arch_height": 0.0,
            "volume": 0.0,
        }

    @classmethod
    def default_use_case_scores(cls) -> Dict[str, float]:
        """Default use case scores."""
        return {
            "easy_runs": 0.5,
            "long_runs": 0.5,
            "tempo": 0.5,
            "intervals": 0.5,
            "racing": 0.5,
            "walking": 0.5,
            "standing": 0.5,
        }

    @classmethod
    def default_terrain_scores(cls) -> Dict[str, float]:
        """Default terrain scores."""
        return {
            "road": 1.0,
            "light_trail": 0.0,
            "technical_trail": 0.0,
            "track": 0.0,
        }


class ReviewSummary(Base):
    """
    AI-extracted summary of all reviews for a shoe.

    This table aggregates insights from multiple reviews into a structured
    format that's easy to query and display in the UI.

    Can be linked to either:
    - shoe_id (old model, legacy support)
    - product_id (new catalog model, preferred)
    """
    __tablename__ = "review_summaries"

    shoe_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shoes.id", ondelete="CASCADE"),
        primary_key=True
    )

    # Link to new catalog model (nullable for backwards compatibility)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("shoe_products.id", ondelete="SET NULL"),
        nullable=True, index=True
    )

    # Review counts
    total_reviews: Mapped[int | None] = mapped_column(Integer, default=0)
    expert_reviews: Mapped[int | None] = mapped_column(Integer, default=0)
    user_reviews: Mapped[int | None] = mapped_column(Integer, default=0)
    average_rating: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))

    # AI-extracted consensus data
    # Example:
    # {
    #   "sizing": {"verdict": "true_to_size", "confidence": 0.85, "notes": "..."},
    #   "width": {"forefoot": "normal", "midfoot": "narrow", "heel": "normal"},
    #   "comfort": {"break_in_miles": 10, "all_day_wearable": true},
    #   "durability": {"expected_miles_min": 300, "expected_miles_max": 500}
    # }
    consensus: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Sentiment scores (0-1) for different aspects
    # Example: {"overall": 0.82, "fit": 0.75, "comfort": 0.90, "durability": 0.70}
    sentiment: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Aggregated pros and cons for UI display
    # Example: ["great cushioning", "lightweight", "breathable"]
    pros: Mapped[List[str] | None] = mapped_column(JSONB, default=list)
    cons: Mapped[List[str] | None] = mapped_column(JSONB, default=list)

    # Recommendations by foot type
    # Example:
    # {
    #   "wide_feet": {"suitable": false, "notes": "Consider wide version"},
    #   "flat_feet": {"suitable": true, "notes": "Good arch support"}
    # }
    recommendations: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Notable quotes from reviews (for UI)
    # Example: [{"quote": "...", "source": "doctors_of_running", "reviewer": "Matt Klein"}]
    notable_quotes: Mapped[List[Dict] | None] = mapped_column(JSONB, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    shoe: Mapped["Shoe"] = relationship("Shoe", back_populates="review_summary")
    product: Mapped[Optional["ShoeProduct"]] = relationship("ShoeProduct", back_populates="review_summary")

    @classmethod
    def default_consensus(cls) -> Dict[str, Any]:
        """Default consensus structure."""
        return {
            "sizing": {
                "verdict": "unknown",
                "confidence": 0.0,
                "notes": None,
            },
            "width": {
                "forefoot": "unknown",
                "midfoot": "unknown",
                "heel": "unknown",
            },
            "comfort": {
                "break_in_miles": None,
                "all_day_wearable": None,
            },
            "durability": {
                "expected_miles_min": None,
                "expected_miles_max": None,
                "weak_points": [],
            },
        }

    @classmethod
    def default_recommendations(cls) -> Dict[str, Any]:
        """Default recommendations structure."""
        return {
            "wide_feet": {"suitable": None, "notes": None},
            "narrow_feet": {"suitable": None, "notes": None},
            "high_arches": {"suitable": None, "notes": None},
            "flat_feet": {"suitable": None, "notes": None},
            "overpronators": {"suitable": None, "notes": None},
            "neutral_gait": {"suitable": None, "notes": None},
        }


# Type hints for relationships (avoid circular imports)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.shoe import Shoe
