from datetime import datetime
from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class BookCollection(Base):
    __tablename__ = "book_collections"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(255), default="PWOnlyIAS", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    collection_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(32), default="english", nullable=False)
    exam_stage: Mapped[str] = mapped_column(String(32), default="both", nullable=False)
    official_source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class UPSCBook(Base):
    __tablename__ = "upsc_books"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    collection_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(255), default="PWOnlyIAS", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    normalized_subject: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    original_subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(32), default="english", nullable=False)
    prelims_relevant: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mains_relevant: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    official_source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    official_pdf_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    canonical_url: Mapped[str] = mapped_column(String(2000), nullable=False, unique=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_status: Mapped[str] = mapped_column(String(32), default="ready", nullable=False, index=True)
    extraction_status: Mapped[str] = mapped_column(String(32), default="ready", nullable=False, index=True)
    indexing_status: Mapped[str] = mapped_column(String(32), default="indexed", nullable=False, index=True)
    content_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    estimated_reading_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    content_blocks_json: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class BookChapter(Base):
    __tablename__ = "book_chapters"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    book_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    chapter_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SavedBook(Base):
    __tablename__ = "saved_books"
    __table_args__ = (UniqueConstraint("user_id", "book_id"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    book_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BookReadingProgress(Base):
    __tablename__ = "book_reading_progress"
    __table_args__ = (UniqueConstraint("user_id", "book_id"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    book_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chapter_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
