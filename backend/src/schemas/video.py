from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; title: str; description: str; subject: str; topic: str
    language: Literal["english", "hindi", "punjabi"]
    source_name: str; source_url: str; thumbnail_url: str; duration_seconds: int
    difficulty: Literal["beginner", "standard", "advanced"]
    verified: bool; active: bool; created_at: datetime; updated_at: datetime


class VideoRecommendationResponse(BaseModel):
    video: VideoResponse
    reasons: list[str]
