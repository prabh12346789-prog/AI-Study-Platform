import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.main import app
from src.rag.manager import DocumentManager


def _document(root, document_id: str, metadata: dict, processing: dict | None = None):
    directory = root / "user_001" / "documents" / document_id
    directory.mkdir(parents=True)
    (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    if processing is not None:
        (directory / "processing.json").write_text(json.dumps(processing), encoding="utf-8")
    return directory


def test_empty_document_library(monkeypatch, tmp_path):
    monkeypatch.setattr(DocumentManager, "BASE_DIR", tmp_path)
    response = TestClient(app).get("/pdf/documents")
    assert response.status_code == 200
    assert response.json() == []


def test_indexed_document_appears_once_without_path_leakage(monkeypatch, tmp_path):
    monkeypatch.setattr(DocumentManager, "BASE_DIR", tmp_path)
    _document(tmp_path, "document-1", {
        "document_id": "document-1", "original_name": "constitution.pdf",
        "uploaded_at": datetime.now(timezone.utc).isoformat(), "pages": 4, "chunks": 7,
        "embedding_provider": "ollama", "embedding_model": "nomic-embed-text",
        "embedding_collection": "documents_ollama_nomic_embed_text", "vectorized": True,
        "status": "indexed", "stored_name": "original.pdf",
    }, {"chunked": True, "embedded": True, "indexed": True})
    response = TestClient(app).get("/pdf/documents")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0] == {
        "document_id": "document-1", "name": "constitution.pdf",
        "uploaded_at": items[0]["uploaded_at"], "status": "indexed",
        "page_count": 4, "chunk_count": 7, "embedding_provider": "ollama",
        "embedding_model": "nomic-embed-text",
        "embedding_collection": "documents_ollama_nomic_embed_text", "indexed": True,
    }
    assert str(tmp_path) not in response.text
    assert "stored_name" not in response.text


def test_failed_document_has_readable_nullable_status(monkeypatch, tmp_path):
    monkeypatch.setattr(DocumentManager, "BASE_DIR", tmp_path)
    _document(tmp_path, "document-failed", {
        "document_id": "document-failed", "original_name": "damaged.pdf",
        "uploaded_at": datetime.now(timezone.utc).isoformat(), "pages": None, "chunks": None,
        "vectorized": False, "status": "failed",
    }, {"chunked": False, "embedded": False, "indexed": False})
    item = TestClient(app).get("/pdf/documents").json()[0]
    assert item["name"] == "damaged.pdf"
    assert item["status"] == "failed"
    assert item["indexed"] is False
    assert item["page_count"] is None
    assert item["chunk_count"] is None


def test_legacy_embedding_is_not_reported_in_active_collection(monkeypatch, tmp_path):
    monkeypatch.setattr(DocumentManager, "BASE_DIR", tmp_path)
    _document(tmp_path, "legacy-document", {
        "document_id": "legacy-document", "original_name": "legacy.pdf",
        "uploaded_at": datetime.now(timezone.utc).isoformat(), "pages": 2, "chunks": 1,
        "embedding_model": "BAAI/bge-small-en-v1.5", "vectorized": True, "status": "embedded",
    }, {"chunked": True, "embedded": True, "indexed": True})
    item = TestClient(app).get("/pdf/documents").json()[0]
    assert item["status"] == "legacy"
    assert item["indexed"] is False
    assert item["embedding_provider"] is None
    assert item["embedding_collection"] is None
