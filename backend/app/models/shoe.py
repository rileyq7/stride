import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Numeric, Text, ARRAY, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Shoe(Base):
    __tablename__ = "shoes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id"), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), nullable=False)

    # Basic info
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    model_year: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[str | None] = mapped_column(String(20))

    # Pricing
    msrp_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    current_price_min: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    current_price_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    # Availability
    available_regions: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    width_options: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    is_discontinued: Mapped[bool] = mapped_column(Boolean, default=False)

    # Images
    primary_image_url: Mapped[str | None] = mapped_column(String(500))
    image_urls: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    brand: Mapped["Brand"] = relationship("Brand", back_populates="shoes")
    category: Mapped["Category"] = relationship("Category", back_populates="shoes")
    running_attributes: Mapped[Optional["RunningShoeAttributes"]] = relationship(
        "RunningShoeAttributes", back_populates="shoe", uselist=False, cascade="all, delete-orphan"
    )
    basketball_attributes: Mapped[Optional["BasketballShoeAttributes"]] = relationship(
        "BasketballShoeAttributes", back_populates="shoe", uselist=False, cascade="all, delete-orphan"
    )
    fit_profile: Mapped[Optional["ShoeFitProfile"]] = relationship(
        "ShoeFitProfile", back_populates="shoe", uselist=False, cascade="all, delete-orphan"
    )
    reviews: Mapped[list["ShoeReview"]] = relationship("ShoeReview", back_populates="shoe", cascade="all, delete-orphan")
    affiliate_links: Mapped[list["ShoeAffiliateLink"]] = relationship(
        "ShoeAffiliateLink", back_populates="shoe", cascade="all, delete-orphan"
    )

    # AI-optimized data for matching and chatbot
    profile: Mapped[Optional["ShoeProfile"]] = relationship(
        "ShoeProfile", back_populates="shoe", uselist=False, cascade="all, delete-orphan"
    )
    review_summary: Mapped[Optional["ReviewSummary"]] = relationship(
        "ReviewSummary", back_populates="shoe", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("brand_id", "slug", name="uq_brand_slug"),)


class RunningShoeAttributes(Base):
    __tablename__ = "running_shoe_attributes"

    shoe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shoes.id", ondelete="CASCADE"), primary_key=True)

    # Type
    terrain: Mapped[str] = mapped_column(Text, nullable=False)  # 'road', 'trail', 'track'
    subcategory: Mapped[str | None] = mapped_column(Text)  # 'neutral', 'stability', 'motion_control', 'racing', 'daily_trainer'

    # Physical specs
    weight_oz: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    stack_height_heel_mm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    stack_height_forefoot_mm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    drop_mm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))

    # Features
    has_carbon_plate: Mapped[bool] = mapped_column(Boolean, default=False)
    has_rocker: Mapped[bool] = mapped_column(Boolean, default=False)
    cushion_type: Mapped[str | None] = mapped_column(Text)  # 'foam', 'gel', 'air', 'hybrid'
    cushion_level: Mapped[str | None] = mapped_column(Text)  # 'minimal', 'moderate', 'max'

    # Best for
    best_for_distances: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    best_for_pace: Mapped[str | None] = mapped_column(Text)  # 'easy', 'tempo', 'speed', 'racing'

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    shoe: Mapped["Shoe"] = relationship("Shoe", back_populates="running_attributes")


class BasketballShoeAttributes(Base):
    __tablename__ = "basketball_shoe_attributes"

    shoe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shoes.id", ondelete="CASCADE"), primary_key=True)

    # Type
    cut: Mapped[str] = mapped_column(Text, nullable=False)  # 'low', 'mid', 'high'
    court_type: Mapped[list[str] | None] = mapped_column(ARRAY(Text))  # ['indoor', 'outdoor']

    # Physical specs
    weight_oz: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))

    # Features
    cushion_type: Mapped[str | None] = mapped_column(Text)
    cushion_level: Mapped[str | None] = mapped_column(Text)
    traction_pattern: Mapped[str | None] = mapped_column(Text)
    ankle_support_level: Mapped[str | None] = mapped_column(Text)
    lockdown_level: Mapped[str | None] = mapped_column(Text)

    # Best for
    best_for_position: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    best_for_playstyle: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    outdoor_durability: Mapped[str | None] = mapped_column(Text)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    shoe: Mapped["Shoe"] = relationship("Shoe", back_populates="basketball_attributes")


