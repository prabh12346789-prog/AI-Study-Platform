from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class BaseLLM(ABC):

    @abstractmethod
    async def generate_stream(self, prompt: str, mode: str) -> AsyncIterator[str]:
        pass

    async def generate(self, prompt: str, mode: str) -> str:
        answer = ""

        async for token in self.generate_stream(prompt=prompt, mode=mode):
            answer += token

        return answer