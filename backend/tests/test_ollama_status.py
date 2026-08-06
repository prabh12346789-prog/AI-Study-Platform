import requests

from src.ai.ollama_status import availability_status
from src.core.config import settings


class Response:
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): return None
    def json(self): return self.payload


def test_generation_and_embedding_models_are_checked_separately(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: Response({"models": [
        {"name": f' "{settings.OLLAMA_GENERATION_MODEL}" '},
    ]}))
    status = availability_status()
    assert status.reachable is True
    assert status.generation_model_available is True
    assert status.embedding_model_available is False


def test_missing_generation_model_is_reported(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: Response({"models": [
        {"name": settings.OLLAMA_EMBEDDING_MODEL},
    ]}))
    status = availability_status()
    assert status.reachable is True
    assert status.generation_model_available is False
    assert status.embedding_model_available is True


def test_implicit_latest_tag_matches_configured_model(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: Response({"models": [
        {"name": f"{settings.OLLAMA_EMBEDDING_MODEL}:latest"},
    ]}))
    status = availability_status()
    assert status.embedding_model_available is True


def test_unavailable_timeout_and_invalid_response_are_distinct(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.ConnectionError()))
    assert availability_status().error_code == "ollama_unavailable"
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.Timeout()))
    assert availability_status().error_code == "ollama_timeout"
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: Response({"models": "invalid"}))
    assert availability_status().error_code == "invalid_ollama_response"
