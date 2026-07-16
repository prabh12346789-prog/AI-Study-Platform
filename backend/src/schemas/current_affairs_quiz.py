from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field

class QuizCreate(BaseModel):
    period_type: Literal["daily", "weekly", "custom"] = "daily"
    date_from: date | None = None
    date_to: date | None = None
    question_count: int | None = Field(default=None, ge=1, le=20)
    difficulty: Literal["easy", "standard", "difficult"] = "standard"

class QuizAnswer(BaseModel):
    question_id: str
    answer: str = Field(max_length=2000)

class QuizSubmission(BaseModel):
    answers: list[QuizAnswer] = Field(min_length=1, max_length=20)

class QuizQuestionResponse(BaseModel):
    id: str; question_type: str; question: str; options_json: list[str]
    article_id: str; source_url: str; subject: str; topic: str; difficulty: str

class QuizResponse(BaseModel):
    id: str; title: str; period_type: str; date_from: date; date_to: date
    question_count: int; difficulty: str; status: str; article_ids_json: list[str]
    questions: list[QuizQuestionResponse]; created_at: datetime; updated_at: datetime
