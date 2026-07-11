import asyncio
import time
from collections.abc import AsyncIterator

from src.ai.factory import get_llm
from src.core.config import settings
from src.memory.manager import MemoryManager
from src.rag.prompt_builder import PromptBuilder
from src.search.provider import SearchProvider
from src.services.orchestrator.prompts import SYSTEM_PROMPTS
from src.services.orchestrator.formatter import format_response


class AIOrchestrator:

    def __init__(self, memory_manager: MemoryManager | None = None):
        self.llm = get_llm()
        self.search_provider = SearchProvider()
        self.prompt_builder = PromptBuilder()
        self.memory_manager = memory_manager or MemoryManager()
        self._conversation_id: str | None = None

    def _format_history(self, history_messages: list[dict[str, str]]) -> str:
        if not history_messages:
            return ""

        lines = []
        for message in history_messages:
            lines.append(f"{message['role'].upper()}: {message['content']}")
        return "\n".join(lines)

    async def _prepare_prompt(self, question: str, mode: str):
        print("[orchestrator] before SearchProvider.search()", flush=True)
        search_result = await asyncio.to_thread(
            self.search_provider.search,
            question,
        )
        print(
            f"[orchestrator] after SearchProvider.search(): provider={search_result.get('provider')!r}, sources={len(search_result.get('sources', []))}",
            flush=True,
        )

        if self._conversation_id is None:
            conversation = self.memory_manager.create_conversation(title=f"{mode} chat")
            self._conversation_id = conversation.id

        history_messages = self.memory_manager.get_recent_history(
            conversation_id=self._conversation_id,
            limit=settings.MAX_CHAT_HISTORY,
        )
        history_text = self._format_history(history_messages)

        self.memory_manager.add_user_message(
            conversation_id=self._conversation_id,
            content=question,
        )

        print("[orchestrator] before PromptBuilder.build_prompt()", flush=True)
        prompt_body = self.prompt_builder.build_prompt(question, search_result)
        print("[orchestrator] after PromptBuilder.build_prompt()", flush=True)

        sources = search_result.get("sources", [])

        history_block = f"\n\nConversation History\n\n{history_text}" if history_text else ""

        if search_result.get("context"):
            prompt = f"""
System:
{SYSTEM_PROMPTS[mode]}

{history_block}
{prompt_body}
"""
        else:
            prompt = f"""
System:
{SYSTEM_PROMPTS[mode]}

Question:
{question}
{history_block}
"""

        print("=" * 80)
        print("PROMPT LENGTH:", len(prompt))
        print("=" * 80)
        print(prompt[:2000])
        print("=" * 80)

        return search_result, prompt, sources

    async def process(self, question: str, mode: str):

        print(f"[orchestrator] process() entry: question={question!r}, mode={mode!r}", flush=True)

        search_result, prompt, sources = await self._prepare_prompt(question, mode)

        print("[orchestrator] before LLM.generate()", flush=True)

        start = time.perf_counter()

        answer = await self.llm.generate(
            prompt=prompt,
            mode=mode,
        )

        elapsed = time.perf_counter() - start

        print(f"LLM Generation Time: {elapsed:.2f} seconds", flush=True)

        print("[orchestrator] after LLM.generate()", flush=True)
        print("[orchestrator] before formatter", flush=True)

        self.memory_manager.add_assistant_message(
            conversation_id=self._conversation_id,
            content=answer,
        )

        response = format_response(
            answer,
            provider=search_result.get("provider", "local"),
            sources=sources,
        )

        print("[orchestrator] after formatter", flush=True)

        return response

    async def process_stream(self, question: str, mode: str) -> AsyncIterator[str]:

        print(f"[orchestrator] process_stream() entry: question={question!r}, mode={mode!r}", flush=True)
        print("[stream] started", flush=True)

        search_result, prompt, _sources = await self._prepare_prompt(question, mode)

        print("[orchestrator] before LLM.generate_stream()", flush=True)

        start = time.perf_counter()
        first_token = True
        parts: list[str] = []

        async for token in self.llm.generate_stream(
            prompt=prompt,
            mode=mode,
        ):
            if first_token:
                print("[stream] first token", flush=True)
                first_token = False

            parts.append(token)
            yield token

        elapsed = time.perf_counter() - start

        print("[stream] finished", flush=True)
        print(f"LLM Generation Time: {elapsed:.2f} seconds", flush=True)

        self.memory_manager.add_assistant_message(
            conversation_id=self._conversation_id,
            content="".join(parts),
        )

        print("[orchestrator] after LLM.generate_stream()", flush=True)