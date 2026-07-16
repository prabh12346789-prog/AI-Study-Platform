import math
import subprocess
import sys

import pytest
import requests

from src.core.config import settings
from src.rag.embeddings import EmbeddingProviderError, EmbeddingService
from src.rag.retriever import Retriever
from src.rag.vector_store import VectorStore


class Response:
    def __init__(self, payload=None, status_code=200, text=""):
        self.payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(self.text)


@pytest.fixture(autouse=True)
def reset_embedding_state():
    previous_dimension = EmbeddingService._dimension
    previous_available = EmbeddingService._available
    EmbeddingService._dimension = None
    EmbeddingService._available = False
    yield
    EmbeddingService._dimension = previous_dimension
    EmbeddingService._available = previous_available


def test_successful_single_embedding_is_numeric_and_normalized(monkeypatch):
    monkeypatch.setattr("src.rag.embeddings.requests.post", lambda *args, **kwargs: Response({"embeddings": [[3, 4]]}))
    vector = EmbeddingService.generate_embedding("Constitution")
    assert vector == pytest.approx([0.6, 0.8])
    assert math.sqrt(sum(value * value for value in vector)) == pytest.approx(1.0)


def test_batch_embedding_uses_one_ollama_request(monkeypatch):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response({"embeddings": [[1, 0], [0, 2]]})
    monkeypatch.setattr("src.rag.embeddings.requests.post", post)
    vectors = EmbeddingService.generate_embeddings([{"text": "one"}, {"text": "two"}])
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert calls[0][1]["json"] == {"model": settings.OLLAMA_EMBEDDING_MODEL, "input": ["one", "two"]}


def test_ollama_unavailable_is_readable(monkeypatch):
    def unavailable(*args, **kwargs):
        raise requests.ConnectionError("offline")
    monkeypatch.setattr("src.rag.embeddings.requests.post", unavailable)
    with pytest.raises(EmbeddingProviderError, match="Ollama embeddings are unavailable"):
        EmbeddingService.generate_embedding("test")


def test_embedding_model_missing_is_readable(monkeypatch):
    monkeypatch.setattr("src.rag.embeddings.requests.post", lambda *args, **kwargs: Response(status_code=404))
    with pytest.raises(EmbeddingProviderError, match="ollama pull nomic-embed-text"):
        EmbeddingService.generate_embedding("test")


@pytest.mark.parametrize("payload", [{}, {"embeddings": []}, {"embeddings": [["bad"]]}])
def test_malformed_response_is_rejected(monkeypatch, payload):
    monkeypatch.setattr("src.rag.embeddings.requests.post", lambda *args, **kwargs: Response(payload))
    with pytest.raises(EmbeddingProviderError):
        EmbeddingService.generate_embedding("test")


def test_dimension_consistency_is_enforced(monkeypatch):
    responses = iter([Response({"embeddings": [[1, 0]]}), Response({"embeddings": [[1, 0, 0]]})])
    monkeypatch.setattr("src.rag.embeddings.requests.post", lambda *args, **kwargs: next(responses))
    EmbeddingService.generate_embedding("first")
    with pytest.raises(EmbeddingProviderError, match="dimension changed"):
        EmbeddingService.generate_embedding("second")


def test_ingestion_preserves_metadata_and_uses_isolated_collection(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CHROMA_DB_PATH", str(tmp_path / "chroma"))
    monkeypatch.setattr(settings, "CHROMA_COLLECTION", "documents_ollama_nomic_embed_text")
    VectorStore._client = VectorStore._collection = None
    VectorStore._client_path = VectorStore._collection_name = None
    store = VectorStore()
    store.store_vectors("doc", "notes.pdf", [{"chunk_id": 0, "text": "Article 21", "word_count": 2, "page_start": 1, "page_end": 2}], [[1.0, 0.0]])
    result = store.collection.get(ids=["doc_0"], include=["metadatas"])
    metadata = result["metadatas"][0]
    assert metadata["page_start"] == 1 and metadata["page_end"] == 2
    assert metadata["embedding_model"] == "nomic-embed-text"
    assert store.collection.name == "documents_ollama_nomic_embed_text"


def test_retrieval_interface_and_threshold_remain_compatible(monkeypatch):
    class Store:
        def search(self, query_embedding, n_results):
            assert query_embedding == [1.0, 0.0]
            assert n_results == settings.TOP_K_RESULTS
            return {"ids": [["doc_0"]], "documents": [["Article 21 protects life."]],
                    "metadatas": [[{"document_id": "doc", "original_name": "notes.pdf", "chunk_id": 0, "page_start": 1, "page_end": 1}]],
                    "distances": [[0.0]]}
    monkeypatch.setattr("src.rag.retriever.VectorStore", Store)
    monkeypatch.setattr(EmbeddingService, "generate_embedding", lambda text: [1.0, 0.0])
    result = Retriever().retrieve("Article 21")
    assert result[0]["document_name"] == "notes.pdf"
    assert result[0]["metadata"]["page_start"] == 1 and result[0]["score"] == 1.0


def test_application_startup_does_not_import_torch():
    result = subprocess.run(
        [sys.executable, "-c", "import sys; import src.main; assert 'torch' not in sys.modules"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
