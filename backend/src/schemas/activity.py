from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ActivityEventType = Literal[
    "question_asked", "answer_generated", "pdf_uploaded", "quiz_answered",
    "revision_completed", "video_opened", "recommendation_accepted",
    "recommendation_skipped",
    "study_time_logged",
]


class ActivityEventCreate(BaseModel):
    event_type: ActivityEventType
    user_id: str = "user_001"
    conversation_id: str | None = None
    subject: str | None = None
    topic: str | None = None
    duration_seconds: int | None = None
    metadata: dict | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ActivityEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    event_type: ActivityEventType
    conversation_id: str | None
    subject: str | None
    topic: str | None
    duration_seconds: int | None
    metadata: dict | None = Field(validation_alias="metadata_json")
    occurred_at: datetime
    created_at: datetime


class ActivityBreakdown(BaseModel):
    name: str
    study_seconds: int
    event_count: int


class ActivitySummary(BaseModel):
    total_study_seconds: int
    questions_asked: int
    answers_generated: int
    pdfs_uploaded: int
    subjects_studied: int
    top_subject: str | None
    top_topic: str | None
    subject_breakdown: list[ActivityBreakdown]
    topic_breakdown: list[ActivityBreakdown]
    recent_events: list[ActivityEventResponse]
