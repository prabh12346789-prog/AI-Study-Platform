import json
import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.activity.manager import ActivityManager
from src.schemas.visual_roadmap import RoadmapStructure, VisualRoadmapCreate
from src.visual_roadmap.service import InsufficientContextError, VisualRoadmapService


def payload(visual_type="timeline", nodes=None, connections=None):
    sources = [{"id": "source_1", "document": "notes.pdf", "page_start": 1, "page_end": 1, "chunk_id": "c1"}]
    return {"title": "Constitutional development", "visual_type": visual_type, "summary": "A grounded overview.",
            "nodes": nodes or [{"id": "n1", "label": "Regulating Act", "year": "1773", "description": "Parliamentary control began.", "importance": "Early central control.", "source_ids": ["source_1"]}],
            "connections": connections or [], "exam_points": ["Connect Acts to institutional change."], "sources": sources}


class FakeRetriever:
    def __init__(self, available=True): self.available = available
    def retrieve(self, _topic):
        return [{"document_name": "notes.pdf", "chunk_id": "c1", "text": "The Regulating Act of 1773 began parliamentary control.", "score": .95, "metadata": {"page_start": 1, "page_end": 1}}] if self.available else []


class FakeLLM:
    def __init__(self, visual_type="timeline"): self.visual_type = visual_type
    async def generate(self, **_kwargs): return json.dumps(payload(self.visual_type))


class SequenceLLM:
    def __init__(self, *responses): self.responses = iter(responses); self.prompts = []
    async def generate(self, **kwargs):
        self.prompts.append(kwargs["prompt"])
        response = next(self.responses)
        if isinstance(response, Exception): raise response
        return response


def service(tmp_path, visual_type="timeline", available=True):
    db = str(tmp_path / "roadmaps.sqlite3")
    return VisualRoadmapService(db_path=db, retriever=FakeRetriever(available), llm=FakeLLM(visual_type),
        activity_manager=ActivityManager(db), base_dir=tmp_path / "generated")


def test_timeline_and_flowchart_schema_validation():
    assert RoadmapStructure.model_validate(payload()).visual_type == "timeline"
    assert RoadmapStructure.model_validate(payload("flowchart")).visual_type == "flowchart"


def test_duplicate_ids_invalid_connection_node_limit_and_source_rejected():
    node = payload()["nodes"][0]
    with pytest.raises(ValidationError): RoadmapStructure.model_validate(payload(nodes=[node, node]))
    with pytest.raises(ValidationError): RoadmapStructure.model_validate(payload(connections=[{"from": "n1", "to": "missing", "label": "then"}]))
    with pytest.raises(ValidationError): RoadmapStructure.model_validate(payload(nodes=[{**node, "id": f"n{i}"} for i in range(13)]))
    with pytest.raises(ValidationError): RoadmapStructure.model_validate(payload(nodes=[{**node, "source_ids": ["unknown"]}]))
    with pytest.raises(ValidationError): RoadmapStructure.model_validate({**payload(), "unknown": True})


@pytest.mark.parametrize("raw", [
    lambda value: json.dumps(value),
    lambda value: f"```json\n{json.dumps(value)}\n```",
    lambda value: f"Here is the roadmap:\n{json.dumps(value)}\nThis is grounded.",
    lambda value: json.dumps(value).replace('"sources":', '"exam_points": [], "sources":').replace('"exam_points": [], "exam_points": [],', '"exam_points": [],').replace(']}', '],}', 1),
])
def test_safe_parser_accepts_direct_fenced_prose_and_trailing_comma(raw):
    expected = payload()
    assert VisualRoadmapService._json(raw(expected))["title"] == expected["title"]


def test_schema_rejects_missing_fields_and_invalid_edges():
    missing = payload(); missing.pop("summary")
    with pytest.raises(ValidationError): RoadmapStructure.model_validate(missing)
    invalid = payload(connections=[{"from": "n1", "to": "missing", "label": "then"}])
    with pytest.raises(ValidationError): RoadmapStructure.model_validate(invalid)
    missing_node_field = payload(); missing_node_field["nodes"][0].pop("importance")
    with pytest.raises(ValueError, match="node has missing"):
        VisualRoadmapService._validate_structure(
            missing_node_field, VisualRoadmapCreate(topic="Constitution", visual_type="timeline"),
            missing_node_field["sources"],
        )


