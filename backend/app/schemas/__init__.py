from app.schemas.category import CategoryBase, CategoryCreate, CategoryResponse
from app.schemas.brand import BrandBase, BrandCreate, BrandResponse
from app.schemas.shoe import (
    ShoeBase, ShoeCreate, ShoeResponse, ShoeDetailResponse,
    RunningAttributesCreate, BasketballAttributesCreate,
    FitProfileResponse, AffiliateLink
)
from app.schemas.quiz import (
    QuizStartRequest, QuizStartResponse, QuizAnswerRequest, QuizAnswerResponse,
    RecommendRequest, RecommendResponse, RecommendedShoe, FeedbackRequest
)
from app.schemas.admin import (
    AdminLoginRequest, AdminLoginResponse, AdminUserResponse,
    RecommendationReviewRequest, ShoeCreateRequest, ShoeUpdateRequest
)

__all__ = [
    # Category
    "CategoryBase", "CategoryCreate", "CategoryResponse",
    # Brand
    "BrandBase", "BrandCreate", "BrandResponse",
    # Shoe
    "ShoeBase", "ShoeCreate", "ShoeResponse", "ShoeDetailResponse",
    "RunningAttributesCreate", "BasketballAttributesCreate",
    "FitProfileResponse", "AffiliateLink",
    # Quiz
    "QuizStartRequest", "QuizStartResponse", "QuizAnswerRequest", "QuizAnswerResponse",
    "RecommendRequest", "RecommendResponse", "RecommendedShoe", "FeedbackRequest",
    # Admin
    "AdminLoginRequest", "AdminLoginResponse", "AdminUserResponse",
    "RecommendationReviewRequest", "ShoeCreateRequest", "ShoeUpdateRequest",
]
