import math
from typing import Sequence

import requests

from src.core.config import settings


class EmbeddingProviderError(RuntimeError):
    """Readable failure raised by the configured embedding provider."""


class EmbeddingService:
    _available = False
    _dimension: int | None = None

    @classmethod
    def _endpoint(cls, path: str) -> str:
        return f"{settings.OLLAMA_BASE_URL.rstrip('/')}{path}"

    @classmethod
    def _normalize(cls, vector) -> list[float]:
        if not isinstance(vector, list) or not vector:
            raise EmbeddingProviderError("Ollama returned a malformed embedding response.")
        try:
            values = [float(value) for value in vector]
        except (TypeError, ValueError) as error:
            raise EmbeddingProviderError("Ollama returned a non-numeric embedding vector.") from error
        if not all(math.isfinite(value) for value in values):
            raise EmbeddingProviderError("Ollama returned a non-finite embedding vector.")
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0:
            raise EmbeddingProviderError("Ollama returned a zero-length embedding vector.")
        return [value / norm for value in values]

    @classmethod
    def embed_texts(cls, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        if settings.EMBEDDING_PROVIDER.casefold() != "ollama":
            raise EmbeddingProviderError(f"Unsupported embedding provider: {settings.EMBEDDING_PROVIDER}")
        try:
            response = requests.post(
                cls._endpoint("/api/embed"),
                json={"model": settings.OLLAMA_EMBEDDING_MODEL, "input": list(texts)},
                timeout=settings.OLLAMA_EMBEDDING_TIMEOUT_SECONDS,
            )
        except requests.RequestException as error:
            cls._available = False
            raise EmbeddingProviderError(
                f"Ollama embeddings are unavailable at {settings.OLLAMA_BASE_URL}."
            ) from error

        if response.status_code == 404:
            cls._available = False
            raise EmbeddingProviderError(
                f"Ollama embedding model '{settings.OLLAMA_EMBEDDING_MODEL}' is unavailable. "
                f"Run: ollama pull {settings.OLLAMA_EMBEDDING_MODEL}"
            )
        try:
            response.raise_for_status()
        except requests.RequestException as error:
            cls._available = False
            detail = response.text.strip() if response.text else "unknown Ollama error"
            raise EmbeddingProviderError(f"Ollama embedding request failed: {detail}") from error

        try:
            raw_embeddings = response.json()["embeddings"]
        except (ValueError, KeyError, TypeError) as error:
            raise EmbeddingProviderError("Ollama returned a malformed embedding response.") from error
        if not isinstance(raw_embeddings, list) or len(raw_embeddings) != len(texts):
            raise EmbeddingProviderError("Ollama returned an unexpected number of embeddings.")

        embeddings = [cls._normalize(vector) for vector in raw_embeddings]
        dimensions = {len(vector) for vector in embeddings}
        if len(dimensions) != 1:
            raise EmbeddingProviderError("Ollama returned inconsistent embedding dimensions.")
        dimension = dimensions.pop()
        if cls._dimension is not None and cls._dimension != dimension:
            raise EmbeddingProviderError(
                f"Embedding dimension changed from {cls._dimension} to {dimension}; use a separate Chroma collection."
            )
        cls._dimension = dimension
        cls._available = True
        return embeddings

    @classmethod
    def generate_embedding(cls, text: str) -> list[float]:
        return cls.embed_texts([text])[0]

    @classmethod
    def generate_embeddings(cls, chunks: Sequence[dict]) -> list[list[float]]:
        return cls.embed_texts([chunk["text"] for chunk in chunks])

    @classmethod
    def is_loaded(cls) -> bool:
        return cls._available

    @classmethod
    def health_status(cls) -> dict:
        status = {
            "provider": settings.EMBEDDING_PROVIDER,
            "model": settings.OLLAMA_EMBEDDING_MODEL,
            "ollama_reachable": False,
            "model_available": False,
        }
        try:
            response = requests.get(cls._endpoint("/api/tags"), timeout=settings.OLLAMA_HEALTH_TIMEOUT_SECONDS)
            response.raise_for_status()
            names = {model.get("name", "").split(":", 1)[0] for model in response.json().get("models", [])}
            status["ollama_reachable"] = True
            status["model_available"] = settings.OLLAMA_EMBEDDING_MODEL.split(":", 1)[0] in names
        except (requests.RequestException, ValueError, AttributeError):
            pass
        return status
