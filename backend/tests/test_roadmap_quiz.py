from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from src.activity.manager import ActivityManager
from src.mastery.manager import MasteryManager
from src.mastery.models import LearningEvidence
from src.memory.storage import get_session_factory
from src.schemas.roadmap_quiz import QuizAnswer
from src.visual_roadmap.quiz_service import RoadmapQuizService


def structure(count=5, visual_type="timeline"):
    nodes = [{"id": f"n{i}", "label": f"Act {i}", "year": str(1770 + i),
              "description": f"Saved description {i}.", "importance": f"Saved importance {i}.",
              "source_ids": ["source_1"]} for i in range(1, count + 1)]
    return {"title": "Saved roadmap", "visual_type": visual_type, "summary": "Saved summary", "nodes": nodes,
            "connections": [{"from": f"n{i}", "to": f"n{i+1}", "label": "followed by"} for i in range(1, count)],
            "exam_points": ["Saved exam point"], "sources": [{"id": "source_1", "document": "notes.pdf"}]}


class Roadmaps:
    def __init__(self, data=None): self.row = SimpleNamespace(id="roadmap-1", user_id="user_001", status="ready",
        subject="Polity and Governance", topic="Constitution", conversation_id=None, structure_json=data or structure())
    def get(self, roadmap_id, user_id="user_001"):
        return self.row if roadmap_id == self.row.id and user_id == self.row.user_id else None


def quiz_service(tmp_path, data=None):
    db = str(tmp_path / "quiz.sqlite3"); activity = ActivityManager(db)
    return RoadmapQuizService(db_path=db, roadmap_service=Roadmaps(data), activity_manager=activity,
        mastery_manager=MasteryManager(db)), db


def test_default_five_questions_chronology_unique_and_roadmap_only(tmp_path):
    svc, _ = quiz_service(tmp_path); quiz = svc.generate("roadmap-1")
    assert len(quiz.questions_json) == 5
    assert quiz.questions_json[0]["question_type"] == "sequence"
    assert len({item["question"] for item in quiz.questions_json}) == 5
    saved = structure(); corpus = str(saved)
    for item in quiz.questions_json:
        assert all(node_id in {node["id"] for node in saved["nodes"]} for node_id in item["source_node_ids"])
        assert item["correct_answer"] in corpus or item["question_type"] == "sequence"


def test_invalid_and_insufficient_roadmaps_rejected(tmp_path):
    svc, _ = quiz_service(tmp_path, structure(2))
    with pytest.raises(ValueError, match="at least three"): svc.generate("roadmap-1")
    svc.roadmaps.row.status = "failed"
    with pytest.raises(ValueError, match="Valid ready"): svc.generate("roadmap-1")


def test_scoring_explanations_mastery_activity_and_deduplication(tmp_path):
    svc, db = quiz_service(tmp_path); quiz = svc.generate("roadmap-1")
    answers = [QuizAnswer(question_id=q["id"], answer=q["correct_answer"] if i < 3 else "wrong") for i, q in enumerate(quiz.questions_json)]
    result = svc.submit("roadmap-1", answers)
    assert result["score"] == 3 and result["total"] == 5 and result["percentage"] == 60
    assert len(result["explanations"]) == 5 and result["weak_source_nodes"]
    factory = get_session_factory(db)
    with factory() as session: assert session.scalar(select(func.count()).select_from(LearningEvidence)) == 5
    assert svc.submit("roadmap-1", answers) == result
    with factory() as session: assert session.scalar(select(func.count()).select_from(LearningEvidence)) == 5
    assert len(svc.activity.list_events(event_type="roadmap_quiz_started")) == 1
    assert len(svc.activity.list_events(event_type="roadmap_quiz_completed")) == 1


def test_opening_quiz_does_not_affect_mastery_and_user_isolation(tmp_path):
    svc, _ = quiz_service(tmp_path); svc.generate("roadmap-1")
    assert svc.get("roadmap-1") is not None
    assert svc.get("roadmap-1", user_id="other") is None
    assert svc.mastery.list_topic_mastery() == []
