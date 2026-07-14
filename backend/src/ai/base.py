from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class BaseLLM(ABC):

    @abstractmethod
    async def generate_stream(self, prompt: str, mode: str, depth: str = "standard") -> AsyncIterator[str]:
        pass

    async def generate(self, prompt: str, mode: str, depth: str = "standard") -> str:
        answer = ""

        async for token in self.generate_stream(prompt=prompt, mode=mode, depth=depth):
            answer += token

        return answer
