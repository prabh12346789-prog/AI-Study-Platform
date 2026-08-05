import sqlite3

from fastapi.testclient import TestClient
from sqlalchemy import text

from src.api.routes.chat import get_orchestrator
from src.main import app
from src.memory.storage import get_session_factory
from src.rag.embeddings import EmbeddingService
from src.rag.vector_store import VectorStore


def test_health_reports_ollama_embedding_state_without_loading_chat_services(monkeypatch):
    from src.ai.ollama_status import OllamaStatus
    import src.ai.ollama_status as ollama_status_module
    get_orchestrator.cache_clear()
    embeddings_before = EmbeddingService.is_loaded()
    vector_store_before = VectorStore.is_initialized()

    monkeypatch.setattr(ollama_status_module, "availability_status", lambda: OllamaStatus(
        True, "qwen2.5:3b", True, "nomic-embed-text", True,
    ))
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ready",
        "ollama": {
            "reachable": True, "generation_model": "qwen2.5:3b", "generation_model_available": True,
            "embedding_model": "nomic-embed-text", "embedding_model_available": True, "error_code": None,
        },
        "embedding_provider": "ollama",
        "embedding_model": "nomic-embed-text",
        "embedding_model_available": True,
        "embeddings": "available" if embeddings_before else "not_checked",
        "vector_store": "ready" if vector_store_before else "not_initialized",
    }
    assert get_orchestrator.cache_info().currsize == 0
    assert EmbeddingService.is_loaded() == embeddings_before
    assert VectorStore.is_initialized() == vector_store_before


def test_router_excludes_removed_community_endpoints():
    assert not any(path.startswith("/community") for path in app.openapi()["paths"])


def test_startup_tolerates_legacy_community_tables(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        for table in ("community_groups", "community_posts", "community_comments", "community_saves", "community_reports"):
            connection.execute(f"CREATE TABLE {table} (id TEXT PRIMARY KEY, legacy_value TEXT)")
            connection.execute(f"INSERT INTO {table} VALUES (?, ?)", (table, "preserve"))

    factory = get_session_factory(str(path))
    with factory() as session:
        assert session.execute(text("SELECT COUNT(*) FROM community_posts")).scalar_one() == 1
        assert session.execute(text("SELECT legacy_value FROM community_reports")).scalar_one() == "preserve"


def test_all_active_router_groups_are_registered():
    paths = app.openapi()["paths"]
    for prefix in ("/chat", "/pdf", "/conversations", "/activity", "/profile", "/mastery", "/mentor", "/videos", "/visual-roadmaps", "/current-affairs"):
        assert any(path.startswith(prefix) for path in paths), prefix
