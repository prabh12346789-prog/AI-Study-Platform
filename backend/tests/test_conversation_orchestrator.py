import asyncio

import pytest

from src.memory.manager import MemoryManager
from src.activity.manager import ActivityManager
from src.profile.manager import ProfileManager
from src.services.orchestrator.models import ResponseMode
from src.services.orchestrator.service import AIOrchestrator, ConversationEvent


class FakeSearch:
    def search(self, question):
        return {"provider": "test", "sources": []}


class FakeLlm:
    def __init__(self):
        self.prompts = []

    async def generate(self, prompt, mode, depth="standard"):
        self.prompts.append(prompt)
        return "## Answer\nFinal answer"

    async def generate_stream(self, prompt, mode, depth="standard"):
        yield "## Answer\n"
        yield "Final answer"


def orchestrator(tmp_path):
    memory_path = str(tmp_path / "memory.sqlite3")
    activity_path = str(tmp_path / "activity.sqlite3")
    service = AIOrchestrator(
        MemoryManager(memory_path), ActivityManager(activity_path), ProfileManager(activity_path),
    )
    service.search_provider = FakeSearch()
    service.llm = FakeLlm()
    return service


def test_normal_chat_uses_explicit_conversation(tmp_path):
    service = orchestrator(tmp_path)
    conversation = service.memory_manager.create_conversation()
    response = asyncio.run(service.process("Explain Fundamental Rights", ResponseMode.LEARN, conversation.id))
    assert response["conversation_id"] == conversation.id
    assert [m.role for m in service.memory_manager.get_messages(conversation.id)] == ["user", "assistant"]
    assert [e.event_type for e in service.activity_manager.list_events()][::-1] == ["question_asked", "answer_generated"]
    events = service.activity_manager.list_events()
    assert {(event.subject, event.topic) for event in events} == {
        ("Polity and Governance", "Fundamental Rights")
    }
    assert response["subject"] == "Polity and Governance"


def test_stream_saves_only_final_assistant_message(tmp_path):
    service = orchestrator(tmp_path)
    async def collect():
        return [event async for event in service.process_stream("Explain inflation", ResponseMode.LEARN)]
    events = asyncio.run(collect())
    assert isinstance(events[0], ConversationEvent)
    assert events[1:] == ["## Answer\n", "Final answer"]
    assert len(events[1:]) > 1
    messages = service.memory_manager.get_messages(events[0].conversation_id)
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[-1].content == "".join(events[1:])
    assert len(messages) == 2
    assert [e.event_type for e in service.activity_manager.list_events()][::-1] == ["question_asked", "answer_generated"]


def test_failed_stream_does_not_save_partial_assistant_response(tmp_path):
    service = orchestrator(tmp_path)

    async def fail_after_token(prompt, mode, depth="standard"):
        yield "partial"
        raise RuntimeError("stream failed")

    service.llm.generate_stream = fail_after_token

    async def collect():
        return [event async for event in service.process_stream("Explain inflation", ResponseMode.LEARN)]

    with pytest.raises(RuntimeError, match="stream failed"):
        asyncio.run(collect())
    conversations = service.memory_manager.list_conversations()
    messages = service.memory_manager.get_messages(conversations[0].id)
    assert [message.role for message in messages] == ["user"]
    assert [event.event_type for event in service.activity_manager.list_events()] == ["question_asked"]


def test_failed_generation_does_not_record_answer_event(tmp_path):
    service = orchestrator(tmp_path)

    async def fail(prompt, mode, depth="standard"):
        raise RuntimeError("generation failed")

    service.llm.generate = fail
    with pytest.raises(RuntimeError, match="generation failed"):
        asyncio.run(service.process("Explain Parliament", ResponseMode.LEARN))
    assert [event.event_type for event in service.activity_manager.list_events()] == ["question_asked"]


def test_missing_id_is_backward_compatible_and_invalid_id_is_clear(tmp_path):
    service = orchestrator(tmp_path)
    response = asyncio.run(service.process("Explain Parliament", ResponseMode.LEARN))
    assert response["conversation_id"]
    with pytest.raises(ValueError, match="not found"):
        asyncio.run(service.process("Hello", ResponseMode.LEARN, "invalid"))


def test_deterministic_title_is_short():
    assert AIOrchestrator._title_from_question("Explain Fundamental Rights in simple words") == "Fundamental Rights"
    assert len(AIOrchestrator._title_from_question("one two three four five six seven").split()) == 6


def test_fundamental_rights_and_inflation_conversations_remain_isolated(tmp_path):
    service = orchestrator(tmp_path)
    conversation_a = service.memory_manager.create_conversation("Fundamental Rights")
    conversation_b = service.memory_manager.create_conversation("Inflation")

    asyncio.run(service.process("Explain Fundamental Rights", ResponseMode.LEARN, conversation_a.id))
    asyncio.run(service.process("Explain Inflation", ResponseMode.LEARN, conversation_b.id))
    asyncio.run(service.process("What about Article 32?", ResponseMode.LEARN, conversation_a.id))

    inflation_prompt = service.llm.prompts[1]
    article_32_prompt = service.llm.prompts[2]
    assert "Explain Fundamental Rights" not in inflation_prompt
    assert "Explain Inflation" not in article_32_prompt
    assert "Explain Fundamental Rights" in article_32_prompt

    assert [m.content for m in service.memory_manager.get_messages(conversation_a.id) if m.role == "user"] == [
        "Explain Fundamental Rights",
        "What about Article 32?",
    ]
    assert [m.content for m in service.memory_manager.get_messages(conversation_b.id) if m.role == "user"] == [
        "Explain Inflation",
    ]


def test_chat_loads_profile_and_request_preferences_override_it(tmp_path):
    service = orchestrator(tmp_path)
    service.profile_manager.update({
        "preferred_language": "hindi", "preferred_depth": "detailed",
        "preferred_format": "explanation",
    })
    asyncio.run(service.process("Explain Parliament", ResponseMode.LEARN))
    assert "Respond in hindi" in service.llm.prompts[-1]
    assert "Depth: detailed" in service.llm.prompts[-1]

    asyncio.run(service.process(
        "Explain Parliament", ResponseMode.LEARN,
        preferred_language="english", preferred_depth="quick", preferred_format="bullets",
    ))
    assert "Respond in english" in service.llm.prompts[-1]
    assert "Depth: quick" in service.llm.prompts[-1]
    assert "Format: bullets" in service.llm.prompts[-1]
    assert service.profile_manager.get_or_create().preferred_language == "hindi"
