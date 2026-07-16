from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Language = Literal["auto", "english", "hindi", "punjabi"]
Depth = Literal["quick", "standard", "detailed"]
AnswerFormat = Literal["bullets", "structured", "explanation", "mixed"]
ContentType = Literal["text", "quiz", "video", "mixed"]


class ProfileFields(BaseModel):
    preferred_language: Language = "auto"
    preferred_depth: Depth = "standard"
    preferred_format: AnswerFormat = "mixed"
    daily_study_target_minutes: int = Field(default=120, ge=1, le=1440)
    preferred_content_type: ContentType = "mixed"


class ProfileReplace(ProfileFields):
    pass


class ProfilePatch(BaseModel):
    preferred_language: Language | None = None
    preferred_depth: Depth | None = None
    preferred_format: AnswerFormat | None = None
    daily_study_target_minutes: int | None = Field(default=None, ge=1, le=1440)
    preferred_content_type: ContentType | None = None


class ProfileResponse(ProfileFields):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    onboarding_completed: bool
    created_at: datetime
    updated_at: datetime


class ProfileInsights(BaseModel):
    most_studied_subject: str | None
    most_studied_topic: str | None
    total_study_seconds_7d: int
    questions_asked_7d: int
    active_days_7d: int
    average_daily_study_seconds: int
    preferred_mode_observed: str | None
