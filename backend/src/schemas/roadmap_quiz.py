from typing import Literal

from pydantic import BaseModel, Field

Difficulty = Literal["easy", "standard", "difficult"]
QuestionType = Literal["mcq", "sequence", "match_year", "true_false", "short_recall"]


class QuizCreate(BaseModel):
    question_count: int = Field(default=5, ge=1, le=10)
    difficulty: Difficulty = "standard"


class QuizQuestion(BaseModel):
    id: str
    roadmap_id: str
    question_type: QuestionType
    question: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str
    explanation: str
    source_node_ids: list[str] = Field(min_length=1)
    difficulty: Difficulty


class QuizResponse(BaseModel):
    id: str
    roadmap_id: str
    difficulty: Difficulty
    questions: list[QuizQuestion]


class QuizAnswer(BaseModel):
    question_id: str
    answer: str = Field(max_length=1000)


class QuizSubmission(BaseModel):
    answers: list[QuizAnswer] = Field(min_length=1, max_length=10)


class AnswerResult(BaseModel):
    question_id: str; correct: bool; submitted_answer: str; correct_answer: str
    explanation: str; source_node_ids: list[str]


class QuizResult(BaseModel):
    score: int; total: int; percentage: float
    correct_answers: list[AnswerResult]; incorrect_answers: list[AnswerResult]
    explanations: list[str]; weak_source_nodes: list[str]
