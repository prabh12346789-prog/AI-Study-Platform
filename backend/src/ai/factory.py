from src.ai.base import BaseLLM
from src.ai.providers.dummy import DummyLLM
from src.ai.providers.ollama import OllamaLLM
from src.core.config import settings


def get_llm() -> BaseLLM:
    provider = settings.LLM_PROVIDER.lower()

    if provider == "dummy":
        return DummyLLM()

    return OllamaLLM(
        model_name=settings.OLLAMA_GENERATION_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )
