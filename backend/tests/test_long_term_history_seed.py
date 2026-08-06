import sqlite3
from datetime import date, datetime

from scripts.seed_long_term_history import seed_long_term_history
from src.activity.manager import ActivityManager


def test_long_term_history_seed_is_detailed_and_idempotent(tmp_path):
    db_path = str(tmp_path / "history.sqlite3")
    first = seed_long_term_history(db_path, start_date=date(2023, 1, 9), end_date=date(2025, 12, 31))
    second = seed_long_term_history(db_path, start_date=date(2023, 1, 9), end_date=date(2025, 12, 31))

    assert first["learning_days"] > 600
    assert first["events_added"] > 1_000
    assert second["events_added"] == 0
    assert second["events_already_present"] == first["events_planned"]

    summary = ActivityManager(db_path).summarize(
        date_from=datetime(2023, 1, 1),
        date_to=datetime(2026, 1, 1),
    )
    assert summary["total_learning_days"] > 600
    assert len(summary["monthly_breakdown"]) == 36
    assert summary["searches_made"] > 150
    assert summary["questions_asked"] > 300
    assert len(summary["subject_breakdown"]) == 8

    with sqlite3.connect(db_path) as connection:
        timestamps = connection.execute(
            "select occurred_at from activity_events where id like 'history-%'"
        ).fetchall()
    assert timestamps
    assert all("+00:00" not in value for (value,) in timestamps)
