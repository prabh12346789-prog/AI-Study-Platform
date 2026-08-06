from datetime import datetime, timedelta, timezone

import pytest

from src.activity.manager import ActivityManager


def test_record_retrieve_persist_and_delete(tmp_path):
    path = str(tmp_path / "activity.sqlite3")
    store = ActivityManager(path)
    event = store.record_event(
        "revision_completed", datetime.now(timezone.utc), subject="Polity",
        topic="Fundamental Rights", duration_seconds=600,
        metadata_json={"source": "manual"},
    )
    loaded = ActivityManager(path).get_event(event.id)
    assert loaded is not None
    assert loaded.user_id == "user_001"
    assert loaded.metadata_json == {"source": "manual"}
    assert store.delete_event(event.id) is True
    assert store.get_event(event.id) is None


def test_list_newest_first_and_filters(tmp_path):
    store = ActivityManager(str(tmp_path / "activity.sqlite3"))
    now = datetime.now(timezone.utc)
    older = store.record_event(
        "question_asked", now - timedelta(hours=2), conversation_id="a",
        subject="Polity", topic="Rights",
    )
    newer = store.record_event(
        "answer_generated", now - timedelta(hours=1), conversation_id="b",
        subject="Economy", topic="Inflation",
    )

    assert [event.id for event in store.list_events()] == [newer.id, older.id]
    assert [event.id for event in store.list_events(event_type="question_asked")] == [older.id]
    assert [event.id for event in store.list_events(conversation_id="b")] == [newer.id]
    assert [event.id for event in store.list_events(subject="Polity", topic="Rights")] == [older.id]
    assert [event.id for event in store.list_events(
        date_from=now - timedelta(minutes=90), date_to=now,
    )] == [newer.id]


def test_invalid_event_type_rejected(tmp_path):
    store = ActivityManager(str(tmp_path / "activity.sqlite3"))
    with pytest.raises(ValueError, match="Unsupported activity event type"):
        store.record_event("device_activity", datetime.now(timezone.utc))
    assert store.list_events() == []


def test_study_time_requires_positive_duration(tmp_path):
    store = ActivityManager(str(tmp_path / "activity.sqlite3"))
    event = store.record_event(
        "study_time_logged", datetime.now(timezone.utc), duration_seconds=300,
        subject="Polity and Governance", topic="Fundamental Rights",
    )
    assert event.duration_seconds == 300
    for invalid in (0, -1):
        with pytest.raises(ValueError, match="greater than zero"):
            store.record_event("study_time_logged", datetime.now(timezone.utc), duration_seconds=invalid)


def test_today_and_seven_day_summary_breakdowns(tmp_path):
    store = ActivityManager(str(tmp_path / "activity.sqlite3"))
    now = datetime.now(timezone.utc)
    store.record_event("question_asked", now, subject="Economy", topic="Monetary Policy")
    store.record_event("answer_generated", now, subject="Economy", topic="Monetary Policy")
    store.record_event(
        "study_time_logged", now, duration_seconds=600,
        subject="Economy", topic="Monetary Policy",
    )
    store.record_event(
        "study_time_logged", now - timedelta(days=3), duration_seconds=300,
        subject="Geography", topic="Climatology",
    )

    today = store.summarize(
        date_from=now.replace(hour=0, minute=0, second=0, microsecond=0), date_to=now,
    )
    seven_days = store.summarize(date_from=now - timedelta(days=7), date_to=now)
    assert today["total_study_seconds"] == 600
    assert today["questions_asked"] == 1
    assert today["top_subject"] == "Economy"
    assert today["subject_breakdown"][0]["study_seconds"] == 600
    assert seven_days["total_study_seconds"] == 900
    assert seven_days["subjects_studied"] == 2


def test_internal_searches_and_daily_history_are_summarized(tmp_path):
    store = ActivityManager(str(tmp_path / "activity.sqlite3"))
    now = datetime.now(timezone.utc)
    store.record_event("internal_search", now, subject="UPSC Books", topic="fundamental rights", metadata_json={"page": "upsc_books"})
    store.record_event("internal_search", now - timedelta(days=20), subject="Current Affairs", topic="inflation", metadata_json={"page": "current_affairs"})
    store.record_event("study_time_logged", now, duration_seconds=420, subject="Polity", topic="Rights")

    summary = store.summarize(date_from=now - timedelta(days=90), date_to=now)
    assert summary["searches_made"] == 2
    assert summary["top_searches"] == ["fundamental rights", "inflation"]
    assert summary["daily_breakdown"][-1]["study_seconds"] == 420
    assert summary["total_learning_days"] == 2
    assert summary["first_activity_at"] == now - timedelta(days=20)
    assert summary["monthly_breakdown"][-1]["searches_made"] == 1
