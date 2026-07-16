from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.activity.manager import ActivityManager
from src.api.routes import mentor
from src.main import app
from src.mastery.manager import MasteryManager
from src.mentor.dashboard import MentorDashboardService
from src.mentor.manager import MentorDecisionEngine
from src.profile.manager import ProfileManager


def setup(tmp_path):
    path = str(tmp_path / "dashboard.sqlite3")
    activity = ActivityManager(path); mastery = MasteryManager(path); profile = ProfileManager(path, activity)
    engine = MentorDecisionEngine(path, mastery, profile, activity)
    return MentorDashboardService(engine), engine, activity, mastery, profile


def test_empty_and_partial_dashboard(tmp_path):
    dashboard, _, activity, _, _ = setup(tmp_path)
    empty = dashboard.get_dashboard()
    assert empty["today"]["study_seconds"] == 0
    assert empty["recommendations"]["primary"] is None
    assert "not enough reliable" in empty["mentor_brief"]["summary"]
    activity.record_event("study_time_logged", datetime.now(timezone.utc), duration_seconds=300, subject="Economy", topic="Inflation")
    partial = dashboard.get_dashboard()
    assert partial["today"]["study_seconds"] == 300
    assert partial["today"]["top_subject"] == "Economy"
    assert "Economy" in partial["mentor_brief"]["summary"]


def test_dashboard_combines_mastery_actions_profile_and_isolates_users(tmp_path):
    dashboard, engine, _, mastery, profile = setup(tmp_path)
    profile.update({"preferred_language": "hindi", "preferred_depth": "quick"})
    for _ in range(4): mastery.record_evidence(subject="Polity", topic="Strong", evidence_type="recall_success")
    for topic in ("Weak", "Risk", "Alternative"):
        mastery.record_evidence(subject="Economy", topic=topic, evidence_type="recall_failure")
    mastery.record_evidence(user_id="user_002", subject="Private", topic="Private", evidence_type="recall_failure")
    data = dashboard.get_dashboard()
    assert data["mastery"]["strong_topics"]
    assert data["mastery"]["weak_topics"]
    assert data["mastery"]["high_risk_topics"]
    assert data["recommendations"]["primary"]
    assert len(data["recommendations"]["alternatives"]) == 2
    assert data["profile"]["preferred_language"] == "hindi"
    serialized = str(data)
    assert "Private" not in serialized
    assert len(data["mentor_brief"]["summary"].split(". ")) <= 3


def test_dashboard_endpoint(tmp_path, monkeypatch):
    _, engine, _, _, _ = setup(tmp_path)
    monkeypatch.setattr(mentor, "engine", engine)
    response = TestClient(app).get("/mentor/dashboard")
    assert response.status_code == 200
    assert set(response.json()) == {"today", "mentor_brief", "mastery", "recommendations", "recommended_videos", "profile", "recent_activity"}
