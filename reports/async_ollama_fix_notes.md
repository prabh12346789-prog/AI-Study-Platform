# Async Ollama Fix Notes

This note contains the full code before and after the async fix for the 7 relevant files.

---

## 1) backend/src/ai/base.py

### Before
```python
from abc import ABC, abstractmethod


class BaseLLM(ABC):

    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass
```

### After
```python
from abc import ABC, abstractmethod


class BaseLLM(ABC):

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        pass
```

---

## 2) backend/src/ai/providers/dummy.py

### Before
```python
from src.ai.base import BaseLLM


class DummyLLM(BaseLLM):

    def generate(self, prompt: str) -> str:
        return f"Dummy AI Response\n\n{prompt}"
```

### After
```python
from src.ai.base import BaseLLM


class DummyLLM(BaseLLM):

    async def generate(self, prompt: str) -> str:
        return f"Dummy AI Response\n\n{prompt}"
```

---

## 3) backend/src/ai/providers/ollama.py

### Before
```python
import ollama
from src.ai.base import BaseLLM # Assuming you have a BaseLLM abstract class

class OllamaLLM:
    def __init__(self, model_name: str = "qwen3:8b"):
        self.model_name = model_name

    async def generate(self, prompt: str) -> str:
        try:
            # Using the asynchronous client prevents the server from hanging
            response = await ollama.AsyncClient().generate(
                model=self.model_name,
                prompt=prompt
            )
            return response.get("response", "")
        except Exception as e:
            return f"Error communicating with Ollama: {str(e)}"
```

### After
```python
import asyncio

import ollama

from src.ai.base import BaseLLM


class OllamaLLM(BaseLLM):
    def __init__(self, model_name: str = "qwen3:8b"):
        self.model_name = model_name
        self._client = ollama.AsyncClient()

    async def generate(self, prompt: str) -> str:
        try:
            generate_call = self._client.generate
            if asyncio.iscoroutinefunction(generate_call):
                response = await generate_call(model=self.model_name, prompt=prompt)
            else:
                response = await asyncio.to_thread(
                    generate_call,
                    model=self.model_name,
                    prompt=prompt,
                )

            if isinstance(response, dict):
                return response.get("response", "")
            return str(response)
        except Exception as exc:
            return f"Error communicating with Ollama: {exc}"
```

---

## 4) backend/src/ai/factory.py

### Before
```python
import ollama
from src.ai.base import BaseLLM # Assuming you have a BaseLLM abstract class

class OllamaLLM:
    def __init__(self, model_name: str = "qwen3:8b"):
        self.model_name = model_name

    async def generate(self, prompt: str) -> str:
        try:
            # Using the asynchronous client prevents the server from hanging
            response = await ollama.AsyncClient().generate(
                model=self.model_name,
                prompt=prompt
            )
            return response.get("response", "")
        except Exception as e:
            return f"Error communicating with Ollama: {str(e)}"
```

### After
```python
import os

from src.ai.base import BaseLLM
from src.ai.providers.dummy import DummyLLM
from src.ai.providers.ollama import OllamaLLM


def get_llm() -> BaseLLM:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "dummy":
        return DummyLLM()

    return OllamaLLM(model_name=os.getenv("OLLAMA_MODEL", "qwen3:8b"))
```

---

## 5) backend/src/services/orchestrator/service.py

### Before
```python
from src.ai.factory import get_llm
from src.services.orchestrator.prompts import SYSTEM_PROMPTS
from src.services.orchestrator.formatter import format_response


class AIOrchestrator:

    def __init__(self):
        self.llm = get_llm()

    def process(self, question: str, mode: str):

        prompt = f"""
System:
{SYSTEM_PROMPTS[mode]}

Question:
{question}
"""

        answer = self.llm.generate(prompt)

        return format_response(answer)
```

### After
```python
from src.ai.factory import get_llm
from src.services.orchestrator.prompts import SYSTEM_PROMPTS
from src.services.orchestrator.formatter import format_response


class AIOrchestrator:

    def __init__(self):
        self.llm = get_llm()

    async def process(self, question: str, mode: str):

        prompt = f"""
System:
{SYSTEM_PROMPTS[mode]}

Question:
{question}
"""

        answer = await self.llm.generate(prompt)

        return format_response(answer)
```

---

## 6) backend/src/api/routes/chat.py

### Before
```python
from fastapi import APIRouter

from src.schemas.chat import ChatRequest
from src.services.orchestrator.service import AIOrchestrator

router = APIRouter()

orchestrator = AIOrchestrator()


@router.post("/")
async def chat(request: ChatRequest):
    return orchestrator.process(
        question=request.question,
        mode=request.mode,
    )
```

### After
```python
from fastapi import APIRouter

from src.schemas.chat import ChatRequest
from src.services.orchestrator.service import AIOrchestrator

router = APIRouter()

orchestrator = AIOrchestrator()


@router.post("/")
async def chat(request: ChatRequest):
    return await orchestrator.process(
        question=request.question,
        mode=request.mode,
    )
```

---

## 7) backend/tests/test_async_ollama_flow.py

### Before
```python
# File did not exist before
```

### After
```python
import inspect

from src.services.orchestrator.service import AIOrchestrator


def test_orchestrator_process_is_async():
    assert inspect.iscoroutinefunction(AIOrchestrator.process)
```
