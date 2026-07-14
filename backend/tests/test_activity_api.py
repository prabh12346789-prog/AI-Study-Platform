from fastapi.testclient import TestClient

from src.activity.manager import ActivityManager
from src.api.routes import activity
from src.main import app


def test_activity_event_crud_and_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(activity, "store", ActivityManager(str(tmp_path / "activity.sqlite3")))
    client = TestClient(app)

    invalid = client.post("/activity/events", json={"event_type": "device_activity"})
    assert invalid.status_code == 422

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
