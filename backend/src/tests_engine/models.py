import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, JSON
from src.db.base import Base

class MainsTestSession(Base):
    __tablename__ = "mains_test_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, default="user_001")
    source_mode = Column(String, nullable=False, default="static")  # static, current_affairs, mixed
    subject = Column(String, nullable=False, default="General Studies")
    marks = Column(Integer, nullable=False, default=10)
    word_limit = Column(Integer, nullable=False, default=150)
    status = Column(String, nullable=False, default="ready")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

class MainsQuestion(Base):
    __tablename__ = "mains_questions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, nullable=False)
    question_text = Column(Text, nullable=False)
    directive = Column(String, nullable=False, default="Discuss")
    marks = Column(Integer, nullable=False, default=10)
    word_limit = Column(Integer, nullable=False, default=150)
    subject = Column(String, nullable=False, default="General Studies")
    gs_paper = Column(String, nullable=True, default="GS Paper 1")
    source_ids_json = Column(JSON, nullable=False, default=list)
    page_refs_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class MainsAnswerAttempt(Base):
    __tablename__ = "mains_answer_attempts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False, default="user_001")
    answer_text = Column(Text, nullable=False)
    word_count = Column(Integer, nullable=False, default=0)
    score = Column(Float, nullable=False, default=0.0)
    evaluation_json = Column(JSON, nullable=False, default=dict)
    evaluation_status = Column(String, nullable=False, default="completed")
    submitted_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
