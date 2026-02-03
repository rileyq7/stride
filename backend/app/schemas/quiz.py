from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any
from pydantic import BaseModel


class QuestionOption(BaseModel):
    value: str
    label: str
    icon: Optional[str] = None
    description: Optional[str] = None


class Question(BaseModel):
    id: str
    type: str  # 'single_select', 'multi_select', 'rank', 'shoe_history'
    question: str
    hint: Optional[str] = None
    options: list[QuestionOption]
    optional: bool = False
    max_select: Optional[int] = None
    max_rank: Optional[int] = None


class QuizStartRequest(BaseModel):
    category: str  # 'running' or 'basketball'
    region: Optional[str] = None


class QuizStartResponse(BaseModel):
    session_id: UUID
    session_token: str
    questions: list[Question]


class QuizAnswerRequest(BaseModel):
    question_id: str
    answer: Any  # str, list[str], or dict for shoe_history


class QuizAnswerResponse(BaseModel):
    next_question: Optional[Question] = None
    progress: float
    is_complete: bool


class PreviousShoe(BaseModel):
    shoe_id: Optional[UUID] = None
    name: Optional[str] = None
    liked: bool
    notes: Optional[str] = None


class RecommendRequest(BaseModel):
    previous_shoes: Optional[list[PreviousShoe]] = None


class FitNotes(BaseModel):
    sizing: Optional[str] = None
    width: Optional[str] = None
    highlights: list[str] = []
    considerations: list[str] = []


class AffiliateLinkResponse(BaseModel):
    retailer: str
    url: str
    price: Optional[Decimal] = None


class ShoeInfo(BaseModel):
    id: UUID
    brand: str
    name: str
    primary_image_url: Optional[str] = None
    msrp_usd: Optional[Decimal] = None
    current_price_min: Optional[Decimal] = None


class RecommendedShoe(BaseModel):
    rank: int
    shoe: ShoeInfo
    match_score: float
    reasoning: str
    fit_notes: FitNotes
    affiliate_links: list[AffiliateLinkResponse] = []


class NotRecommendedShoe(BaseModel):
    shoe: ShoeInfo
    reason: str


class RecommendResponse(BaseModel):
    recommendation_id: UUID
    shoes: list[RecommendedShoe]
    not_recommended: list[NotRecommendedShoe] = []


class FeedbackRequest(BaseModel):
    helpful: bool
    purchased_shoe_id: Optional[UUID] = None
    rating: Optional[int] = None
    notes: Optional[str] = None
