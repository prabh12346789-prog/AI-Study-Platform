from datetime import datetime, timezone
import uuid

from fastapi.testclient import TestClient

from src.activity.manager import ActivityManager
from src.activity.models import ActivityEvent
from src.api.routes import activity
from src.main import app
from src.memory.storage import get_session_factory


def test_activity_event_crud_and_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(activity, "store", ActivityManager(str(tmp_path / "activity.sqlite3")))
    client = TestClient(app)

    invalid = client.post("/activity/events", json={"event_type": "device_activity"})
    assert invalid.status_code == 422
    assert client.post("/activity/events", json={"event_type": "community_post_created"}).status_code == 422

    created = client.post(
        "/activity/events",
        json={
            "event_type": "revision_completed", "subject": "Polity",
            "topic": "Fundamental Rights", "duration_seconds": 600,
            "metadata": {"source": "manual"},
        },
    )
    assert created.status_code == 201
    event = created.json()
    assert event["metadata"] == {"source": "manual"}
    assert client.get(f"/activity/events/{event['id']}").json()["id"] == event["id"]
    assert client.get("/activity/events", params={"subject": "Polity"}).json()[0]["id"] == event["id"]
    assert client.delete(f"/activity/events/{event['id']}").status_code == 204


def test_historical_removed_event_type_remains_readable_but_not_in_summary(tmp_path, monkeypatch):
    path = str(tmp_path / "historical.sqlite3")
    store = ActivityManager(path)
    monkeypatch.setattr(activity, "store", store)
    with get_session_factory(path)() as session:
        session.add(ActivityEvent(
            id=str(uuid.uuid4()), user_id="user_001", event_type="community_post_created",
            subject="Community", topic="Introductions", duration_seconds=3600,
            consented=True, occurred_at=datetime.now(timezone.utc),
        ))
        session.commit()
    client = TestClient(app)
    response = client.get("/activity/events")
    assert response.status_code == 200
    assert response.json()[0]["event_type"] == "community_post_created"
    summary = client.get("/activity/summary").json()
    assert summary["total_study_seconds"] == 0
    assert summary["subjects_studied"] == 0
    assert summary["top_subject"] is None
    assert summary["top_topic"] is None


def test_activity_api_accepts_internal_search_and_90_day_period(tmp_path, monkeypatch):
    monkeypatch.setattr(activity, "store", ActivityManager(str(tmp_path / "searches.sqlite3")))
    client = TestClient(app)
    created = client.post("/activity/events", json={
        "event_type": "internal_search", "subject": "Current Affairs",
        "topic": "monetary policy", "metadata": {"page": "current_affairs"},
    })
    assert created.status_code == 201
    summary = client.get("/activity/summary?period=90d")
    assert summary.status_code == 200
    assert summary.json()["searches_made"] == 1
    assert summary.json()["top_searches"] == ["monetary policy"]
    lifetime = client.get("/activity/summary?period=all")
    assert lifetime.status_code == 200
    assert lifetime.json()["total_learning_days"] == 1
    assert lifetime.json()["monthly_breakdown"][0]["searches_made"] == 1
