"""
3-Layer Catalog Data Model

Layer 1: ShoeModel (concept) - e.g., "Pegasus", "Clifton"
Layer 2: ShoeProduct (version/colorway) - e.g., "Pegasus 41", "Pegasus 41 Blue/White"
Layer 3: ShoeOffer (merchant listing) - e.g., Running Warehouse listing with price/stock

This structure allows:
- Deduplication across sources
- Tracking multiple colorways/versions
- Price comparison across retailers
- Historical price tracking
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String, Integer, Boolean, DateTime, ForeignKey, Numeric, Text,
    ARRAY, JSON, UniqueConstraint, Index, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
import enum

from app.core.database import Base


# ============================================================================
# ENUMS
# ============================================================================

class Gender(str, enum.Enum):
    MENS = "mens"
    WOMENS = "womens"
    UNISEX = "unisex"
    KIDS = "kids"


class Terrain(str, enum.Enum):
    ROAD = "road"
    TRAIL = "trail"
    TRACK = "track"
    HYBRID = "hybrid"


class SupportType(str, enum.Enum):
    NEUTRAL = "neutral"
    STABILITY = "stability"
    MOTION_CONTROL = "motion_control"


class ShoeCategory(str, enum.Enum):
    DAILY_TRAINER = "daily_trainer"
    RACING = "racing"
    TEMPO = "tempo"
    LONG_RUN = "long_run"
    RECOVERY = "recovery"
    TRAIL = "trail"
    TRACK_SPIKE = "track_spike"


# ============================================================================
# LAYER 1: SHOE MODEL (Concept)
# ============================================================================

class ShoeModel(Base):
    """
    A shoe model represents a conceptual product line.
    Example: Nike Pegasus, Hoka Clifton, Brooks Ghost

    This is the canonical "master" record for a shoe family.
    """
    __tablename__ = "shoe_models"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id"), nullable=False)

    # Canonical name (normalized)
    name: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g., "Pegasus"
    slug: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g., "pegasus"

    # Classification
    # Note: create_type=False because enums are created in migration, values_callable for lowercase values
    gender: Mapped[Gender] = mapped_column(
        SQLEnum(Gender, values_callable=lambda e: [m.value for m in e], create_type=False),
        nullable=False
    )
    terrain: Mapped[Terrain] = mapped_column(
        SQLEnum(Terrain, values_callable=lambda e: [m.value for m in e], create_type=False),
        default=Terrain.ROAD
    )
    support_type: Mapped[SupportType | None] = mapped_column(
        SQLEnum(SupportType, values_callable=lambda e: [m.value for m in e], create_type=False)
    )
    category: Mapped[ShoeCategory | None] = mapped_column(
        SQLEnum(ShoeCategory, values_callable=lambda e: [m.value for m in e], create_type=False)
    )

    # Description (AI-generated or from brand)
    description: Mapped[str | None] = mapped_column(Text)
    key_features: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    # Typical specs (may vary by version)
    typical_weight_oz: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    typical_drop_mm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    typical_stack_heel_mm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    typical_stack_forefoot_mm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))

    # Features
    has_carbon_plate: Mapped[bool] = mapped_column(Boolean, default=False)
    has_rocker: Mapped[bool] = mapped_column(Boolean, default=False)
    cushion_type: Mapped[str | None] = mapped_column(String(100))
    cushion_level: Mapped[str | None] = mapped_column(String(50))

    # Embedding for semantic search (optional)
    description_embedding: Mapped[list | None] = mapped_column(ARRAY(Numeric))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    first_release_year: Mapped[int | None] = mapped_column(Integer)
    is_discontinued: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    brand: Mapped["Brand"] = relationship("Brand")
    products: Mapped[List["ShoeProduct"]] = relationship("ShoeProduct", back_populates="model", cascade="all, delete-orphan")
    name_aliases: Mapped[List["ShoeModelAlias"]] = relationship("ShoeModelAlias", back_populates="model", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("brand_id", "slug", "gender", name="uq_model_brand_slug_gender"),
        Index("ix_shoe_models_brand", "brand_id"),
        Index("ix_shoe_models_terrain", "terrain"),
    )


class ShoeModelAlias(Base):
    """
    Alternative names for a shoe model to help with matching.
    Example: "Pegasus 41" might also be "Air Zoom Pegasus 41"
    """
    __tablename__ = "shoe_model_aliases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shoe_models.id", ondelete="CASCADE"), nullable=False)

    alias: Mapped[str] = mapped_column(String(300), nullable=False)
    alias_normalized: Mapped[str] = mapped_column(String(300), nullable=False)  # Lowercased, stripped
    source: Mapped[str | None] = mapped_column(String(100))  # Where this alias was found

    model: Mapped["ShoeModel"] = relationship("ShoeModel", back_populates="name_aliases")

    __table_args__ = (
        UniqueConstraint("model_id", "alias_normalized", name="uq_model_alias"),
        Index("ix_model_aliases_normalized", "alias_normalized"),
    )


# ============================================================================
# LAYER 2: SHOE PRODUCT (Version / Colorway)
# ============================================================================

class ShoeProduct(Base):
    """
    A specific version/colorway of a shoe model.
    Example: Nike Pegasus 41 in "Wolf Grey/Black"

    This represents a unique SKU or product listing.
    """
    __tablename__ = "shoe_products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shoe_models.id", ondelete="CASCADE"), nullable=False)

    # Full product name
    name: Mapped[str] = mapped_column(String(300), nullable=False)  # e.g., "Nike Pegasus 41"
    slug: Mapped[str] = mapped_column(String(300), nullable=False)

    # Version info
    version: Mapped[str | None] = mapped_column(String(20))  # e.g., "41", "v3"
    release_year: Mapped[int | None] = mapped_column(Integer)
    colorway: Mapped[str | None] = mapped_column(String(200))  # e.g., "Wolf Grey/Black"
    style_id: Mapped[str | None] = mapped_column(String(100))  # Brand's SKU/style number

    # Specs for this specific version (may differ from model typical)
    weight_oz: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    drop_mm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    stack_height_heel_mm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    stack_height_forefoot_mm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))

    # Pricing
    msrp_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    # Images
    primary_image_url: Mapped[str | None] = mapped_column(String(500))
    image_urls: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    # Availability
    width_options: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    is_discontinued: Mapped[bool] = mapped_column(Boolean, default=False)

    # Source tracking
    canonical_url: Mapped[str | None] = mapped_column(String(1000))  # Brand's official URL
    discovered_from: Mapped[str | None] = mapped_column(String(500))  # Sitemap, retailer, etc.
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    model: Mapped["ShoeModel"] = relationship("ShoeModel", back_populates="products")
    offers: Mapped[List["ShoeOffer"]] = relationship("ShoeOffer", back_populates="product", cascade="all, delete-orphan")
    reviews: Mapped[List["ShoeReview"]] = relationship("ShoeReview", back_populates="product")
    review_summary: Mapped[Optional["ReviewSummary"]] = relationship("ReviewSummary", back_populates="product", uselist=False)

    __table_args__ = (
        UniqueConstraint("model_id", "slug", name="uq_product_model_slug"),
        Index("ix_shoe_products_model", "model_id"),
        Index("ix_shoe_products_style_id", "style_id"),
    )


# ============================================================================
# LAYER 3: SHOE OFFER (Merchant Listing)
# ============================================================================

class ShoeOffer(Base):
    """
    A merchant listing for a shoe product.
    Example: Running Warehouse listing for Pegasus 41 at $129.95

    This tracks prices, stock, and sizes across retailers.
    """
    __tablename__ = "shoe_offers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shoe_products.id", ondelete="CASCADE"), nullable=False)

    # Merchant info
    merchant: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "running_warehouse"
    merchant_product_id: Mapped[str | None] = mapped_column(String(200))  # Their internal ID

    # URL
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    affiliate_url: Mapped[str | None] = mapped_column(String(1500))  # With affiliate tag

    # Pricing
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    # Availability
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    sizes_available: Mapped[dict | None] = mapped_column(JSONB)  # {"7": true, "7.5": true, "8": false}
    stock_level: Mapped[str | None] = mapped_column(String(50))  # "in_stock", "low_stock", "out_of_stock"

    # Timestamps
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    price_updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    product: Mapped["ShoeProduct"] = relationship("ShoeProduct", back_populates="offers")
    price_history: Mapped[List["OfferPriceHistory"]] = relationship("OfferPriceHistory", back_populates="offer", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("product_id", "merchant", "url", name="uq_offer_product_merchant_url"),
        Index("ix_shoe_offers_product", "product_id"),
        Index("ix_shoe_offers_merchant", "merchant"),
        Index("ix_shoe_offers_in_stock", "in_stock"),
    )


class OfferPriceHistory(Base):
    """
    Historical price tracking for offers.
    Useful for "price dropped" alerts and analysis.
    """
    __tablename__ = "offer_price_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shoe_offers.id", ondelete="CASCADE"), nullable=False)

    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    in_stock: Mapped[bool] = mapped_column(Boolean)

    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    offer: Mapped["ShoeOffer"] = relationship("ShoeOffer", back_populates="price_history")

    __table_args__ = (
        Index("ix_price_history_offer_date", "offer_id", "recorded_at"),
    )


# ============================================================================
# URL DISCOVERY TRACKING
# ============================================================================

class DiscoveredURL(Base):
    """
    Tracks URLs discovered from sitemaps and other sources.
    Used to manage the discovery → product pipeline.
    """
    __tablename__ = "discovered_urls"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # URL info
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    canonical_url: Mapped[str] = mapped_column(String(1000), nullable=False)

    # Source tracking
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "sitemap", "retailer", "manual"
    source_url: Mapped[str | None] = mapped_column(String(1000))  # The sitemap URL
    source_brand: Mapped[str | None] = mapped_column(String(100))  # Brand slug

    # Sitemap metadata
    lastmod: Mapped[datetime | None] = mapped_column(DateTime)
    changefreq: Mapped[str | None] = mapped_column(String(20))
    priority: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))

    # Processing status
    status: Mapped[str] = mapped_column(String(50), default="pending")  # "pending", "processed", "failed", "skipped"
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shoe_products.id", ondelete="SET NULL"))
    error_message: Mapped[str | None] = mapped_column(Text)

    # Classification (from URL classifier)
    is_product: Mapped[bool | None] = mapped_column(Boolean)
    is_running_shoe: Mapped[bool | None] = mapped_column(Boolean)
    classification_reason: Mapped[str | None] = mapped_column(String(200))

    # Timestamps
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_discovered_urls_status", "status"),
        Index("ix_discovered_urls_source_brand", "source_brand"),
        Index("ix_discovered_urls_canonical", "canonical_url"),
    )


# ============================================================================
# MERCHANT CONFIGURATION
# ============================================================================

class Merchant(Base):
    """
    Configuration for each merchant/retailer we scrape.
    """
    __tablename__ = "merchants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    website_url: Mapped[str] = mapped_column(String(500))

    # Affiliate info
    affiliate_network: Mapped[str | None] = mapped_column(String(100))  # "cj", "rakuten", "impact"
    affiliate_id: Mapped[str | None] = mapped_column(String(200))
    affiliate_url_template: Mapped[str | None] = mapped_column(String(1000))

    # Scraping config
    scraper_class: Mapped[str | None] = mapped_column(String(200))  # Python class path
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, default=30)
    requires_browser: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scrape_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_scrape_status: Mapped[str | None] = mapped_column(String(50))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
