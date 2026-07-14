from fastapi.testclient import TestClient

from src.api.routes import community
from src.community.manager import CommunityManager
from src.main import app


def test_community_crud_api(tmp_path, monkeypatch):
    manager = CommunityManager(str(tmp_path / "api.sqlite3")); monkeypatch.setattr(community, "manager", manager)
    client = TestClient(app); groups = client.get("/community/groups").json(); assert len(groups) == 11
    payload = {"group_id": groups[0]["id"], "title": "Focused question", "content": "How can this be used in a Mains answer?", "language": "english"}
    created = client.post("/community/posts", json=payload); assert created.status_code == 201; post_id = created.json()["id"]
    assert client.get(f"/community/posts/{post_id}").status_code == 200
    assert client.patch(f"/community/posts/{post_id}", json={"title": "Updated question"}).status_code == 200
    assert client.patch(f"/community/posts/{post_id}", json={"title": "No"}, headers={"X-User-Id": "user_002"}).status_code == 403
    comment = client.post(f"/community/posts/{post_id}/comments", json={"content": "Useful response"}); assert comment.status_code == 201
    assert client.patch(f"/community/comments/{comment.json()['id']}", json={"content": "Other"}, headers={"X-User-Id": "user_002"}).status_code == 403
    assert client.post(f"/community/posts/{post_id}/save").status_code == 201
    assert client.get("/community/saved").json()[0]["id"] == post_id
    assert client.delete(f"/community/posts/{post_id}/save").status_code == 204
    assert client.post("/community/reports", json={"target_type": "post", "target_id": post_id, "reason": "spam"}).status_code == 403
    assert client.delete(f"/community/posts/{post_id}").status_code == 204
    assert client.get("/community/posts").json() == []


def test_community_api_rejects_empty_pii_and_bad_url(tmp_path, monkeypatch):
    manager = CommunityManager(str(tmp_path / "safe.sqlite3")); monkeypatch.setattr(community, "manager", manager)
    client = TestClient(app); group_id = client.get("/community/groups").json()[0]["id"]
    base = {"group_id": group_id, "title": "Question", "language": "english"}
    assert client.post("/community/posts", json={**base, "content": ""}).status_code == 422
    assert client.post("/community/posts", json={**base, "content": "Email a@b.com"}).status_code == 422
    assert client.post("/community/posts", json={**base, "content": "Useful", "source_url": "not-a-url"}).status_code == 422
