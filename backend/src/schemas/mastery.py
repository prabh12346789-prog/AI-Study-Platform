from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EvidenceType = Literal["quiz_correct", "quiz_incorrect", "revision_completed", "answer_self_rating", "mains_answer_score", "recall_success", "recall_failure"]
RiskLevel = Literal["low", "medium", "high"]


class EvidenceCreate(BaseModel):
    user_id: str = "user_001"
    subject: str = Field(min_length=1, max_length=128)
    topic: str = Field(min_length=1, max_length=255)
    evidence_type: EvidenceType
    score: float | None = Field(default=None, ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = Field(default="manual", max_length=64)
    metadata: dict | None = None


class TopicMasteryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; user_id: str; subject: str; topic: str
    mastery_score: float; forgetting_risk: float; risk_level: RiskLevel; confidence_score: float
    total_attempts: int; correct_attempts: int; incorrect_attempts: int; revision_count: int
    last_attempt_at: datetime | None; last_revised_at: datetime | None; next_revision_at: datetime | None
    explanation: list[str] = Field(validation_alias="explanation_json")
    created_at: datetime; updated_at: datetime


class SubjectMastery(BaseModel):
    subject: str
    mastery_score: float


class MasteryOverview(BaseModel):
    average_mastery: float
    strong_topics: list[TopicMasteryResponse]
    weak_topics: list[TopicMasteryResponse]
    high_risk_topics: list[TopicMasteryResponse]
    due_for_revision: list[TopicMasteryResponse]
    subject_breakdown: list[SubjectMastery]
    recent_changes: list[TopicMasteryResponse]
