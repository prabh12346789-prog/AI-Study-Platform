from datetime import datetime, timedelta, timezone

from src.activity.models import ActivityEvent
from src.mastery.manager import MasteryManager


def evidence(manager, kind, topic="Inflation", **kwargs):
    return manager.record_evidence(subject="Economy", topic=topic, evidence_type=kind, **kwargs)


def test_creation_correct_incorrect_revision_and_bounds(tmp_path):
    manager = MasteryManager(str(tmp_path / "mastery.sqlite3"))
    correct = evidence(manager, "quiz_correct")
    assert correct.mastery_score > .5
    after_wrong = evidence(manager, "quiz_incorrect")
    assert after_wrong.mastery_score < correct.mastery_score
    before_revision = after_wrong.mastery_score
    revised = evidence(manager, "revision_completed")
    assert 0 < revised.mastery_score - before_revision <= .03
    for _ in range(20): evidence(manager, "recall_success")
    assert 0 <= evidence(manager, "recall_failure").mastery_score <= 1


def test_repeated_and_recent_evidence_weighting(tmp_path):
    manager = MasteryManager(str(tmp_path / "mastery.sqlite3"))
    old = evidence(manager, "quiz_correct", topic="Old", occurred_at=datetime.now(timezone.utc) - timedelta(days=90))
    recent = evidence(manager, "quiz_correct", topic="Recent")
    assert recent.mastery_score > old.mastery_score
    first = recent.mastery_score
    second = evidence(manager, "quiz_correct", topic="Recent")
    assert first < second.mastery_score < 1


def test_forgetting_risk_and_next_revision(tmp_path):
    manager = MasteryManager(str(tmp_path / "mastery.sqlite3"))
    for _ in range(3): evidence(manager, "recall_success", topic="Strong")
    strong = evidence(manager, "revision_completed", topic="Strong")
    assert strong.risk_level == "low"
    assert strong.next_revision_at is not None

    old = datetime.now(timezone.utc) - timedelta(days=90)
    evidence(manager, "revision_completed", topic="Weak", occurred_at=old)
    weak = evidence(manager, "recall_failure", topic="Weak", occurred_at=old)
    assert weak.risk_level == "high"
    current_risk = evidence(manager, "quiz_correct", topic="RecallRisk").forgetting_risk
    failed = evidence(manager, "recall_failure", topic="RecallRisk")
    assert failed.forgetting_risk > current_risk


def test_activity_deduplication_and_ignored_activity(tmp_path):
    manager = MasteryManager(str(tmp_path / "mastery.sqlite3"))
    now = datetime.now(timezone.utc)
    quiz = ActivityEvent(id="quiz-1", user_id="user_001", event_type="quiz_answered",
        conversation_id=None, subject="Economy", topic="Inflation", duration_seconds=None,
        metadata_json={"correct": True, "confidence": .8}, consented=True, occurred_at=now)
    first = manager.process_activity_event(quiz)
    second = manager.process_activity_event(quiz)
    assert first.id == second.id
    assert second.total_attempts == 1

    for event_type in ("question_asked", "answer_generated", "video_opened"):
        ignored = ActivityEvent(id=event_type, user_id="user_001", event_type=event_type,
            conversation_id=None, subject="Economy", topic="Inflation", duration_seconds=None,
            metadata_json={}, consented=True, occurred_at=now)
        assert manager.process_activity_event(ignored) is None
    assert manager.get_topic_mastery(first.id).total_attempts == 1


def test_overview_delete_and_user_isolation(tmp_path):
    manager = MasteryManager(str(tmp_path / "mastery.sqlite3"))
    for _ in range(3): strong = evidence(manager, "recall_success", topic="Strong")
    for _ in range(3): weak = evidence(manager, "recall_failure", topic="Weak")
    other = manager.record_evidence(user_id="user_002", subject="Economy", topic="Private",
        evidence_type="quiz_correct")
    overview = manager.get_mastery_overview()
    assert any(item.id == strong.id for item in overview["strong_topics"])
    assert any(item.id == weak.id for item in overview["weak_topics"])
    assert any(item.id == weak.id for item in overview["high_risk_topics"])
    assert all(item.id != other.id for item in manager.list_topic_mastery())
    assert manager.delete_topic_mastery(weak.id)
    assert manager.get_topic_mastery(weak.id) is None
