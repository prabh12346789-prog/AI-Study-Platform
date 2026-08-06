import httpx
from fastapi.testclient import TestClient

from src.api.routes import chat as chat_routes
from src.main import app


class UnavailableOrchestrator:
    async def process(self, **_kwargs):
        raise httpx.ConnectError("Ollama connection refused")

    async def process_stream(self, **_kwargs):
        raise httpx.ConnectError("Ollama connection refused")
        yield "unreachable"


def test_normal_chat_maps_local_model_connection_failure_to_503(monkeypatch):
    monkeypatch.setattr(chat_routes, "get_orchestrator", lambda: UnavailableOrchestrator())
    response = TestClient(app).post("/chat/", json={"question": "Explain Article 32", "mode": "learn"})
    assert response.status_code == 503
    assert "Start Ollama" in response.json()["detail"]


def test_stream_chat_emits_actionable_model_error(monkeypatch):
    monkeypatch.setattr(chat_routes, "get_orchestrator", lambda: UnavailableOrchestrator())
    response = TestClient(app).post("/chat/stream", json={"question": "Explain Article 32", "mode": "learn"})
    assert response.status_code == 200
    assert "event: error" in response.text
    assert "Start Ollama" in response.text
