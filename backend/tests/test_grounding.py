import asyncio
import json
from datetime import datetime, timedelta, timezone

from src.core.config import settings
from src.search.grounding import GroundingDecisionService
from src.search.provider import SearchProvider
from src.search.web_search import TrustedSourcePolicy, WebCache, WebSearch
from src.schemas.visual_roadmap import VisualRoadmapCreate
from src.visual_roadmap.service import InsufficientContextError, VisualRoadmapService
from src.services.orchestrator.models import ResponseMode
from src.services.orchestrator.service import ConversationEvent
from tests.test_conversation_orchestrator import orchestrator


def chunk(score=.95, text="Relevant constitutional material", source_type="pdf"):
    return {"text": text, "score": score, "source_type": source_type, "document_name": "notes.pdf",
            "chunk_id": "c1", "metadata": {"page_start": 1, "page_end": 1}}


class Local:
    def __init__(self, chunks): self.chunks = chunks; self.calls = 0
    def search(self, _question):
        self.calls += 1
        return {"context": "local", "chunks": self.chunks, "sources": [{"source_type": "pdf", "title": "notes.pdf", "document_name": "notes.pdf", "document": "notes.pdf", "chunk_id": "c1", "page_start": 1, "page_end": 1}], "provider": "local"}


class Web:
    def __init__(self, chunks=None, error=None): self.chunks = chunks or []; self.calls = 0; self.error = error
    def search(self, _question):
        self.calls += 1
        if self.error: return {"context": "", "chunks": [], "sources": [], "provider": "web", "error": self.error}
        sources = [{"source_type": "web", "title": "Constitutional History", "document_name": None,
            "url": "https://legislative.gov.in/history", "publisher": "Government of India", "page_start": None,
            "page_end": None, "retrieved_at": datetime.now(timezone.utc).isoformat(), "trust_level": "official"}]
        return {"context": "trusted web", "chunks": self.chunks, "sources": sources, "provider": "web", "rejected_count": 0, "cache_hits": 0}


def test_relevant_pdf_prevents_web_and_sources_are_backward_compatible():
    web = Web([chunk(source_type="web")]); provider = SearchProvider(Local([chunk()]), web)
    result = provider.search("Explain the Constitution")
    assert web.calls == 0 and result["grounding"]["status"] == "sufficient"
    assert result["sources"][0]["source_type"] == "pdf" and result["sources"][0]["document"] == "notes.pdf"


