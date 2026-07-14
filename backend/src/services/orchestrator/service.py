import asyncio
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone

from src.ai.factory import get_llm
from src.activity.manager import ActivityManager
from src.activity.taxonomy import SubjectTopicClassifier
from src.core.config import settings
from src.memory.manager import MemoryManager
from src.profile.manager import ProfileManager
from src.services.adaptation import AdaptationPolicy
from src.rag.prompt_builder import PromptBuilder
from src.search.provider import SearchProvider
from src.services.orchestrator.prompts import COMMON_FORMAT_RULES, SYSTEM_PROMPTS
from src.services.orchestrator.formatter import format_response
from src.services.orchestrator.format_repair import repair_mode_format


@dataclass(frozen=True)
class ConversationEvent:
    conversation_id: str
    subject: str
    topic: str
    effective_language: str
    effective_depth: str
    effective_format: str


class AIOrchestrator:

    def __init__(
        self, memory_manager: MemoryManager | None = None,
        activity_manager: ActivityManager | None = None,
        profile_manager: ProfileManager | None = None,
    ):
        self.llm = get_llm()
        self.search_provider = SearchProvider()
        self.prompt_builder = PromptBuilder()
        self.memory_manager = memory_manager or MemoryManager()
        self.activity_manager = activity_manager or ActivityManager()
        self.profile_manager = profile_manager or ProfileManager()
        self.classifier = SubjectTopicClassifier()
        self.adaptation_policy = AdaptationPolicy()

    @staticmethod
    def _mode_value(mode: str) -> str:
        return getattr(mode, "value", mode)

    @staticmethod
    def _title_from_question(question: str) -> str:
        cleaned = re.sub(r"[^\w\s-]", " ", question).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"^(please\s+)?(explain|describe|discuss|tell me about)\s+", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s+(in\s+)?(simple|easy|brief)\s+(words|terms|language)$", "", cleaned, flags=re.I)
        return " ".join(cleaned.split()[:6]) or "New Conversation"

    def _resolve_conversation(self, question: str, conversation_id: str | None) -> str:
        if conversation_id is None:
            return self.memory_manager.create_conversation(self._title_from_question(question)).id
        conversation = self.memory_manager.get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation '{conversation_id}' not found")
        if conversation.title == "New Conversation" and not self.memory_manager.get_messages(conversation_id):
            self.memory_manager.rename_conversation(conversation_id, self._title_from_question(question))
        return conversation_id

    def _format_history(self, history_messages: list[dict[str, str]]) -> str:
        if not history_messages:
            return ""

        lines = []
        for message in history_messages:
            lines.append(f"{message['role'].upper()}: {message['content']}")
        return "\n".join(lines)

    def _prepare_request(
        self, question: str, mode: str, conversation_id: str | None,
        subject: str | None, topic: str | None,
        preferred_language: str | None, preferred_depth: str | None,
        preferred_format: str | None, language: str | None,
        depth: str | None, format: str | None,
    ):
        resolved_conversation_id = self._resolve_conversation(question, conversation_id)
        classification = self.classifier.classify(question, subject=subject, topic=topic)
        profile = self.profile_manager.get_or_create()
        adaptation = self.adaptation_policy.resolve(
            text=question, profile=profile, language=language or preferred_language,
            depth=depth or preferred_depth, format=format or preferred_format,
        )
        history_messages = self.memory_manager.get_recent_history(
            conversation_id=resolved_conversation_id, limit=settings.MAX_CHAT_HISTORY,
        )
        history_text = self._format_history(history_messages)
        user_message = self.memory_manager.add_user_message(
            conversation_id=resolved_conversation_id, content=question,
        )
        self.activity_manager.record_event(
            "question_asked", datetime.now(timezone.utc),
            conversation_id=resolved_conversation_id,
            subject=str(classification["subject"]), topic=str(classification["topic"]),
            metadata_json={"mode": self._mode_value(mode), "message_id": user_message.id},
        )
        return resolved_conversation_id, classification, adaptation, history_text

    async def _prepare_prompt(
        self, question: str, mode: str, conversation_id: str | None,
        subject: str | None = None, topic: str | None = None,
        preferred_language: str | None = None, preferred_depth: str | None = None,
        preferred_format: str | None = None,
        language: str | None = None, depth: str | None = None, format: str | None = None,
        prepared=None,
    ):
        if prepared is None:
            prepared = self._prepare_request(
                question, mode, conversation_id, subject, topic,
                preferred_language, preferred_depth, preferred_format,
                language, depth, format,
            )
        resolved_conversation_id, classification, adaptation, history_text = prepared
        print("[orchestrator] before SearchProvider.search()", flush=True)
        search_result = await asyncio.to_thread(
            self.search_provider.search,
            question,
        )
        print(
            f"[orchestrator] after SearchProvider.search(): provider={search_result.get('provider')!r}, sources={len(search_result.get('sources', []))}",
            flush=True,
        )

        print("[orchestrator] before PromptBuilder.build_prompt()", flush=True)
        prompt_body = self.prompt_builder.build_prompt(question, search_result)
        print("[orchestrator] after PromptBuilder.build_prompt()", flush=True)

        sources = search_result.get("sources", [])

        prompt_sections = [
            "System Instructions:\n" + COMMON_FORMAT_RULES.strip(),
            "Mode-specific Formatting Instructions:\n" + SYSTEM_PROMPTS[mode].strip(),
        ]

        if history_text:
            prompt_sections.append("Conversation History:\n" + history_text)

        if prompt_body:
            prompt_sections.append(
                "Retrieved PDF or Web Context:\n"
                "Use this context whenever possible; do not invent facts beyond it.\n"
                + prompt_body
            )

        prompt_sections.append(
            "Effective Response Adaptation (apply at prompt level; the selected UPSC mode remains authoritative):\n"
            f"- Respond in {adaptation['effective_language']}. Preserve constitutional Articles, Acts, official names, dates, citations, and source metadata; include English technical terms in brackets when useful.\n"
            f"- Depth: {adaptation['effective_depth']} (quick: direct and about 120-250 words; standard: concepts, examples and exam relevance in about 300-550 words; detailed: broader analysis, dimensions and limitations in about 600-900 words).\n"
            f"- Format: {adaptation['effective_format']} (bullets: concise facts; structured: headings with points; explanation: short readable paragraphs; mixed: short explanation plus key bullets)."
        )

        prompt_sections.extend(
            [
                "Current User Question:\n" + question,
                "Final Reminder:\nFollow the requested Markdown structure exactly.",
            ]
        )
        prompt = "\n\n".join(prompt_sections)

        print("=" * 80)
        print("PROMPT LENGTH:", len(prompt))
        print("=" * 80)
        print(prompt[:2000])
        print("=" * 80)

        return search_result, prompt, sources, resolved_conversation_id, classification, adaptation

    async def process(
        self, question: str, mode: str, conversation_id: str | None = None,
        subject: str | None = None, topic: str | None = None,
        preferred_language: str | None = None, preferred_depth: str | None = None,
        preferred_format: str | None = None,
        language: str | None = None, depth: str | None = None, format: str | None = None,
    ):

        print(f"[orchestrator] process() entry: question={question!r}, mode={mode!r}", flush=True)

        search_result, prompt, sources, resolved_conversation_id, classification, adaptation = await self._prepare_prompt(
            question, mode, conversation_id, subject, topic,
            preferred_language, preferred_depth, preferred_format,
            language, depth, format,
        )

        print("[orchestrator] before LLM.generate()", flush=True)

        start = time.perf_counter()

        answer = await self.llm.generate(
            prompt=prompt,
            mode=mode,
            depth=adaptation["effective_depth"],
        )
        answer = repair_mode_format(answer, mode)

        elapsed = time.perf_counter() - start

        print(f"LLM Generation Time: {elapsed:.2f} seconds", flush=True)

        print("[orchestrator] after LLM.generate()", flush=True)
        print("[orchestrator] before formatter", flush=True)

        assistant_message = self.memory_manager.add_assistant_message(
            conversation_id=resolved_conversation_id,
            content=answer,
        )
        self.activity_manager.record_event(
            "answer_generated", datetime.now(timezone.utc),
            conversation_id=resolved_conversation_id,
            subject=str(classification["subject"]),
            topic=str(classification["topic"]),
            metadata_json={
                "mode": self._mode_value(mode),
                "provider": search_result.get("provider", "local"),
                "message_id": assistant_message.id,
                "success": True,
            },
        )

        response = format_response(
            answer,
            provider=search_result.get("provider", "local"),
            sources=sources,
        )
        response["conversation_id"] = resolved_conversation_id
        response["subject"] = classification["subject"]
        response["topic"] = classification["topic"]
        response["effective_language"] = adaptation["effective_language"]
        response["effective_depth"] = adaptation["effective_depth"]
        response["effective_format"] = adaptation["effective_format"]

        print("[orchestrator] after formatter", flush=True)

        return response

    async def process_stream(
        self, question: str, mode: str, conversation_id: str | None = None,
        subject: str | None = None, topic: str | None = None,
        preferred_language: str | None = None, preferred_depth: str | None = None,
        preferred_format: str | None = None,
        language: str | None = None, depth: str | None = None, format: str | None = None,
    ) -> AsyncIterator[str | ConversationEvent]:

        print(f"[orchestrator] process_stream() entry: question={question!r}, mode={mode!r}", flush=True)
        print("[stream] started", flush=True)

        prepared = self._prepare_request(
            question, mode, conversation_id, subject, topic,
            preferred_language, preferred_depth, preferred_format,
            language, depth, format,
        )
        resolved_conversation_id, classification, adaptation, _history_text = prepared
        yield ConversationEvent(
            resolved_conversation_id, str(classification["subject"]), str(classification["topic"]),
            str(adaptation["effective_language"]), str(adaptation["effective_depth"]), str(adaptation["effective_format"])
        )
        search_result, prompt, _sources, resolved_conversation_id, classification, adaptation = await self._prepare_prompt(
            question, mode, conversation_id, subject, topic,
            preferred_language, preferred_depth, preferred_format,
            language, depth, format, prepared,
        )

        print("[orchestrator] before LLM.generate_stream()", flush=True)

        start = time.perf_counter()
        first_token = True
        parts: list[str] = []

        async for token in self.llm.generate_stream(
            prompt=prompt,
            mode=mode,
            depth=adaptation["effective_depth"],
        ):
            if first_token:
                print("[stream] first token", flush=True)
                first_token = False

            parts.append(token)
            yield token

        elapsed = time.perf_counter() - start

        print("[stream] finished", flush=True)
        print(f"LLM Generation Time: {elapsed:.2f} seconds", flush=True)

        completed_answer = "".join(parts)

        assistant_message = self.memory_manager.add_assistant_message(
            conversation_id=resolved_conversation_id,
            content=completed_answer,
        )
        self.activity_manager.record_event(
            "answer_generated", datetime.now(timezone.utc),
            conversation_id=resolved_conversation_id,
            subject=str(classification["subject"]),
            topic=str(classification["topic"]),
            metadata_json={
                "mode": self._mode_value(mode),
                "provider": search_result.get("provider", "local"),
                "message_id": assistant_message.id,
                "success": True,
            },
        )

        print("[orchestrator] after LLM.generate_stream()", flush=True)
