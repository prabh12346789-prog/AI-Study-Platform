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
    def _json(text: str):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
        return json.loads(text)

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
        prompt = f"""Create a UPSC visual roadmap using ONLY the retrieved context. Return JSON only, no markdown.
Visual type: {request.visual_type}. Language: {request.language}. Topic: {request.topic}.
Required keys: title, visual_type, summary, nodes, connections, exam_points, sources.
Each node: id, label (max 90 chars), year or null, description (max 280 chars), importance, source_ids.
Maximum 12 nodes. Every fact/year and every node must be supported by its source_ids. Connections use from, to, label and valid node IDs.
Copy this exact sources array into the response: {json.dumps(sources)}
Retrieved context:\n{context}"""
        raw = await self.llm.generate(prompt=prompt, mode="learn", depth="standard")
        try:
            data = self._json(raw)
            structure = RoadmapStructure.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as first_error:
            repair = f"Repair only the JSON syntax/schema of the following output. Do not add or change facts. Return JSON only. Error: {first_error}\nOUTPUT:\n{raw}"
            raw = await self.llm.generate(prompt=repair, mode="learn", depth="quick")
            structure = RoadmapStructure.model_validate(self._json(raw))
        if structure.visual_type != request.visual_type: raise ValueError("Generated visual type does not match request")
        allowed = {s["id"] for s in sources}
        if {s.id for s in structure.sources} != allowed: raise ValueError("Roadmap contains unsupported source IDs")
        roadmap_id = str(uuid.uuid4()); directory = self._directory(user_id, roadmap_id); directory.mkdir(parents=True)
        svg = render_svg(structure); svg_path = directory / "roadmap.svg"
        structure_data = structure.model_dump(by_alias=True, mode="json")
        (directory / "roadmap.json").write_text(json.dumps(structure_data, ensure_ascii=False, indent=2), encoding="utf-8")
        svg_path.write_text(svg, encoding="utf-8")
        (directory / "sources.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
        metadata = {"roadmap_id": roadmap_id, "language": request.language, "scene_order": [n.id for n in structure.nodes], "narration_text": structure.summary}
        (directory / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        row = VisualRoadmap(id=roadmap_id, user_id=user_id, conversation_id=request.conversation_id,
            title=structure.title, subject=str(classification["subject"]), topic=str(classification["topic"]),
            visual_type=request.visual_type, language=request.language, status="ready", structure_json=structure_data,
            source_metadata_json=sources, svg_path=str(svg_path), png_path=None)
        with self.sessions() as session:
            session.add(row); session.commit(); session.refresh(row)
        self.activity.record_event("visual_roadmap_generated", datetime.now(timezone.utc), user_id=user_id,
            conversation_id=request.conversation_id, subject=row.subject, topic=row.topic,
            metadata_json={"roadmap_id": row.id, "visual_type": row.visual_type, "language": row.language})
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
