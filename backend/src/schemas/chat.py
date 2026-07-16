from pydantic import BaseModel, ConfigDict, model_validator

from src.schemas.profile import AnswerFormat, Depth, Language

from src.services.orchestrator.models import ResponseMode


class ChatRequest(BaseModel):

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "Explain Fundamental Rights.",
                "mode": "study",
            }
        }
    )

    question: str
    mode: ResponseMode = ResponseMode.LEARN
    conversation_id: str | None = None
    subject: str | None = None
    topic: str | None = None
    preferred_language: Language | None = None
    preferred_depth: Depth | None = None
    preferred_format: AnswerFormat | None = None
    language: Language | None = None
    depth: Depth | None = None
    format: AnswerFormat | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data):

        # Preserve object-based API while tolerating legacy raw-string clients.
        if isinstance(data, str):
            return {
                "question": data,
                "mode": ResponseMode.LEARN,
            }

        if isinstance(data, dict) and data.get("mode") == "study":
            normalized = dict(data)
            normalized["mode"] = ResponseMode.LEARN
            return normalized

        return data


class ChatResponse(BaseModel):
    status: str
    answer: str
    provider: str
    sources: list[dict]
    conversation_id: str | None = None
    subject: str | None = None
    topic: str | None = None
    effective_language: str | None = None
    effective_depth: str | None = None
    effective_format: str | None = None
    grounding: dict | None = None
