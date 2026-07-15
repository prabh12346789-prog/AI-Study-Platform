import asyncio

from src.ai.generation_config import get_generation_config
from src.services.adaptation import AdaptationPolicy
from src.services.orchestrator.models import ResponseMode
from src.services.orchestrator.prompts import build_presentation_instructions
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


def test_learn_format_matrix_has_no_fixed_template():
    bullets = build_presentation_instructions(ResponseMode.LEARN, "bullets", "standard")["format"]
    explanation = build_presentation_instructions(ResponseMode.LEARN, "explanation", "standard")["format"]
    structured = build_presentation_instructions(ResponseMode.LEARN, "structured", "standard")["format"]
    mixed = build_presentation_instructions(ResponseMode.LEARN, "mixed", "standard")["format"]
    assert "5–8 explanatory bullets" in bullets and "do not require Definition" in bullets
    assert "2–4 short connected paragraphs" in explanation and "Do not use Markdown headings or bullet markers" in explanation
    assert "topic-specific headings" in structured and "never default mechanically" in structured
    assert "overview paragraph" in mixed and "4–6 key bullets" in mixed


def test_exam_mode_format_combinations_remain_purpose_specific():
    prelims = build_presentation_instructions(ResponseMode.PRELIMS, "structured", "standard")["format"]
    mains = build_presentation_instructions(ResponseMode.MAINS, "structured", "detailed")["format"]
    interview = build_presentation_instructions(ResponseMode.INTERVIEW, "explanation", "quick")["format"]
    revision = build_presentation_instructions(ResponseMode.REVISION, "bullets", "quick")["format"]
    assert all(value in prelims for value in ("Core Facts", "Important Provisions", "Prelims Traps"))
    assert all(value in mains for value in ("Introduction", "Challenges", "Way Forward", "Conclusion"))
    assert "conversationally" in interview and "practical conclusion" in interview
    assert "compact recall points only" in revision


def test_prompt_priority_exact_question_and_message_format_override(tmp_path):
    service = orchestrator(tmp_path)
    service.profile_manager.update({"preferred_format": "structured"})
    conversation = service.memory_manager.create_conversation("Constitution")
    service.memory_manager.add_user_message(conversation.id, "What is the Indian Constitution?")
    asyncio.run(service.process(
        "Historical Background of the Indian Constitution", ResponseMode.LEARN,
        conversation_id=conversation.id, format="explanation",
    ))
    prompt = service.llm.prompts[-1]
    assert "Selected Presentation Format (explanation)" in prompt
    assert prompt.index("2. Exact Current User Question") < prompt.index("8. Conversation History")
    assert "Do not replace it with a broader or easier generic topic" in prompt
    exact_section = prompt.split("3. UPSC Mode Intent:", 1)[0]
    assert "Historical Background of the Indian Constitution" in exact_section
    assert "constitutional-development chronology" in exact_section
    assert "Do not substitute a definition" in exact_section
    assert "History is background only and must not override" in prompt


def test_normal_and_streaming_build_same_prompt_policy(tmp_path):
    service = orchestrator(tmp_path)
    asyncio.run(service.process("Historical Background of the Indian Constitution", ResponseMode.LEARN, format="mixed"))
    normal_prompt = service.llm.prompts[-1]

    async def capture_stream():
        return [item async for item in service.process_stream(
            "Historical Background of the Indian Constitution", ResponseMode.LEARN, format="mixed"
        )]
    asyncio.run(capture_stream())
    stream_prompt = service.llm.prompts[-1]
    for marker in ("Accuracy and Grounding Rules", "Exact Current User Question", "UPSC Mode Intent", "Selected Presentation Format (mixed)"):
        assert marker in normal_prompt and marker in stream_prompt
