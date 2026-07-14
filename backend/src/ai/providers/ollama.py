import json
import traceback

import httpx
from collections.abc import AsyncIterator

from src.ai.base import BaseLLM
from src.ai.generation_config import get_generation_config


class OllamaLLM(BaseLLM):

    def __init__(self, model_name: str):
        self.model_name = model_name

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
            "options": {
                "temperature": config["temperature"],
                "top_p": config["top_p"],
                "num_predict": config["num_predict"],
            },
        }

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    "http://127.0.0.1:11434/api/generate",
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        data = json.loads(line)

                        token = data.get("response", "")
                        if token:
                            yield token

                        if data.get("done"):
                            break

        except Exception:
            traceback.print_exc()
            raise
