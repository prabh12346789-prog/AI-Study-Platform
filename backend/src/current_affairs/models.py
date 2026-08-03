from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class CurrentAffairsArticle(Base):
    __tablename__ = "current_affairs_articles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_title: Mapped[str] = mapped_column(String(500), nullable=False)
    publisher: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(String(32), default="current_affairs", nullable=False)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    subject: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    syllabus_tags_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    importance_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    relevance_prelims: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_mains: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cadence: Mapped[str | None] = mapped_column(String(32), default="daily", nullable=True, index=True)
    content_type: Mapped[str | None] = mapped_column(String(32), default="article", nullable=True)
    week_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    pdf_availability: Mapped[str | None] = mapped_column(String(32), default="unknown", nullable=True)
    extraction_status: Mapped[str | None] = mapped_column(String(32), default="completed", nullable=True)
    content_blocks_json: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)
    qa_pairs_json: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)
    content_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_method: Mapped[str | None] = mapped_column(String(32), default="extractive", nullable=True)
    summary_model: Mapped[str | None] = mapped_column(String(64), default="extractive_fallback", nullable=True)
    summary_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gs_paper: Mapped[str | None] = mapped_column(String(64), nullable=True)
    relevance_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification_method: Mapped[str | None] = mapped_column(String(32), default="deterministic_keywords", nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CurrentAffairsIngestionRun(Base):
    __tablename__ = "current_affairs_ingestion_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    source_results: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    fetched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summarized_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    indexed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)



class DailyCurrentAffairsBrief(Base):
    __tablename__ = "daily_current_affairs_briefs"
    __table_args__ = (UniqueConstraint("brief_date", "language"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    brief_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    overview: Mapped[str] = mapped_column(Text, nullable=False)
    article_ids_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    subject_breakdown_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    prelims_points_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    mains_points_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SavedCurrentAffairs(Base):
    __tablename__ = "saved_current_affairs"
    __table_args__ = (UniqueConstraint("user_id", "article_id"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    article_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CurrentAffairsQuiz(Base):
    __tablename__ = "current_affairs_quizzes"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ready")
    article_ids_json: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CurrentAffairsQuizQuestion(Base):
    __tablename__ = "current_affairs_quiz_questions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    quiz_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    question_type: Mapped[str] = mapped_column(String(32), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[list] = mapped_column(JSON, nullable=False)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    article_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False)


class CurrentAffairsQuizAttempt(Base):
    __tablename__ = "current_affairs_quiz_attempts"
    __table_args__ = (UniqueConstraint("user_id", "quiz_id"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    quiz_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)
    submitted_answers_json: Mapped[list] = mapped_column(JSON, nullable=False)
    weak_article_ids_json: Mapped[list] = mapped_column(JSON, nullable=False)
    weak_topics_json: Mapped[list] = mapped_column(JSON, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CurrentAffairsRetention(Base):
    __tablename__ = "current_affairs_retention"
    __table_args__ = (UniqueConstraint("user_id", "article_id"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    article_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    retention_score: Mapped[float] = mapped_column(Float, nullable=False, default=.5)
    correct_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    incorrect_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recall_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_revised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_revision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
