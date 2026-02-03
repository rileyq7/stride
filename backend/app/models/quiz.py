import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import String, DateTime, ForeignKey, Text, ARRAY
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Session tracking
    session_token: Mapped[str | None] = mapped_column(String(100), unique=True)
    ip_address: Mapped[str | None] = mapped_column(String(45))  # Supports IPv6
    user_agent: Mapped[str | None] = mapped_column(Text)

    # Quiz data
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id"))
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # User profile extracted from answers
    user_foot_profile: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    user_preferences: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Optional
    region: Mapped[str | None] = mapped_column(String(10))
    previous_shoes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    foot_scan_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    category: Mapped["Category"] = relationship("Category")
    recommendations: Mapped[list["Recommendation"]] = relationship("Recommendation", back_populates="quiz_session")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quiz_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quiz_sessions.id"), nullable=False)

    # The recommendations
    recommended_shoes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Algorithm metadata
    algorithm_version: Mapped[str | None] = mapped_column(String(20))
    model_weights: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Admin review (RLHF)
    review_status: Mapped[str] = mapped_column(Text, default="pending")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    adjusted_shoes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    admin_notes: Mapped[str | None] = mapped_column(Text)

    # User feedback
    user_clicked_shoes: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    user_feedback: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    quiz_session: Mapped["QuizSession"] = relationship("QuizSession", back_populates="recommendations")
    reviewer: Mapped["AdminUser"] = relationship("AdminUser")


class TrainingExample(Base):
    __tablename__ = "training_examples"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Input
    quiz_answers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id"))

    # Labels
    ideal_shoes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reasoning: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Meta
    source: Mapped[str | None] = mapped_column(Text)
    quality_score: Mapped[float | None] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    category: Mapped["Category"] = relationship("Category")
