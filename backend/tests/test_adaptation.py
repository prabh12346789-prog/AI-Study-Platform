import asyncio

from src.ai.generation_config import get_generation_config
from src.services.adaptation import AdaptationPolicy
from src.services.orchestrator.models import ResponseMode
from tests.test_conversation_orchestrator import orchestrator


class Profile:
    preferred_language = "auto"
    preferred_depth = "standard"
    preferred_format = "mixed"


def test_language_detection_fallback_and_overrides():
    policy = AdaptationPolicy(); profile = Profile()
    assert policy.resolve(text="Explain inflation", profile=profile)["effective_language"] == "english"
    assert policy.resolve(text="ਮਹਿੰਗਾਈ ਸਮਝਾਓ", profile=profile, language="auto")["effective_language"] == "punjabi"
    assert policy.resolve(text="महंगाई समझाइए", profile=profile, language="auto")["effective_language"] == "hindi"
    profile.preferred_language = "hindi"
    assert policy.resolve(text="Explain inflation", profile=profile)["effective_language"] == "hindi"
    result = policy.resolve(text="Explain", profile=profile, language="punjabi", depth="quick", format="bullets")
    assert result["source"] == {"language": "message_override", "depth": "message_override", "format": "message_override"}


def test_depth_generation_limits():
    assert get_generation_config("learn", "quick")["num_predict"] < get_generation_config("learn", "detailed")["num_predict"]


def test_normal_and_streaming_use_one_effective_adaptation(tmp_path):
    service = orchestrator(tmp_path)
    service.profile_manager.update({"preferred_language": "hindi", "preferred_depth": "detailed", "preferred_format": "structured"})
    before = service.profile_manager.get_or_create().preferred_language
    response = asyncio.run(service.process(
        "Explain inflation", ResponseMode.LEARN, language="english", depth="quick", format="bullets"
    ))
    assert (response["effective_language"], response["effective_depth"], response["effective_format"]) == ("english", "quick", "bullets")
    assert response["sources"] == []
    assert service.profile_manager.get_or_create().preferred_language == before

    async def first():
        iterator = service.process_stream("Explain inflation", ResponseMode.LEARN, language="punjabi", depth="quick", format="bullets")
        event = await anext(iterator)
        await iterator.aclose()
        return event
    event = asyncio.run(first())
    assert (event.effective_language, event.effective_depth, event.effective_format) == ("punjabi", "quick", "bullets")


def test_existing_request_is_backward_compatible(tmp_path):
    response = asyncio.run(orchestrator(tmp_path).process("Explain Parliament", ResponseMode.LEARN))
    assert response["conversation_id"] and response["effective_language"]
