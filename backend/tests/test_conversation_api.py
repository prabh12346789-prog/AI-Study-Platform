from fastapi.testclient import TestClient

from src.api.routes import conversations
from src.main import app
from src.memory.manager import MemoryManager


def test_conversation_crud_api(tmp_path, monkeypatch):
    manager = MemoryManager(str(tmp_path / "api-memory.sqlite3"))
    monkeypatch.setattr(conversations, "memory", manager)
    client = TestClient(app)

    created = client.post("/conversations")
    assert created.status_code == 201
    conversation = created.json()
    assert conversation["title"] == "New Conversation"

    manager.add_user_message(conversation["id"], "Explain Fundamental Rights")
    messages = client.get(f"/conversations/{conversation['id']}/messages")
    assert messages.status_code == 200
    assert messages.json()[0]["content"] == "Explain Fundamental Rights"
    assert "timestamp" in messages.json()[0]

    renamed = client.patch(f"/conversations/{conversation['id']}", json={"title": "Fundamental Rights"})
    assert renamed.json()["title"] == "Fundamental Rights"
    assert client.get("/conversations").json()[0]["id"] == conversation["id"]
    assert client.get(f"/conversations/{conversation['id']}").status_code == 200

    assert client.delete(f"/conversations/{conversation['id']}").status_code == 204
    assert client.get(f"/conversations/{conversation['id']}").status_code == 404
