from datetime import datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

Language = Literal["english", "hindi", "punjabi"]
Reason = Literal["spam", "misinformation", "abusive", "unsafe", "personal_information", "irrelevant", "other"]

class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; name: str; slug: str; description: str; subject: str; active: bool; created_at: datetime; updated_at: datetime
class PostCreate(BaseModel):
    group_id: str; title: str = Field(max_length=200); content: str = Field(max_length=5000); language: Language = "english"; source_url: AnyHttpUrl | None = None
class PostPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200); content: str | None = Field(default=None, max_length=5000); language: Language | None = None; source_url: AnyHttpUrl | None = None
class PostResponse(BaseModel):
    id: str; user_id: str; group_id: str; group_name: str; subject: str | None; title: str; content: str; language: Language
    source_url: str | None; status: str; display_name: str; comment_count: int; saved: bool; created_at: datetime; updated_at: datetime
class CommentCreate(BaseModel): content: str = Field(max_length=1500)
class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; user_id: str; post_id: str; content: str; status: str; created_at: datetime; updated_at: datetime
class ReportCreate(BaseModel):
    target_type: Literal["post", "comment"]; target_id: str; reason: Reason; details: str | None = Field(default=None, max_length=1000)
class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; reporter_user_id: str; target_type: str; target_id: str; reason: str; details: str | None; status: str; created_at: datetime; reviewed_at: datetime | None
