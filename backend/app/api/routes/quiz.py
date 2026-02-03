import uuid
import secrets
from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models import Category, QuizSession, Recommendation
from app.schemas.quiz import (
    QuizStartRequest, QuizStartResponse, QuizAnswerRequest, QuizAnswerResponse,
    RecommendRequest, RecommendResponse, FeedbackRequest, Question, QuestionOption
)
from app.services.matching import MatchingService

router = APIRouter()


# Quiz questions by category
RUNNING_QUESTIONS = [
    Question(
        id="gender",
        type="single_select",
        question="Are you looking for men's or women's shoes?",
        options=[
            QuestionOption(value="mens", label="Men's"),
            QuestionOption(value="womens", label="Women's"),
        ],
    ),
    Question(
        id="terrain",
        type="single_select",
        question="What type of surface do you primarily run on?",
        options=[
            QuestionOption(value="road", label="Road / Pavement", icon="road"),
            QuestionOption(value="trail", label="Trail / Off-road", icon="mountain"),
            QuestionOption(value="track", label="Track", icon="track"),
            QuestionOption(value="treadmill", label="Treadmill", icon="treadmill"),
            QuestionOption(value="mixed", label="Mixed surfaces", icon="mixed"),
        ],
    ),
    Question(
        id="distance",
        type="single_select",
        question="What distances do you typically run?",
        options=[
            QuestionOption(value="short", label="Short runs (under 5K)"),
            QuestionOption(value="mid", label="Mid distance (5K - Half Marathon)"),
            QuestionOption(value="long", label="Long distance (Marathon+)"),
            QuestionOption(value="mixed", label="Mixed / Varies"),
        ],
    ),
    Question(
        id="experience",
        type="single_select",
        question="How would you describe your running experience?",
        options=[
            QuestionOption(value="beginner", label="New to running (< 1 year)"),
            QuestionOption(value="recreational", label="Recreational (1-3 years)"),
            QuestionOption(value="experienced", label="Experienced (3+ years)"),
            QuestionOption(value="competitive", label="Competitive / Racing"),
        ],
    ),
    Question(
        id="foot_issues",
        type="multi_select",
        question="Do you have any of these foot characteristics or issues?",
        hint="Select all that apply",
        options=[
            QuestionOption(value="overpronation", label="Overpronation (feet roll inward)"),
            QuestionOption(value="underpronation", label="Underpronation / Supination (feet roll outward)"),
            QuestionOption(value="flat_feet", label="Flat feet / Low arches"),
            QuestionOption(value="high_arches", label="High arches"),
            QuestionOption(value="wide_feet", label="Wide feet"),
            QuestionOption(value="narrow_feet", label="Narrow feet"),
            QuestionOption(value="plantar_fasciitis", label="Plantar fasciitis"),
            QuestionOption(value="bunions", label="Bunions"),
            QuestionOption(value="none", label="None of these"),
        ],
    ),
    Question(
        id="priorities",
        type="multi_select",
        question="What matters most to you in a running shoe?",
        hint="Select up to 3",
        max_select=3,
        options=[
            QuestionOption(value="cushion", label="Cushioning & Comfort"),
            QuestionOption(value="speed", label="Speed & Responsiveness"),
            QuestionOption(value="stability", label="Stability & Support"),
            QuestionOption(value="durability", label="Durability"),
            QuestionOption(value="price", label="Price / Value"),
        ],
    ),
    Question(
        id="budget",
        type="single_select",
        question="What's your budget?",
        options=[
            QuestionOption(value="under_100", label="Under $100"),
            QuestionOption(value="100_150", label="$100 - $150"),
            QuestionOption(value="150_200", label="$150 - $200"),
            QuestionOption(value="any", label="Whatever it takes"),
        ],
    ),
]

