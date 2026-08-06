from __future__ import annotations

from dataclasses import asdict, dataclass

import requests

from src.core.config import settings


@dataclass(frozen=True)
class OllamaStatus:
    reachable: bool
    generation_model: str
    generation_model_available: bool
    embedding_model: str
    embedding_model_available: bool
    error_code: str | None = None

    def model_dump(self) -> dict:
        return asdict(self)


def _normalized_model(value: str) -> str:
    normalized = value.strip().strip('"\'').casefold()
    return normalized.removesuffix(":latest")


def availability_status() -> OllamaStatus:
    generation_model = settings.OLLAMA_GENERATION_MODEL
    embedding_model = settings.OLLAMA_EMBEDDING_MODEL
    try:
        response = requests.get(
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags",
            timeout=(settings.OLLAMA_CONNECT_TIMEOUT_SECONDS, settings.OLLAMA_HEALTH_TIMEOUT_SECONDS),
        )
        response.raise_for_status()
        payload = response.json()
        models = payload.get("models")
        if not isinstance(models, list):
            raise ValueError("models must be a list")
        names = {
            _normalized_model(str(item.get("name") or item.get("model") or ""))
            for item in models if isinstance(item, dict)
        }
        return OllamaStatus(
            reachable=True,
            generation_model=generation_model,
            generation_model_available=_normalized_model(generation_model) in names,
            embedding_model=embedding_model,
            embedding_model_available=_normalized_model(embedding_model) in names,
        )
    except requests.Timeout:
        code = "ollama_timeout"
    except requests.ConnectionError:
        code = "ollama_unavailable"
    except (requests.RequestException, ValueError, TypeError):
        code = "invalid_ollama_response"
    return OllamaStatus(False, generation_model, False, embedding_model, False, code)
