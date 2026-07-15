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


def test_historical_removed_event_type_remains_readable(tmp_path, monkeypatch):
    path = str(tmp_path / "historical.sqlite3")
    store = ActivityManager(path)
    monkeypatch.setattr(activity, "store", store)
    with get_session_factory(path)() as session:
        session.add(ActivityEvent(id=str(uuid.uuid4()), user_id="user_001", event_type="community_post_created", consented=True, occurred_at=datetime.now(timezone.utc)))
        session.commit()
    response = TestClient(app).get("/activity/events")
    assert response.status_code == 200
    assert response.json()[0]["event_type"] == "community_post_created"