BASKETBALL_QUESTIONS = [
    Question(
        id="position",
        type="single_select",
        question="What position do you play / what's your play style?",
        options=[
            QuestionOption(value="guard", label="Guard - Quick cuts, speed, agility"),
            QuestionOption(value="wing", label="Wing - All-around, versatile"),
            QuestionOption(value="big", label="Big - Post play, physicality, rebounding"),
        ],
    ),
    Question(
        id="court_type",
        type="single_select",
        question="Where do you play most often?",
        options=[
            QuestionOption(value="indoor", label="Indoor (gym/hardwood)"),
            QuestionOption(value="outdoor", label="Outdoor (concrete/asphalt)"),
            QuestionOption(value="both", label="Both equally"),
        ],
    ),
    Question(
        id="priorities",
        type="multi_select",
        question="What matters most to you?",
        hint="Select up to 2",
        max_select=2,
        options=[
            QuestionOption(value="traction", label="Traction / Grip"),
            QuestionOption(value="cushion", label="Cushioning / Impact protection"),
            QuestionOption(value="court_feel", label="Court feel / Responsiveness"),
            QuestionOption(value="support", label="Ankle support / Lockdown"),
            QuestionOption(value="durability", label="Durability (especially outdoor)"),
        ],
    ),
    Question(
        id="cut_preference",
        type="single_select",
        question="Do you have a cut preference?",
        options=[
            QuestionOption(value="low", label="Low - Maximum mobility"),
            QuestionOption(value="mid", label="Mid - Balance of support and mobility"),
            QuestionOption(value="high", label="High - Maximum ankle support"),
            QuestionOption(value="no_preference", label="No preference"),
        ],
    ),
    Question(
        id="foot_issues",
        type="multi_select",
        question="Any foot concerns?",
        hint="Select all that apply",
        options=[
            QuestionOption(value="wide_feet", label="Wide feet"),
            QuestionOption(value="narrow_feet", label="Narrow feet"),
            QuestionOption(value="ankle_history", label="History of ankle injuries"),
            QuestionOption(value="knee_issues", label="Knee issues"),
            QuestionOption(value="none", label="None"),
        ],
    ),
    Question(
        id="budget",
        type="single_select",
        question="What's your budget?",
        options=[
            QuestionOption(value="under_100", label="Under $100"),
            QuestionOption(value="100_150", label="$100 - $150"),
            QuestionOption(value="150_plus", label="$150+"),
        ],
    ),
]

QUESTIONS_BY_CATEGORY = {
    "running": RUNNING_QUESTIONS,
    "basketball": BASKETBALL_QUESTIONS,
}


@router.post("/start", response_model=QuizStartResponse)
async def start_quiz(
    request: QuizStartRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
):
    """Start a new quiz session."""
    # Get category
    result = await db.execute(
        select(Category).where(Category.slug == request.category, Category.is_active == True)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category: {request.category}",
        )

    # Create session
    session_token = secrets.token_urlsafe(32)
    session = QuizSession(
        session_token=session_token,
        ip_address=req.client.host if req.client else None,
        user_agent=req.headers.get("user-agent"),
        category_id=category.id,
        region=request.region,
        answers={},
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)

    questions = QUESTIONS_BY_CATEGORY.get(request.category, [])

    return QuizStartResponse(
        session_id=session.id,
        session_token=session_token,
        questions=questions,
    )


@router.post("/{session_id}/answer", response_model=QuizAnswerResponse)
async def submit_answer(
    session_id: uuid.UUID,
    request: QuizAnswerRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit an answer for a quiz question."""
    result = await db.execute(
        select(QuizSession).where(QuizSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz session not found",
        )

    # Update answers
    answers = session.answers or {}
    answers[request.question_id] = request.answer
    session.answers = answers

    await db.commit()

    # Get questions for this category
    category_result = await db.execute(
        select(Category).where(Category.id == session.category_id)
    )
    category = category_result.scalar_one_or_none()
    questions = QUESTIONS_BY_CATEGORY.get(category.slug if category else "running", [])

    # Calculate progress and find next question
    answered_ids = set(answers.keys())
    current_index = next(
        (i for i, q in enumerate(questions) if q.id == request.question_id),
        -1
    )

    progress = (current_index + 1) / len(questions) if questions else 1.0
    next_question = None

    if current_index + 1 < len(questions):
        next_question = questions[current_index + 1]

    is_complete = current_index + 1 >= len(questions)

    if is_complete:
        session.completed_at = datetime.utcnow()
        await db.commit()

    return QuizAnswerResponse(
        next_question=next_question,
        progress=progress,
        is_complete=is_complete,
    )


@router.post("/{session_id}/recommend", response_model=RecommendResponse)
async def get_recommendations(
    session_id: uuid.UUID,
    request: RecommendRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate shoe recommendations based on quiz answers."""
    result = await db.execute(
        select(QuizSession).where(QuizSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz session not found",
        )

    # Store previous shoes if provided
    if request.previous_shoes:
        session.previous_shoes = [shoe.model_dump() for shoe in request.previous_shoes]
        await db.commit()

    # Generate recommendations using matching service
    matching_service = MatchingService(db)
    recommendations = await matching_service.generate_recommendations(session)

    return recommendations


@router.post("/recommendations/{recommendation_id}/feedback")
async def submit_feedback(
    recommendation_id: uuid.UUID,
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit user feedback on recommendations."""
    result = await db.execute(
        select(Recommendation).where(Recommendation.id == recommendation_id)
    )
    recommendation = result.scalar_one_or_none()

    if not recommendation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found",
        )

    recommendation.user_feedback = {
        "helpful": request.helpful,
        "purchased_shoe_id": str(request.purchased_shoe_id) if request.purchased_shoe_id else None,
        "rating": request.rating,
        "notes": request.notes,
    }
    recommendation.feedback_at = datetime.utcnow()

    await db.commit()

    return {"success": True}
