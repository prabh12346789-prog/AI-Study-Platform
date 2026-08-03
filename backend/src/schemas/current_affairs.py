from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CollectRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "date": "2026-07-15", "max_results": 10, "generate_brief": True, "language": "english"
    }})
    date: date
    max_results: int = Field(default=10, ge=1, le=20)
    generate_brief: bool = False
    language: Literal["english", "hindi", "punjabi"] = "english"

    @field_validator("date", mode="before")
    @classmethod
    def yyyy_mm_dd(cls, value):
        import re
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("date must use YYYY-MM-DD format")
        return value


class CollectResponse(BaseModel):
    date: date
    collected: int
    accepted: int
    rejected: int
    duplicates: int
    article_ids: list[str]
    collection_errors: list[str]
    daily_brief: Literal["not_requested", "generated", "failed"]
    brief_error: str | None = None


class DailyGenerateRequest(BaseModel):
    date: date
    language: Literal["english", "hindi", "punjabi"] = "english"


class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; title: str; summary: str; source_title: str; publisher: str; source_url: str; source_type: str
    publication_date: date | None; retrieved_at: datetime; subject: str; topic: str; syllabus_tags_json: list
    importance_level: Literal["low", "medium", "high"]; relevance_prelims: str; relevance_mains: str
    content_hash: str; status: Literal["active", "archived", "rejected"]; is_demo: bool = False
    created_at: datetime; updated_at: datetime
    slug: str | None = None; cadence: str | None = "daily"; content_type: str | None = "article"
    week_label: str | None = None; month: int | None = None; year: int | None = None
    pdf_url: str | None = None; pdf_availability: str | None = "unknown"
    extraction_status: str | None = "completed"; content_blocks_json: list | None = None
    qa_pairs_json: list | None = None
    saved: bool = False; opened: bool = False


class DailyBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; brief_date: date; language: str; title: str; overview: str
    article_ids_json: list[str]; subject_breakdown_json: dict; prelims_points_json: list[str]; mains_points_json: list[str]
    created_at: datetime; updated_at: datetime