class ShoeFitProfile(Base):
    __tablename__ = "shoe_fit_profiles"

    shoe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shoes.id", ondelete="CASCADE"), primary_key=True)

    # Sizing
    size_runs: Mapped[str | None] = mapped_column(Text)  # 'small', 'true', 'large'
    size_offset: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    size_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))

    # Width
    width_runs: Mapped[str | None] = mapped_column(Text)  # 'narrow', 'true', 'wide'
    toe_box_room: Mapped[str | None] = mapped_column(Text)
    heel_fit: Mapped[str | None] = mapped_column(Text)
    midfoot_fit: Mapped[str | None] = mapped_column(Text)

    # Arch
    arch_support: Mapped[str | None] = mapped_column(Text)
    arch_support_level: Mapped[str | None] = mapped_column(Text)

    # Comfort
    break_in_period: Mapped[str | None] = mapped_column(Text)
    break_in_miles: Mapped[int | None] = mapped_column(Integer)
    all_day_comfort: Mapped[bool | None] = mapped_column(Boolean)

    # Durability
    expected_miles_min: Mapped[int | None] = mapped_column(Integer)
    expected_miles_max: Mapped[int | None] = mapped_column(Integer)
    durability_rating: Mapped[str | None] = mapped_column(Text)
    common_wear_points: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    # Issues
    common_complaints: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    works_well_for: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    avoid_if: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    # Sentiment
    overall_sentiment: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    review_count: Mapped[int | None] = mapped_column(Integer)

    # Meta
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    extraction_model: Mapped[str | None] = mapped_column(String(50))
    needs_review: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    shoe: Mapped["Shoe"] = relationship("Shoe", back_populates="fit_profile")


class ShoeReview(Base):
    __tablename__ = "shoe_reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    shoe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shoes.id", ondelete="CASCADE"), nullable=False)

    # Link to new catalog model (nullable for backwards compatibility)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("shoe_products.id", ondelete="SET NULL"), nullable=True
    )

    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    source_review_id: Mapped[str | None] = mapped_column(String(100))

    # Content
    reviewer_name: Mapped[str | None] = mapped_column(String(100))
    rating: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))
    title: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str | None] = mapped_column(Text)

    # Reviewer context
    reviewer_foot_width: Mapped[str | None] = mapped_column(Text)
    reviewer_arch_type: Mapped[str | None] = mapped_column(Text)
    reviewer_size_purchased: Mapped[str | None] = mapped_column(String(20))
    reviewer_typical_size: Mapped[str | None] = mapped_column(String(20))
    reviewer_miles_tested: Mapped[int | None] = mapped_column(Integer)

    # Dates
    review_date: Mapped[date | None] = mapped_column(Date)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    shoe: Mapped["Shoe"] = relationship("Shoe", back_populates="reviews")
    product: Mapped[Optional["ShoeProduct"]] = relationship("ShoeProduct", back_populates="reviews")

    __table_args__ = (UniqueConstraint("shoe_id", "source", "source_review_id", name="uq_review_source"),)


class ShoeAffiliateLink(Base):
    __tablename__ = "shoe_affiliate_links"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    shoe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shoes.id", ondelete="CASCADE"), nullable=False)

    retailer: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    affiliate_tag: Mapped[str | None] = mapped_column(String(100))
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    shoe: Mapped["Shoe"] = relationship("Shoe", back_populates="affiliate_links")

    __table_args__ = (UniqueConstraint("shoe_id", "retailer", name="uq_shoe_retailer"),)
