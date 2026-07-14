from datetime import datetime, timedelta, timezone

from src.activity.manager import ActivityManager
from src.profile.manager import ProfileManager


def test_default_update_partial_and_reset_profile(tmp_path):
    path = str(tmp_path / "profile.sqlite3")
    manager = ProfileManager(path)
    profile = manager.get_or_create()
    assert profile.user_id == "user_001"
    assert profile.preferred_language == "auto"
    assert manager.get_or_create().id == profile.id

    replaced = manager.update({
        "preferred_language": "english", "preferred_depth": "quick",
        "preferred_format": "bullets", "daily_study_target_minutes": 180,
        "preferred_content_type": "mixed",
    }, replace=True)
    assert replaced.preferred_language == "english"
    patched = manager.update({"preferred_depth": "detailed"})
    assert patched.preferred_depth == "detailed"
    assert patched.preferred_language == "english"

    assert manager.delete() is True
    reset = manager.get_or_create()
    assert reset.id != profile.id
    assert reset.preferred_language == "auto"


def test_profile_insights_are_derived_without_changing_preferences(tmp_path):
    path = str(tmp_path / "profile.sqlite3")
    activity = ActivityManager(path)
    manager = ProfileManager(path, activity)
    manager.update({"preferred_language": "hindi"})
    now = datetime.now(timezone.utc)
    activity.record_event(
        "question_asked", now, subject="Economy", topic="Monetary Policy",
        metadata_json={"mode": "learn"},
    )
    activity.record_event(
        "study_time_logged", now - timedelta(days=1), duration_seconds=600,
        subject="Economy", topic="Monetary Policy",
    )
    insights = manager.insights()
    assert insights["most_studied_subject"] == "Economy"
    assert insights["total_study_seconds_7d"] == 600
    assert insights["questions_asked_7d"] == 1
    assert insights["active_days_7d"] == 2
    assert manager.get_or_create().preferred_language == "hindi"
