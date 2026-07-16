from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.activity.models import ActivityEvent
from src.api.routes import mastery
from src.main import app
from src.mastery.manager import MasteryManager


def test_mastery_api_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(mastery, "manager", MasteryManager(str(tmp_path / "mastery.sqlite3")))
    client = TestClient(app)
    created = client.post("/mastery/evidence", json={
        "subject": "Economy", "topic": "Inflation", "evidence_type": "quiz_incorrect",
        "confidence": .8, "source": "quiz",
    })
    assert created.status_code == 201
    item = created.json()
    assert 0 <= item["mastery_score"] <= 1
    assert item["explanation"]
    assert client.get("/mastery/topics").json()[0]["id"] == item["id"]
    assert client.get(f"/mastery/topics/{item['id']}").status_code == 200
    assert client.get("/mastery/overview").status_code == 200
    assert client.post(f"/mastery/topics/{item['id']}/recalculate").status_code == 200
    assert client.delete(f"/mastery/topics/{item['id']}").status_code == 204


def test_historical_community_event_does_not_affect_mastery(tmp_path):
    manager = MasteryManager(str(tmp_path / "mastery.sqlite3"))
    event = ActivityEvent(
        id="legacy-community-event", user_id="user_001",
        event_type="community_post_created", subject="Polity", topic="Fundamental Rights",
        consented=True, occurred_at=datetime.now(timezone.utc),
    )
    assert manager.process_activity_event(event) is None
    assert manager.list_topic_mastery() == []
