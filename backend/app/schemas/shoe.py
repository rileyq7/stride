from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any
from pydantic import BaseModel


class RunningAttributesCreate(BaseModel):
    terrain: str
    subcategory: Optional[str] = None
    weight_oz: Optional[Decimal] = None
    stack_height_heel_mm: Optional[Decimal] = None
    stack_height_forefoot_mm: Optional[Decimal] = None
    drop_mm: Optional[Decimal] = None
    has_carbon_plate: bool = False
    has_rocker: bool = False
    cushion_type: Optional[str] = None
    cushion_level: Optional[str] = None
    best_for_distances: Optional[list[str]] = None
    best_for_pace: Optional[str] = None


class BasketballAttributesCreate(BaseModel):
    cut: str
    court_type: Optional[list[str]] = None
    weight_oz: Optional[Decimal] = None
    cushion_type: Optional[str] = None
    cushion_level: Optional[str] = None
    traction_pattern: Optional[str] = None
    ankle_support_level: Optional[str] = None
    lockdown_level: Optional[str] = None
    best_for_position: Optional[list[str]] = None
    best_for_playstyle: Optional[list[str]] = None
    outdoor_durability: Optional[str] = None


class FitProfileResponse(BaseModel):
    size_runs: Optional[str] = None
    size_offset: Optional[Decimal] = None
    width_runs: Optional[str] = None
    toe_box_room: Optional[str] = None
    heel_fit: Optional[str] = None
    arch_support: Optional[str] = None
    break_in_period: Optional[str] = None
    durability_rating: Optional[str] = None
    expected_miles_min: Optional[int] = None
    expected_miles_max: Optional[int] = None
    common_complaints: Optional[list[str]] = None
    works_well_for: Optional[list[str]] = None
    overall_sentiment: Optional[Decimal] = None
    review_count: Optional[int] = None

    class Config:
        from_attributes = True


class AffiliateLink(BaseModel):
    retailer: str
    url: str
    price: Optional[Decimal] = None
    in_stock: bool = True

    class Config:
        from_attributes = True


class ShoeBase(BaseModel):
    name: str
    slug: str
    model_year: Optional[int] = None
    version: Optional[str] = None
    msrp_usd: Optional[Decimal] = None
    current_price_min: Optional[Decimal] = None
    current_price_max: Optional[Decimal] = None
    available_regions: Optional[list[str]] = None
    width_options: Optional[list[str]] = None
    is_discontinued: bool = False
    primary_image_url: Optional[str] = None
    image_urls: Optional[list[str]] = None
    is_active: bool = True


class ShoeCreate(ShoeBase):
    brand_id: UUID
    category_id: UUID
    running_attributes: Optional[RunningAttributesCreate] = None
    basketball_attributes: Optional[BasketballAttributesCreate] = None


class BrandInfo(BaseModel):
    id: UUID
    name: str
    logo_url: Optional[str] = None

    class Config:
        from_attributes = True


class ShoeResponse(BaseModel):
    id: UUID
    brand: BrandInfo
    category: str
    name: str
    slug: str
    model_year: Optional[int] = None
    msrp_usd: Optional[Decimal] = None
    current_price_min: Optional[Decimal] = None
    current_price_max: Optional[Decimal] = None
    primary_image_url: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class RunningSpecsResponse(BaseModel):
    terrain: str
    subcategory: Optional[str] = None
    weight_oz: Optional[Decimal] = None
    stack_height_heel_mm: Optional[Decimal] = None
    stack_height_forefoot_mm: Optional[Decimal] = None
    drop_mm: Optional[Decimal] = None
    has_carbon_plate: bool = False
    has_rocker: bool = False
    cushion_type: Optional[str] = None
    cushion_level: Optional[str] = None
    best_for_distances: Optional[list[str]] = None
    best_for_pace: Optional[str] = None

    class Config:
        from_attributes = True


class BasketballSpecsResponse(BaseModel):
    cut: str
    court_type: Optional[list[str]] = None
    weight_oz: Optional[Decimal] = None
    cushion_type: Optional[str] = None
    cushion_level: Optional[str] = None
    traction_pattern: Optional[str] = None
    ankle_support_level: Optional[str] = None
    lockdown_level: Optional[str] = None
    best_for_position: Optional[list[str]] = None
    best_for_playstyle: Optional[list[str]] = None
    outdoor_durability: Optional[str] = None

    class Config:
        from_attributes = True


class ShoeDetailResponse(BaseModel):
    id: UUID
    brand: BrandInfo
    category: str
    name: str
    full_name: str
    slug: str
    model_year: Optional[int] = None
    version: Optional[str] = None

    specs: Optional[dict[str, Any]] = None
    fit_profile: Optional[FitProfileResponse] = None

    pricing: dict[str, Any]
    affiliate_links: list[AffiliateLink] = []
    images: list[str] = []

    class Config:
        from_attributes = True
