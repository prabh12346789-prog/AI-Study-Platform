from pydantic import BaseModel, ConfigDict, model_validator

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