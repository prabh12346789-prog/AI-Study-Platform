import json
import traceback

import httpx
from collections.abc import AsyncIterator

from src.ai.base import BaseLLM
from src.ai.generation_config import get_generation_config
from src.core.config import settings


class OllamaLLM(BaseLLM):

    def __init__(self, model_name: str, base_url: str):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=settings.OLLAMA_CONNECT_TIMEOUT_SECONDS,
            read=settings.OLLAMA_GENERATION_TIMEOUT_SECONDS,
            write=settings.OLLAMA_CONNECT_TIMEOUT_SECONDS,
            pool=settings.OLLAMA_CONNECT_TIMEOUT_SECONDS,
        )

    async def generate_structured(self, prompt: str, mode: str, depth: str = "standard") -> str:
        config = get_generation_config(mode, depth)
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "keep_alive": "5m",
            "options": {
                "temperature": min(config["temperature"], 0.2),
                "top_p": config["top_p"],
                "num_predict": config["num_predict"],
            },
        }
        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        output = data.get("response") if isinstance(data, dict) else None
        if not isinstance(output, str) or not output.strip():
            raise ValueError("Ollama returned an invalid structured response")
        return output

    async def generate_stream(self, prompt: str, mode: str, depth: str = "standard") -> AsyncIterator[str]:

        config = get_generation_config(mode, depth)

        print("==============================", flush=True)
        print("Generation Profile", flush=True)
        print(flush=True)
        print(f"Mode: {mode}", flush=True)
        print(f"Temperature: {config['temperature']}", flush=True)
        print(f"Top P: {config['top_p']}", flush=True)
        print(f"Max Tokens: {config['num_predict']}", flush=True)
        print("==============================", flush=True)

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": True,
            "keep_alive": "5m",
            "options": {
                "temperature": config["temperature"],
                "top_p": config["top_p"],
                "num_predict": config["num_predict"],
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout()) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        try:
                            data = json.loads(line)
                        except (json.JSONDecodeError, TypeError):
                            continue

                        token = data.get("response", "")
                        if token:
                            yield token

                        if data.get("done"):
                            break

        except Exception:
            traceback.print_exc()
            raise
