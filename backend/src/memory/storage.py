from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.base import Base
from src.memory.models import Conversation, ConversationMessage  # noqa: F401


def _default_db_path() -> str:
    project_root = Path(__file__).resolve().parents[2]
    return str(project_root / "data" / "memory.sqlite3")


def get_engine(db_path: str | None = None):
    resolved_db_path = db_path or os.getenv("MEMORY_DB_PATH") or _default_db_path()
    Path(resolved_db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{resolved_db_path}", future=True)
    Base.metadata.create_all(engine)
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
