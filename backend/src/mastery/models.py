from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class TopicMastery(Base):
    __tablename__ = "topic_mastery"
    __table_args__ = (UniqueConstraint("user_id", "subject", "topic"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), default="user_001", index=True)
    subject: Mapped[str] = mapped_column(String(128), index=True)
    topic: Mapped[str] = mapped_column(String(255), index=True)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.5)
    forgetting_risk: Mapped[float] = mapped_column(Float, default=0.5)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    total_attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct_attempts: Mapped[int] = mapped_column(Integer, default=0)
    incorrect_attempts: Mapped[int] = mapped_column(Integer, default=0)
    revision_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_revised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_revision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    explanation_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def risk_level(self) -> str:
        return "high" if self.forgetting_risk >= 0.65 else "medium" if self.forgetting_risk >= 0.35 else "low"


class LearningEvidence(Base):
    __tablename__ = "learning_evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), default="user_001", index=True)
    subject: Mapped[str] = mapped_column(String(128), index=True)
    topic: Mapped[str] = mapped_column(String(255), index=True)
    evidence_type: Mapped[str] = mapped_column(String(32), index=True)
    score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(64))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    source_activity_event_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
