from app.models.category import Category
from app.models.brand import Brand
from app.models.shoe import Shoe, RunningShoeAttributes, BasketballShoeAttributes, ShoeFitProfile, ShoeReview, ShoeAffiliateLink
from app.models.quiz import QuizSession, Recommendation, TrainingExample
from app.models.admin import AdminUser, AdminAuditLog, ScrapeJob
from app.models.ai_models import ShoeProfile, ReviewSummary
from app.models.catalog import (
    ShoeModel, ShoeModelAlias, ShoeProduct, ShoeOffer,
    OfferPriceHistory, DiscoveredURL, Merchant,
    Gender, Terrain, SupportType, ShoeCategory
)

__all__ = [
    "Category",
    "Brand",
    # Legacy shoe model (keeping for backwards compatibility)
    "Shoe",
    "RunningShoeAttributes",
    "BasketballShoeAttributes",
    "ShoeFitProfile",
    "ShoeReview",
    "ShoeAffiliateLink",
    # New 3-layer catalog model
    "ShoeModel",
    "ShoeModelAlias",
    "ShoeProduct",
    "ShoeOffer",
    "OfferPriceHistory",
    "DiscoveredURL",
    "Merchant",
    # Enums
    "Gender",
    "Terrain",
    "SupportType",
    "ShoeCategory",
    # Quiz
    "QuizSession",
    "Recommendation",
    "TrainingExample",
    # Admin
    "AdminUser",
    "AdminAuditLog",
    "ScrapeJob",
    # AI-optimized models
    "ShoeProfile",
    "ReviewSummary",
]