def test_valid_roadmap_creates_accessible_svg_and_activity(tmp_path):
    svc = service(tmp_path)
    row = asyncio.run(svc.create(VisualRoadmapCreate(topic="Indian Constitution", visual_type="timeline", language="english")))
    svg = Path(row.svg_path).read_text(encoding="utf-8")
    assert row.title in svg and "Regulating Act" in svg and "<title" in svg and "<desc" in svg
    events = svc.activity.list_events(event_type="visual_roadmap_generated")
    assert events[0].metadata_json["roadmap_id"] == row.id


def test_insufficient_context_is_clear(tmp_path):
    with pytest.raises(InsufficientContextError, match="Upload a relevant PDF"):
        asyncio.run(service(tmp_path, available=False).create(VisualRoadmapCreate(topic="Unknown topic", visual_type="timeline")))


def test_listing_filtering_retrieval_isolation_and_safe_deletion(tmp_path):
    svc = service(tmp_path)
    row = asyncio.run(svc.create(VisualRoadmapCreate(topic="Indian Constitution", visual_type="timeline")))
    assert svc.list(visual_type="timeline")[0].id == row.id
    assert svc.list(visual_type="process") == []
    assert svc.get(row.id).id == row.id and svc.get(row.id, user_id="other") is None
    directory = Path(row.svg_path).parent
    assert svc.delete(row.id) and not directory.exists() and svc.get(row.id) is None
    with pytest.raises(ValueError): svc._directory("user_001", "../escape")


def test_roadmap_activity_does_not_create_mastery(tmp_path):
    svc = service(tmp_path)
    asyncio.run(svc.create(VisualRoadmapCreate(topic="Indian Constitution", visual_type="timeline")))
    from src.mastery.manager import MasteryManager
    assert MasteryManager(str(tmp_path / "roadmaps.sqlite3")).list_topic_mastery() == []


def test_one_schema_guided_repair_succeeds(tmp_path):
    llm = SequenceLLM('{"title":', json.dumps(payload()))
    svc = VisualRoadmapService(db_path=str(tmp_path / "repair.sqlite3"), retriever=FakeRetriever(), llm=llm,
        activity_manager=ActivityManager(str(tmp_path / "repair.sqlite3")), base_dir=tmp_path / "generated")
    row = asyncio.run(svc.create(VisualRoadmapCreate(topic="Indian Constitution", visual_type="timeline")))
    assert row.status == "ready" and len(llm.prompts) == 2
    assert "Required node keys" in llm.prompts[1]


def test_malformed_model_uses_grounded_deterministic_fallback(tmp_path):
    text = ("The Regulating Act of 1773 began parliamentary control. "
            "Pitt's India Act of 1784 established dual control. "
            "The Charter Act of 1833 centralized legislative power.")
    retriever = FakeRetriever(); retriever.retrieve = lambda _topic: [{"document_name": "notes.pdf", "chunk_id": "c1",
        "text": text, "score": .95, "metadata": {"page_start": 2, "page_end": 3}}]
    llm = SequenceLLM("not json", "still not json")
    db = str(tmp_path / "fallback.sqlite3")
    svc = VisualRoadmapService(db_path=db, retriever=retriever, llm=llm,
        activity_manager=ActivityManager(db), base_dir=tmp_path / "generated")
    row = asyncio.run(svc.create(VisualRoadmapCreate(topic="Constitution history", visual_type="timeline")))
    structure = RoadmapStructure.model_validate(row.structure_json)
    assert [node.year for node in structure.nodes] == ["1773", "1784", "1833"]
    assert all(node.source_ids == ["source_1"] for node in structure.nodes)
    assert all(node.description in text for node in structure.nodes)
    assert row.source_metadata_json[0]["page_start"] == 2
    metadata = json.loads((Path(row.svg_path).parent / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["generation_method"] == "deterministic_fallback"
    event = svc.activity.list_events(event_type="visual_roadmap_generated")[0]
    assert event.metadata_json["generation_method"] == "deterministic_fallback"
    svg = Path(row.svg_path).read_text(encoding="utf-8")
    assert "Regulating Act" in svg and "Sources: source_1" in svg


def test_model_unavailable_has_readable_error(tmp_path):
    llm = SequenceLLM(RuntimeError("model not found"))
    svc = VisualRoadmapService(db_path=str(tmp_path / "missing.sqlite3"), retriever=FakeRetriever(), llm=llm,
        activity_manager=ActivityManager(str(tmp_path / "missing.sqlite3")), base_dir=tmp_path / "generated")
    with pytest.raises(ValueError, match="model is unavailable"):
        asyncio.run(svc.create(VisualRoadmapCreate(topic="Indian Constitution", visual_type="timeline")))
