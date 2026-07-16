from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class LearnerProfile(Base):
    __tablename__ = "learner_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(16), default="auto", nullable=False)
    preferred_depth: Mapped[str] = mapped_column(String(16), default="standard", nullable=False)
    preferred_format: Mapped[str] = mapped_column(String(16), default="mixed", nullable=False)
    daily_study_target_minutes: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    preferred_content_type: Mapped[str] = mapped_column(String(16), default="mixed", nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
