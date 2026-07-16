from fastapi.testclient import TestClient

from src.api.routes import videos
from src.main import app
from src.video.manager import VideoRecommendationService


def test_video_endpoints_and_open_event(tmp_path, monkeypatch):
    service = VideoRecommendationService(str(tmp_path / "api.sqlite3"))
    monkeypatch.setattr(videos, "service", service)
    client = TestClient(app)
    listed = client.get("/videos", params={"subject": "Economy", "max_duration_seconds": 1800})
    assert listed.status_code == 200 and listed.json()
    video_id = listed.json()[0]["id"]
    assert client.get(f"/videos/{video_id}").status_code == 200
    recs = client.get("/videos/recommendations", params={"topic": "Monetary Policy", "language": "english"})
    assert recs.status_code == 200 and recs.json()[0]["video"]["id"] == video_id
    assert client.post(f"/videos/{video_id}/open").status_code == 200
    assert len(service.activity.list_events(event_type="video_opened")) == 1
    assert client.post(f"/videos/{video_id}/dismiss").status_code == 200
    assert client.get("/videos", params={"language": "invalid"}).status_code == 422
