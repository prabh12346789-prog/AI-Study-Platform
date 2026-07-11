from src.ai.base import BaseLLM


class DummyLLM(BaseLLM):

    async def generate_stream(self, prompt: str, mode: str):
        yield f"Dummy AI Response\n\n{prompt}"