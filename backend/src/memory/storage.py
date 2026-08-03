from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.base import Base
from src.memory.models import Conversation, ConversationMessage  # noqa: F401
from src.visual_roadmap.models import VisualRoadmap  # noqa: F401
from src.current_affairs.models import (CurrentAffairsArticle, CurrentAffairsQuiz, CurrentAffairsQuizAttempt,
    CurrentAffairsQuizQuestion, CurrentAffairsRetention, DailyCurrentAffairsBrief, SavedCurrentAffairs)  # noqa: F401
from src.upsc_books.models import (BookCollection, UPSCBook, BookChapter, SavedBook as SavedBookModel, BookReadingProgress as BookReadingProgressModel)  # noqa: F401
from src.tests_engine.models import (MainsTestSession, MainsQuestion, MainsAnswerAttempt)  # noqa: F401

_database_logged = False


def cleanup_synthetic_books(db_path: str | None = None):
    """Explicit maintenance helper — remove confirmed synthetic/demo books.
    Call this from a migration script or admin command, never from server startup.
    """
    import contextlib
    from sqlalchemy import text as _text
    engine = get_engine(db_path=db_path)
    with engine.connect() as conn:
        try:
            rows = conn.execute(_text(
                "SELECT id FROM upsc_books WHERE "
                "title LIKE '%Isolated Test Book%' OR title LIKE '%Prog Book%' "
                "OR id LIKE 'test-%' OR id LIKE 'demo-%' OR id LIKE 'sample-%' "
                "OR id LIKE 'isolated-%' OR id LIKE 'prog-%'"
            )).fetchall()
            for (bid,) in rows:
                conn.execute(_text("DELETE FROM book_chapters WHERE book_id = :b"), {"b": bid})
                conn.execute(_text("DELETE FROM saved_books WHERE book_id = :b"), {"b": bid})
                conn.execute(_text("DELETE FROM book_reading_progress WHERE book_id = :b"), {"b": bid})
                conn.execute(_text("DELETE FROM upsc_books WHERE id = :b"), {"b": bid})
            conn.commit()
        except Exception:
            with contextlib.suppress(Exception):
                conn.rollback()


def _default_db_path() -> str:
    project_root = Path(__file__).resolve().parents[2]
    return str(project_root / "data" / "memory.sqlite3")


def get_engine(db_path: str | None = None):
    global _database_logged
    resolved_db_path = db_path or os.getenv("MEMORY_DB_PATH") or _default_db_path()
    Path(resolved_db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{resolved_db_path}", future=True)
    if not _database_logged:
        logging.getLogger("startup").info("Database initialization started: %s", resolved_db_path)
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        from sqlalchemy import text
        existing_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(current_affairs_articles)")).fetchall()}
        new_cols = [
            ("slug", "TEXT"),
            ("cadence", "TEXT DEFAULT 'daily'"),
            ("content_type", "TEXT DEFAULT 'article'"),
            ("week_label", "TEXT"),
            ("month", "INTEGER"),
            ("year", "INTEGER"),
            ("pdf_url", "TEXT"),
            ("pdf_availability", "TEXT DEFAULT 'unknown'"),
            ("extraction_status", "TEXT DEFAULT 'completed'"),
            ("content_blocks_json", "JSON"),
            ("qa_pairs_json", "JSON"),
            ("content_checksum", "TEXT"),
            ("extracted_text", "TEXT"),
            ("indexed_at", "DATETIME"),
            ("summary_method", "TEXT DEFAULT 'extractive'"),
            ("summary_model", "TEXT DEFAULT 'extractive_fallback'"),
            ("summary_generated_at", "DATETIME"),
            ("gs_paper", "TEXT"),
            ("relevance_reason", "TEXT"),
            ("classification_method", "TEXT DEFAULT 'deterministic_keywords'"),
            ("is_demo", "BOOLEAN DEFAULT 0"),
            ("rejection_reason", "TEXT"),
        ]
        for col_name, col_type in new_cols:
            if col_name not in existing_cols:
                try:
                    conn.execute(text(f"ALTER TABLE current_affairs_articles ADD COLUMN {col_name} {col_type}"))
                except Exception:
                    pass
        existing_books_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(upsc_books)")).fetchall()}
        if "resource_kind" not in existing_books_cols:
            try:
                conn.execute(text("ALTER TABLE upsc_books ADD COLUMN resource_kind TEXT DEFAULT 'study_book'"))
            except Exception:
                pass
        
        # Idempotently update "Post Independence India Prahaar 2026"
        try:
            book_row = conn.execute(text(
                "SELECT id, collection_id FROM upsc_books WHERE title LIKE '%Post Independence%' OR title LIKE '%Post-Independence%'"
            )).fetchone()
            if book_row:
                b_id, col_id = book_row[0], book_row[1]
                conn.execute(text("""
                    UPDATE upsc_books 
                    SET normalized_subject = 'History',
                        prelims_relevant = 0,
                        mains_relevant = 1,
                        resource_kind = 'study_book'
                    WHERE id = :id
                """), {"id": b_id})
                if col_id:
                    conn.execute(text("""
                        UPDATE book_collections 
                        SET title = 'Prahaar 2026'
                        WHERE id = :col_id
                    """), {"col_id": col_id})
        except Exception:
            pass

        # Synthetic-book cleanup is intentionally NOT performed here.
        # Call cleanup_synthetic_books() explicitly from admin/migration scripts.

        conn.commit()
    if not _database_logged:
        logging.getLogger("startup").info("Database initialization completed; registered models=%d", len(Base.metadata.tables))
        _database_logged = True
    return engine


def get_session_factory(db_path: str | None = None):
    engine = get_engine(db_path=db_path)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session(db_path: str | None = None) -> Iterator[Session]:
    factory = get_session_factory(db_path=db_path)
    session = factory()
    try:
        yield session
    finally:
        session.close()
