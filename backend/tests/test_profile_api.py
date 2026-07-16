from fastapi.testclient import TestClient

from src.api.routes import profile
from src.main import app
from src.profile.manager import ProfileManager


def test_profile_api_onboarding_validation_and_reset(tmp_path, monkeypatch):
    manager = ProfileManager(str(tmp_path / "profile.sqlite3"))
    monkeypatch.setattr(profile, "manager", manager)
    client = TestClient(app)

    default = client.get("/profile")
    assert default.status_code == 200
    assert default.json()["onboarding_completed"] is False
    assert client.patch("/profile", json={"preferred_depth": "invalid"}).status_code == 422

    onboarded = client.post("/profile/onboarding", json={
        "preferred_language": "english", "preferred_depth": "quick",
        "preferred_format": "bullets", "daily_study_target_minutes": 180,
        "preferred_content_type": "mixed",
    })
    assert onboarded.status_code == 200
    assert onboarded.json()["onboarding_completed"] is True
    assert client.patch("/profile", json={"preferred_depth": "detailed"}).json()["preferred_language"] == "english"
    assert client.put("/profile", json={
        "preferred_language": "punjabi", "preferred_depth": "standard",
        "preferred_format": "mixed", "daily_study_target_minutes": 90,
        "preferred_content_type": "text",
    }).json()["onboarding_completed"] is True
    assert client.get("/profile/insights").status_code == 200
    assert client.delete("/profile").status_code == 204
    assert client.get("/profile").json()["preferred_language"] == "auto"