def test_insufficient_pdf_triggers_approved_web(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_WEB_SEARCH", True)
    web_chunk = {**chunk(.95, source_type="web"), "source_url": "https://legislative.gov.in/history"}
    web = Web([web_chunk]); result = SearchProvider(Local([chunk(.2)]), web).search("Explain constitutional history")
    assert web.calls == 1 and result["provider"] == "trusted_web"
    assert result["sources"][0]["source_type"] == "web"


def test_web_disabled_and_search_failure_are_clear(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_WEB_SEARCH", False)
    result = SearchProvider(Local([]), Web([chunk(source_type="web")])).search("Explain constitutional history")
    assert result["grounding"]["status"] == "no_context" and not result["web_fallback_used"]
    monkeypatch.setattr(settings, "ENABLE_WEB_SEARCH", True)
    failed = SearchProvider(Local([]), Web(error="trusted_web_unavailable")).search("Explain constitutional history")
    assert failed["grounding"]["status"] == "no_context" and failed["web_error"] == "trusted_web_unavailable"


def test_absent_context_never_calls_model_and_stream_stays_progressive(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_WEB_SEARCH", False)
    service = orchestrator(tmp_path); service.search_provider = SearchProvider(Local([]), Web([]))
    result = asyncio.run(service.process("Explain constitutional history", ResponseMode.LEARN))
    assert "Reliable information was not found" in result["answer"] and service.llm.prompts == []
    async def collect(): return [item async for item in service.process_stream("Explain constitutional history", ResponseMode.LEARN)]
    events = asyncio.run(collect())
    assert isinstance(events[0], ConversationEvent) and events[1:] == [service.NO_RELIABLE_CONTEXT]


def test_trust_policy_rejects_unknown_and_official_ranks_higher():
    assert TrustedSourcePolicy.classify("https://unknown-blog.example/post") is None
    official = TrustedSourcePolicy.classify("https://legislative.gov.in/page")
    trusted = TrustedSourcePolicy.classify("https://www.un.org/page")
    assert official[2] == "official" and trusted[2] == "trusted"


def test_cache_deduplicates_reuses_and_has_freshness_classes(tmp_path, monkeypatch):
    cache = WebCache(tmp_path); now = datetime.now(timezone.utc)
    item = {"source_url": "https://rbi.org.in/page", "content_hash": "same", "retrieved_at": now.isoformat(), "text": "x"}
    cache.put(item); cache.put(item)
    assert len(list(tmp_path.glob("*.json"))) == 1 and cache.get(item["source_url"], current=False)
    path = next(tmp_path.glob("*.json")); old = {**item, "retrieved_at": (now - timedelta(hours=48)).isoformat()}
    path.write_text(json.dumps(old), encoding="utf-8")
    assert cache.get(item["source_url"], current=True) is None
    assert cache.get(item["source_url"], current=False) is not None


def test_grounding_threshold_is_stricter_for_roadmaps(monkeypatch):
    monkeypatch.setattr(settings, "CHAT_MIN_GROUNDING_CONFIDENCE", .7); monkeypatch.setattr(settings, "ROADMAP_MIN_GROUNDING_CONFIDENCE", .8)
    service = GroundingDecisionService(); chunks = [chunk(.75)]
    assert service.decide(chunks=chunks, question="Explain history", requested_operation="chat").status == "sufficient"
    assert service.decide(chunks=chunks, question="Explain history", requested_operation="roadmap").status == "insufficient"


class RoadmapSearch:
    def __init__(self, sufficient=True): self.sufficient = sufficient
    def search(self, _topic, operation):
        assert operation == "roadmap"
        if not self.sufficient: return {"chunks": [], "sources": [], "grounding": {"status": "no_context"}}
        return {"chunks": [{"text": "Regulating Act 1773 began parliamentary control", "score": 1.0, "source_type": "web",
            "source_url": "https://legislative.gov.in/history", "source_title": "Constitutional History", "publisher": "Government of India",
            "domain": "legislative.gov.in", "retrieved_at": datetime.now(timezone.utc).isoformat(), "source_category": "official_government",
            "trust_level": "official", "content_hash": "abc"}], "grounding": {"status": "sufficient"}}


class RoadmapLlm:
    async def generate(self, prompt, **_kwargs):
        sources = json.loads(prompt.split("Supplied sources array:\n", 1)[1].split("\n\nGrounded context:", 1)[0])
        return json.dumps({"title": "History", "visual_type": "timeline", "summary": "Development",
            "nodes": [{"id": "n1", "label": "Regulating Act", "year": "1773", "description": "Parliamentary control began.",
                "importance": "Early control", "source_ids": ["source_1"]}], "connections": [], "exam_points": [], "sources": sources})


def test_roadmap_uses_approved_web_and_rejects_insufficient(tmp_path):
    good = VisualRoadmapService(db_path=str(tmp_path/"good.sqlite3"), llm=RoadmapLlm(), search_provider=RoadmapSearch(), base_dir=tmp_path/"generated")
    row = asyncio.run(good.create(VisualRoadmapCreate(topic="Constitution history", visual_type="timeline")))
    assert row.source_metadata_json[0]["source_type"] == "web" and row.source_metadata_json[0]["trust_level"] == "official"
    bad = VisualRoadmapService(db_path=str(tmp_path/"bad.sqlite3"), llm=RoadmapLlm(), search_provider=RoadmapSearch(False), base_dir=tmp_path/"generated2")
    try: asyncio.run(bad.create(VisualRoadmapCreate(topic="Unknown history", visual_type="timeline")))
    except InsufficientContextError as error: assert "Insufficient trusted context" in str(error)
    else: raise AssertionError("Expected insufficient context")
