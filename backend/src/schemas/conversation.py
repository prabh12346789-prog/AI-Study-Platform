from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class MessageResponse(BaseModel):
    id: int
    conversation_id: str
    role: str
    content: str
    timestamp: datetime

