from fastapi.testclient import TestClient

from src.api.routes.chat import get_orchestrator
from src.main import app
from src.rag.embeddings import EmbeddingService
from src.rag.vector_store import VectorStore


def test_health_is_ready_without_loading_heavy_chat_services():
    get_orchestrator.cache_clear()
    embeddings_before = EmbeddingService.is_loaded()
    vector_store_before = VectorStore.is_initialized()

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ready",
        "ollama": "not_checked",
        "embeddings": "loaded" if embeddings_before else "not_loaded",
        "vector_store": "ready" if vector_store_before else "not_initialized",
    }
    assert get_orchestrator.cache_info().currsize == 0
    assert EmbeddingService.is_loaded() == embeddings_before
    assert VectorStore.is_initialized() == vector_store_before


def test_router_excludes_removed_community_endpoints():
    assert not any(path.startswith("/community") for path in app.openapi()["paths"])
