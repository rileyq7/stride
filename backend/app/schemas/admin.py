from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any
from pydantic import BaseModel, EmailStr


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    name: Optional[str] = None
    role: str
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None
    role: str = "reviewer"


class ShoeRank(BaseModel):
    shoe_id: UUID
    rank: int


class RecommendationReviewRequest(BaseModel):
    status: str  # 'approved', 'rejected', 'adjusted'
    adjusted_shoes: Optional[list[ShoeRank]] = None
    notes: Optional[str] = None


class RecommendationListItem(BaseModel):
    id: UUID
    created_at: datetime
    quiz_summary: dict[str, Any]
    recommended_shoes: list[dict[str, Any]]
    review_status: str


class RecommendationListResponse(BaseModel):
    items: list[RecommendationListItem]
    total: int
    page: int


class ShoeCreateRequest(BaseModel):
    brand_id: UUID
    category_id: UUID
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

    # Category-specific attributes
    running_attributes: Optional[dict[str, Any]] = None
    basketball_attributes: Optional[dict[str, Any]] = None


class ShoeUpdateRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    model_year: Optional[int] = None
    version: Optional[str] = None
    msrp_usd: Optional[Decimal] = None
    current_price_min: Optional[Decimal] = None
    current_price_max: Optional[Decimal] = None
    available_regions: Optional[list[str]] = None
    width_options: Optional[list[str]] = None
    is_discontinued: Optional[bool] = None
    primary_image_url: Optional[str] = None
    image_urls: Optional[list[str]] = None
    is_active: Optional[bool] = None

    running_attributes: Optional[dict[str, Any]] = None
    basketball_attributes: Optional[dict[str, Any]] = None


class FitProfileUpdateRequest(BaseModel):
    size_runs: Optional[str] = None
    size_offset: Optional[Decimal] = None
    width_runs: Optional[str] = None
    toe_box_room: Optional[str] = None
    heel_fit: Optional[str] = None
    midfoot_fit: Optional[str] = None
    arch_support: Optional[str] = None
    arch_support_level: Optional[str] = None
    break_in_period: Optional[str] = None
    break_in_miles: Optional[int] = None
    all_day_comfort: Optional[bool] = None
    expected_miles_min: Optional[int] = None
    expected_miles_max: Optional[int] = None
    durability_rating: Optional[str] = None
    common_wear_points: Optional[list[str]] = None
    common_complaints: Optional[list[str]] = None
    works_well_for: Optional[list[str]] = None
    avoid_if: Optional[list[str]] = None


class ScrapeJobRequest(BaseModel):
    job_type: str  # 'single_shoe', 'brand', 'category', 'all_reviews'
    target_id: Optional[UUID] = None
    sources: Optional[list[str]] = None


class ScrapeJobResponse(BaseModel):
    job_id: UUID
    status: str
    estimated_duration_minutes: Optional[int] = None


class AnalyticsOverview(BaseModel):
    quizzes_completed: int
    recommendations_generated: int
    click_through_rate: float
    quiz_completion_rate: float
    feedback_summary: dict[str, Any]
    top_recommended_shoes: list[dict[str, Any]]
