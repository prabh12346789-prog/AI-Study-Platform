from datetime import datetime, timedelta, timezone

from src.activity.manager import ActivityManager
from src.mastery.manager import MasteryManager
from src.mentor.manager import MentorDecisionEngine
from src.profile.manager import ProfileManager


def setup(tmp_path):
    path = str(tmp_path / "mentor.sqlite3")
    mastery = MasteryManager(path); activity = ActivityManager(path); profile = ProfileManager(path, activity)
    return MentorDecisionEngine(path, mastery, profile, activity), mastery, activity, profile


def test_rules_priority_duration_duplicates_and_sorting(tmp_path):
    engine, mastery, _, profile = setup(tmp_path)
    old = datetime.now(timezone.utc) - timedelta(days=90)
    mastery.record_evidence(subject="Economy", topic="Inflation", evidence_type="revision_completed", occurred_at=old)
    mastery.record_evidence(subject="Economy", topic="Inflation", evidence_type="recall_failure")
    mastery.record_evidence(subject="Polity", topic="Rights", evidence_type="quiz_incorrect")
    mastery.record_evidence(subject="Polity", topic="Rights", evidence_type="quiz_incorrect")
    mastery.record_evidence(subject="History", topic="Modern", evidence_type="mains_answer_score", score=.2)
    actions = engine.generate_actions()
    assert 1 <= len(actions) <= 3
    assert actions == sorted(actions, key=lambda row: row.priority_score, reverse=True)
    assert all(0 <= row.priority_score <= 1 and row.reason for row in actions)
    assert any(row.action_type == "practise_recall" for row in actions)
    assert len(engine.generate_actions()) == len(actions)
    profile.update({"preferred_depth": "quick"})
    assert all(row.estimated_minutes <= 10 for row in engine.generate_actions(user_id="user_001", available_minutes=10))
    assert engine.get_next_action(available_minutes=5)["action"] is not None


def test_strong_recent_topic_has_no_immediate_action(tmp_path):
    engine, mastery, _, _ = setup(tmp_path)
    for _ in range(4): mastery.record_evidence(subject="Economy", topic="Growth", evidence_type="recall_success")
    mastery.record_evidence(subject="Economy", topic="Growth", evidence_type="revision_completed")
    assert engine.generate_actions() == []


def test_status_activity_cooldown_completion_and_isolation(tmp_path):
    engine, mastery, activity, _ = setup(tmp_path)
    mastery.record_evidence(subject="Economy", topic="Inflation", evidence_type="recall_failure")
    action = engine.generate_actions()[0]
    engine.update_action_status(action.id, "accepted")
    assert activity.list_events(event_type="recommendation_accepted")
    engine.update_action_status(action.id, "skipped")
    assert activity.list_events(event_type="recommendation_skipped")
    assert engine.generate_actions() == []

    mastery.record_evidence(subject="Polity", topic="Rights", evidence_type="revision_completed", occurred_at=datetime.now(timezone.utc)-timedelta(days=90))
    revision = next(row for row in engine.generate_actions() if row.topic == "Rights")
    before = mastery.get_topic_mastery(revision.source_mastery_id).mastery_score
    engine.complete_action(revision.id)
    after = mastery.get_topic_mastery(revision.source_mastery_id).mastery_score
    assert activity.list_events(event_type="revision_completed")
    assert after - before <= .03 and after < .7

    mastery.record_evidence(user_id="user_002", subject="Private", topic="Private", evidence_type="recall_failure")
    engine.generate_actions(user_id="user_002")
    assert all(row.user_id == "user_001" for row in engine.list_actions())
