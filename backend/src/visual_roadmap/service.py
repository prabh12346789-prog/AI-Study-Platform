from __future__ import annotations

import asyncio
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select

from src.activity.manager import ActivityManager
from src.activity.taxonomy import SubjectTopicClassifier
from src.ai.factory import get_llm
from src.memory.manager import MemoryManager
from src.memory.storage import get_session_factory
from src.rag.retriever import Retriever
from src.search.local_search import LocalSearch
from src.search.provider import SearchProvider
from src.schemas.visual_roadmap import RoadmapStructure, VisualRoadmapCreate
from src.visual_roadmap.models import VisualRoadmap
from src.visual_roadmap.renderer import render_svg


class InsufficientContextError(ValueError): pass
class RoadmapGenerationError(ValueError): pass


class VisualRoadmapService:
    BASE_DIR = Path(__file__).resolve().parents[2] / "generated" / "users"

    def __init__(self, db_path=None, retriever=None, llm=None, activity_manager=None, base_dir=None, search_provider=None):
        self.sessions = get_session_factory(db_path)
        self.retriever = retriever or Retriever()
        local_search = LocalSearch(); local_search.retriever = self.retriever
        self.search_provider = search_provider or SearchProvider(local_search=local_search)
        self.llm = llm or get_llm()
        self.activity = activity_manager or ActivityManager(db_path)
        self.classifier = SubjectTopicClassifier()
        self.base_dir = Path(base_dir) if base_dir else self.BASE_DIR

    def _directory(self, user_id: str, roadmap_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", user_id) or not re.fullmatch(r"[A-Za-z0-9_-]+", roadmap_id):
            raise ValueError("Invalid roadmap path identifier")
        base = (self.base_dir / user_id / "roadmaps").resolve()
        target = (base / roadmap_id).resolve()
        if base not in target.parents: raise ValueError("Invalid roadmap path")
        return target

    @staticmethod
    def _sources(chunks):
        result = []
        for i, chunk in enumerate(chunks):
            if chunk.get("source_type") == "web":
                result.append({"id": f"source_{i+1}", "source_type": "web", "document": None,
                    "title": chunk.get("source_title"), "url": chunk.get("source_url"), "publisher": chunk.get("publisher"),
                    "domain": chunk.get("domain"), "retrieved_at": chunk.get("retrieved_at"),
                    "source_category": chunk.get("source_category"), "trust_level": chunk.get("trust_level"),
                    "page_start": None, "page_end": None, "chunk_id": chunk.get("content_hash")})
            else:
                result.append({"id": f"source_{i+1}", "source_type": "pdf",
                    "document": chunk.get("document_name") or "Uploaded study material",
                    "title": chunk.get("document_name") or "Uploaded study material", "url": None, "publisher": None,
                    "page_start": chunk.get("metadata", {}).get("page_start"), "page_end": chunk.get("metadata", {}).get("page_end"),
                    "chunk_id": str(chunk.get("chunk_id")) if chunk.get("chunk_id") is not None else None})
        return result

    @staticmethod
    def _first_json_object(text: str) -> str:
        start = text.find("{")
        if start < 0:
            raise json.JSONDecodeError("No JSON object found", text, 0)
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            character = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    in_string = False
                continue
            if character == '"':
                in_string = True
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
        raise json.JSONDecodeError("Unterminated JSON object", text, start)

    @classmethod
    def _json(cls, text: str):
        cleaned = re.sub(r"```(?:json)?", "", text.strip(), flags=re.I).replace("```", "")
        candidate = cls._first_json_object(cleaned)
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        return json.loads(candidate)

    @staticmethod
    def _example(visual_type: str, sources: list[dict]) -> dict:
        source = sources[0]
        return {
            "title": "Grounded topic roadmap",
            "visual_type": visual_type,
            "summary": "Concise summary supported by the retrieved context.",
            "nodes": [
                {"id": "n1", "label": "First grounded fact", "year": None,
                 "description": "A fact copied or closely paraphrased from the context.",
                 "importance": "", "source_ids": [source["id"]]},
                {"id": "n2", "label": "Second grounded fact", "year": None,
                 "description": "Another fact supported by the context.",
                 "importance": "", "source_ids": [source["id"]]},
            ],
            "connections": [{"from": "n1", "to": "n2", "label": "leads to"}],
            "exam_points": [],
            "sources": sources,
        }

    @classmethod
    def _prompt(cls, request: VisualRoadmapCreate, sources: list[dict], context: str) -> str:
        example = cls._example(request.visual_type, sources)
        return f"""Create one UPSC visual roadmap using ONLY the supplied grounded context.
Return exactly one JSON object. Do not use Markdown fences. Do not write any explanation before or after JSON.
Visual type must be exactly: {request.visual_type}
Language: {request.language}
Topic: {request.topic}

The object must contain exactly these keys:
title, visual_type, summary, nodes, connections, exam_points, sources
Each node must contain exactly: id, label, year, description, importance, source_ids
Each connection must contain exactly: from, to, label
Use 2 to 8 nodes and at most 12 connections. Node IDs must be unique. Connections must reference existing node IDs.
Every node must cite one or more supplied source IDs. Do not invent facts, dates, relationships, or sources.
Copy the supplied sources array exactly. Keep labels under 90 characters and descriptions under 280 characters.

Small valid {request.visual_type} example (shape only; do not copy its placeholder facts):
{json.dumps(example, ensure_ascii=False)}

Supplied sources array:
{json.dumps(sources, ensure_ascii=False)}

Grounded context:
{context}
"""

    @staticmethod
    def _validate_structure(data, request: VisualRoadmapCreate, sources: list[dict]) -> RoadmapStructure:
        if not isinstance(data, dict):
            raise ValueError("Roadmap output must be a JSON object")
        root_keys = {"title", "visual_type", "summary", "nodes", "connections", "exam_points", "sources"}
        if set(data) != root_keys:
            raise ValueError("Roadmap output has missing or unknown root fields")
        node_keys = {"id", "label", "year", "description", "importance", "source_ids"}
        if any(not isinstance(node, dict) or set(node) != node_keys for node in data.get("nodes", [])):
            raise ValueError("Roadmap node has missing or unknown fields")
        connection_keys = {"from", "to", "label"}
        if any(not isinstance(edge, dict) or set(edge) != connection_keys for edge in data.get("connections", [])):
            raise ValueError("Roadmap connection has missing or unknown fields")
        structure = RoadmapStructure.model_validate(data)
        if structure.visual_type != request.visual_type:
            raise ValueError("Generated visual type does not match request")
        allowed = {source["id"] for source in sources}
        if {source.id for source in structure.sources} != allowed:
            raise ValueError("Roadmap contains unsupported source IDs")
        return structure

    @staticmethod
    def _facts(text: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", text).strip()
        parts = re.split(r"(?<=[.!?])\s+|\s*[•|]\s*|\s+-\s+", normalized)
        return [part.strip(" -•") for part in parts if len(part.strip(" -•")) >= 18]

    @classmethod
    def _fallback(cls, request: VisualRoadmapCreate, chunks: list[dict], sources: list[dict]) -> RoadmapStructure:
        candidates = []
        for index, chunk in enumerate(chunks):
            for fact in cls._facts(str(chunk.get("text", "")))[:8]:
                candidates.append((fact, sources[index]["id"]))
        candidates = candidates[:8]
        if not candidates:
            raise RoadmapGenerationError("Malformed model output and grounded context could not produce a safe roadmap fallback.")
        nodes = []
        for index, (fact, source_id) in enumerate(candidates, start=1):
            year_match = re.search(r"\b(?:1[5-9]\d{2}|20\d{2})\b", fact) if request.visual_type == "timeline" else None
            label_text = re.split(r"[,:;]", fact, maxsplit=1)[0].strip()
            nodes.append({
                "id": f"n{index}", "label": label_text[:90],
                "year": year_match.group(0) if year_match else None,
                "description": fact[:280], "importance": "", "source_ids": [source_id],
            })
        connections = [
            {"from": f"n{index}", "to": f"n{index + 1}",
             "label": "followed by" if request.visual_type == "timeline" else "next"}
            for index in range(1, len(nodes))
        ]
        return cls._validate_structure({
            "title": request.topic[:180], "visual_type": request.visual_type,
            "summary": "A deterministic roadmap assembled only from the retrieved grounded context.",
            "nodes": nodes, "connections": connections, "exam_points": [], "sources": sources,
        }, request, sources)

    async def create(self, request: VisualRoadmapCreate, user_id="user_001"):
        if request.conversation_id and not MemoryManager().get_conversation(request.conversation_id):
            raise ValueError("Conversation not found")
        classification = self.classifier.classify(request.topic)
        search_result = await asyncio.to_thread(self.search_provider.search, request.topic, "roadmap")
        chunks = search_result.get("chunks", [])
        grounding = search_result.get("grounding", {})
        if grounding.get("status") != "sufficient" or not chunks:
            raise InsufficientContextError("Insufficient trusted context. Upload a relevant PDF, enable/configure trusted web search, or choose another topic; no roadmap was generated.")
        sources = self._sources(chunks)
        context = "\n\n".join(f"[{sources[i]['id']}] {c['text']}" for i, c in enumerate(chunks))
        prompt = self._prompt(request, sources, context)
        try:
            raw = await self.llm.generate(prompt=prompt, mode="learn", depth="standard")
        except Exception as error:
            raise RoadmapGenerationError("Roadmap generation model is unavailable. Confirm Ollama and the configured model are installed.") from error
        generation_method = "model"
        try:
            structure = self._validate_structure(self._json(raw), request, sources)
        except (json.JSONDecodeError, ValidationError, ValueError) as first_error:
            repair = f"""Repair the output into exactly one JSON object matching this schema. Return JSON only; no fences or prose.
Required root keys: title, visual_type, summary, nodes, connections, exam_points, sources.
Required node keys: id, label, year, description, importance, source_ids.
Required connection keys: from, to, label.
Visual type must be {request.visual_type}. Use only these sources: {json.dumps(sources, ensure_ascii=False)}
Do not add or change facts. Validation error: {first_error}
Malformed output:
{raw}"""
            try:
                repaired = await self.llm.generate(prompt=repair, mode="learn", depth="quick")
                structure = self._validate_structure(self._json(repaired), request, sources)
                generation_method = "model_repair"
            except Exception:
                structure = self._fallback(request, chunks, sources)
                generation_method = "deterministic_fallback"
        roadmap_id = str(uuid.uuid4()); directory = self._directory(user_id, roadmap_id); directory.mkdir(parents=True)
        svg = render_svg(structure); svg_path = directory / "roadmap.svg"
        structure_data = structure.model_dump(by_alias=True, mode="json")
        (directory / "roadmap.json").write_text(json.dumps(structure_data, ensure_ascii=False, indent=2), encoding="utf-8")
        svg_path.write_text(svg, encoding="utf-8")
        (directory / "sources.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
        metadata = {"roadmap_id": roadmap_id, "language": request.language, "generation_method": generation_method,
            "scene_order": [n.id for n in structure.nodes], "narration_text": structure.summary}
        (directory / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        row = VisualRoadmap(id=roadmap_id, user_id=user_id, conversation_id=request.conversation_id,
            title=structure.title, subject=str(classification["subject"]), topic=str(classification["topic"]),
            visual_type=request.visual_type, language=request.language, status="ready", structure_json=structure_data,
            source_metadata_json=sources, svg_path=str(svg_path), png_path=None)
        with self.sessions() as session:
            session.add(row); session.commit(); session.refresh(row)
        self.activity.record_event("visual_roadmap_generated", datetime.now(timezone.utc), user_id=user_id,
            conversation_id=request.conversation_id, subject=row.subject, topic=row.topic,
            metadata_json={"roadmap_id": row.id, "visual_type": row.visual_type, "language": row.language,
                "generation_method": generation_method})
        return row

    def get(self, roadmap_id, user_id="user_001", opened=False):
        with self.sessions() as session:
            row = session.scalar(select(VisualRoadmap).where(VisualRoadmap.id == roadmap_id, VisualRoadmap.user_id == user_id))
        if row and opened:
            self.activity.record_event("visual_roadmap_opened", datetime.now(timezone.utc), user_id=user_id,
                conversation_id=row.conversation_id, subject=row.subject, topic=row.topic,
                metadata_json={"roadmap_id": row.id, "visual_type": row.visual_type, "language": row.language})
        return row

    def list(self, user_id="user_001", **filters):
        with self.sessions() as session:
            query = select(VisualRoadmap).where(VisualRoadmap.user_id == user_id)
            for name, value in filters.items():
                if value: query = query.where(getattr(VisualRoadmap, name) == value)
            return list(session.scalars(query.order_by(VisualRoadmap.created_at.desc())))

    def delete(self, roadmap_id, user_id="user_001"):
        row = self.get(roadmap_id, user_id)
        if not row: return False
        directory = self._directory(user_id, roadmap_id)
        with self.sessions() as session:
            stored = session.get(VisualRoadmap, roadmap_id); session.delete(stored); session.commit()
        if directory.exists(): shutil.rmtree(directory)
        return True
