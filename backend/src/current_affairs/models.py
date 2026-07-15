from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, String, Text, UniqueConstraint, func
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


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
