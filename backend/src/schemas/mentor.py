from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict

ActionType = Literal["revise_topic", "take_quiz", "review_explanation", "practise_recall", "practise_mains_answer", "watch_video"]
Priority = Literal["low", "medium", "high", "urgent"]
Status = Literal["pending", "accepted", "completed", "skipped", "expired"]

class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; user_id: str; subject: str; topic: str; action_type: ActionType; title: str
    reason: list[str]; priority_score: float; priority_level: Priority; estimated_minutes: int
    status: Status; source_mastery_id: str; valid_until: datetime; created_at: datetime; updated_at: datetime
    accepted_at: datetime | None; completed_at: datetime | None; skipped_at: datetime | None

class NextActionResponse(BaseModel):
    action: RecommendationResponse | None
    alternatives: list[RecommendationResponse]

class StatusPatch(BaseModel): status: Status
