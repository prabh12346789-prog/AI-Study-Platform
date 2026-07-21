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

_database_logged = False


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
        ]
        for col_name, col_type in new_cols:
            if col_name not in existing_cols:
                try:
                    conn.execute(text(f"ALTER TABLE current_affairs_articles ADD COLUMN {col_name} {col_type}"))
                except Exception:
                    pass
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
