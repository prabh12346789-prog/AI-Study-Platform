from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import or_, select, func

from src.activity.manager import ActivityManager
from src.activity.taxonomy import SubjectTopicClassifier
from src.core.config import settings
from src.memory.storage import get_session_factory
from src.rag.embeddings import EmbeddingService
from src.rag.vector_store import VectorStore
from src.upsc_notes.models import NoteCollection, UPSCNote, SavedNote, NoteReadingProgress

log = logging.getLogger(__name__)

OFFICIAL_NOTES_HUBS = [
    "https://pwonlyias.com/downloads/",
    "https://pwonlyias.com/upsc-free-study-material/",
    "https://pwonlyias.com/upsc-exam-study-material/",
    "https://pwonlyias.com/udaan/",
    "https://pwonlyias.com/udaan-2-booklets/",
    "https://pwonlyias.com/onlyias-all-books/",
    "https://pwonlyias.com/books/",
    "https://pwonlyias.com/ncert-wallah-books/",
]

CORE_SUBJECT_MAP = {
    "polity": "Indian Polity and Governance",
    "indian polity": "Indian Polity and Governance",
    "polity and governance": "Indian Polity and Governance",
    "history": "History",
    "art and culture": "Art and Culture",
    "geography": "Geography",
    "economy": "Indian Economy",
    "indian economy": "Indian Economy",
    "environment": "Environment and Ecology",
    "environment and ecology": "Environment and Ecology",
    "science & tech": "Science and Technology",
    "science and technology": "Science and Technology",
    "ir": "International Relations",
    "international relations": "International Relations",
    "society": "Indian Society and Social Justice",
    "social justice": "Indian Society and Social Justice",
    "internal security": "Internal Security",
    "disaster management": "Disaster Management",
    "ethics": "Ethics",
    "agriculture": "Agriculture",
    "budget": "Budget and Economic Survey",
    "economic survey": "Budget and Economic Survey",
    "essay": "Essay",
}


import ipaddress
import io
from urllib.parse import urlsplit
import pypdf


def is_valid_pwonlyias_source_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    try:
        parts = urlsplit(url)
    except Exception:
        return False

    if parts.scheme not in ("http", "https"):
        return False

    if parts.username or parts.password:
        return False

    hostname = parts.hostname
    if not hostname:
        return False
    hostname = hostname.casefold()

    if hostname == "localhost":
        return False

    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
        return False
    except ValueError:
        pass

    if hostname == "pwonlyias.com" or hostname.endswith(".pwonlyias.com"):
        return True

    return False


def extract_pdf_blocks(pdf_bytes: bytes, max_size_mb: int = 50) -> tuple[list[dict], int, str]:
    if not pdf_bytes or len(pdf_bytes) > max_size_mb * 1024 * 1024:
        return [], 0, "failed"

    stripped = pdf_bytes.lstrip()
    if not stripped.startswith(b"%PDF"):
        return [], 0, "failed"

    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        page_count = len(reader.pages)
        if page_count == 0:
            return [], 0, "failed"

        all_blocks = []
        has_text = False

        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                has_text = True
                page_blocks = UPSCNotesService.extract_html_blocks(text)
                for b in page_blocks:
                    b["page_start"] = i
                    b["page_end"] = i
                    b["page_ref"] = i
                    all_blocks.append(b)

        if not has_text:
            return [], page_count, "image_only"

        return all_blocks, page_count, "ready"
    except Exception as err:
        log.warning(f"pypdf extraction error: {err}")
        return [], 0, "failed"


def normalize_subject(name: str | None) -> str:
    if not name:
        return "Other"
    clean = name.strip().casefold()
    for key, val in CORE_SUBJECT_MAP.items():
        if key in clean:
            return val
    return name.strip().title() or "Other"


class UPSCNotesService:
    def __init__(self, db_path=None, activity=None):
        self.sessions = get_session_factory(db_path)
        self.activity = activity or ActivityManager(db_path)
        self.classifier = SubjectTopicClassifier()

    def list_subjects(self):
        with self.sessions() as session:
            rows = session.query(
                UPSCNote.normalized_subject,
                func.count(UPSCNote.id).label("count")
            ).filter(
                UPSCNote.provider == "PWOnlyIAS",
                UPSCNote.active == True,
                UPSCNote.content_status == "ready",
                ~UPSCNote.title.ilike("%Test Note%"),
                ~UPSCNote.title.ilike("%Demo Note%"),
                ~UPSCNote.title.ilike("%Prog Test%"),
                ~UPSCNote.id.like("test-%"),
                ~UPSCNote.id.like("demo-%"),
                ~UPSCNote.id.like("sample-%"),
                ~UPSCNote.id.like("isolated-%"),
                ~UPSCNote.id.like("prog-%")
            ).group_by(UPSCNote.normalized_subject).all()
            return [{"subject": r[0], "note_count": r[1]} for r in rows if r[0]]

    def list_collections(self, subject=None, language=None, exam_stage=None, search=None):
        with self.sessions() as session:
            query = select(NoteCollection).filter(NoteCollection.active == True, NoteCollection.provider == "PWOnlyIAS")
            if language:
                query = query.filter(NoteCollection.language == language)
            if exam_stage:
                query = query.filter(NoteCollection.exam_stage == exam_stage)
            if search:
                pat = f"%{search}%"
                query = query.filter(or_(NoteCollection.title.ilike(pat), NoteCollection.description.ilike(pat)))
            return list(session.scalars(query.order_by(NoteCollection.created_at.desc())))

    def list_notes(self, *, user_id="user_001", subject=None, collection_id=None, topic=None,
                   language=None, prelims_only=False, mains_only=False, search=None, saved_only=False):
        with self.sessions() as session:
            saved_ids = set(session.scalars(select(SavedNote.note_id).where(SavedNote.user_id == user_id)))
            query = select(UPSCNote).filter(
                UPSCNote.active == True,
                UPSCNote.provider == "PWOnlyIAS",
                ~UPSCNote.title.ilike("%Test Note%"),
                ~UPSCNote.title.ilike("%Demo Note%"),
                ~UPSCNote.title.ilike("%Prog Test%"),
                ~UPSCNote.id.like("test-%"),
                ~UPSCNote.id.like("demo-%"),
                ~UPSCNote.id.like("sample-%"),
                ~UPSCNote.id.like("isolated-%"),
                ~UPSCNote.id.like("prog-%")
            )
            if subject:
                query = query.filter(UPSCNote.normalized_subject == subject)
            if collection_id:
                query = query.filter(UPSCNote.collection_id == collection_id)
            if topic:
                query = query.filter(UPSCNote.topic == topic)
            if language:
                query = query.filter(UPSCNote.language == language)
            if prelims_only:
                query = query.filter(UPSCNote.prelims_relevant == True)
            if mains_only:
                query = query.filter(UPSCNote.mains_relevant == True)
            if saved_only:
                query = query.filter(UPSCNote.id.in_(saved_ids))
            if search:
                pat = f"%{search}%"
                query = query.filter(or_(UPSCNote.title.ilike(pat), UPSCNote.description.ilike(pat), UPSCNote.topic.ilike(pat)))
            
            rows = list(session.scalars(query.order_by(UPSCNote.created_at.desc())))
            
            # Fetch reading progress
            progress_rows = {p.note_id: p for p in session.scalars(select(NoteReadingProgress).where(NoteReadingProgress.user_id == user_id))}

        result = []
        for r in rows:
            prog = progress_rows.get(r.id)
            result.append({
                "note": r,
                "saved": r.id in saved_ids,
                "progress_percentage": prog.progress_percentage if prog else 0.0,
                "last_opened_at": prog.last_opened_at.isoformat() if prog else None
            })
        return result

    def get_note(self, note_id: str, *, user_id="user_001"):
        with self.sessions() as session:
            note = session.get(UPSCNote, note_id)
            if not note or not note.active:
                return None
            saved = bool(session.scalar(select(SavedNote).where(SavedNote.user_id == user_id, SavedNote.note_id == note_id)))
            prog = session.scalar(select(NoteReadingProgress).where(NoteReadingProgress.user_id == user_id, NoteReadingProgress.note_id == note_id))
            return {
                "note": note,
                "saved": saved,
                "progress_percentage": prog.progress_percentage if prog else 0.0,
                "last_position": prog.last_position if prog else 0
            }

    def get_note_content(self, note_id: str, *, user_id="user_001"):
        info = self.get_note(note_id, user_id=user_id)
        if not info:
            return None
        note: UPSCNote = info["note"]

        blocks = note.content_blocks_json or []
        page_refs = sorted(list({
            str(b["page_ref"]) for b in blocks if isinstance(b, dict) and b.get("page_ref") is not None
        }))

        # Record activity
        self.activity.record_event(
            "upsc_note_opened",
            datetime.now(timezone.utc),
            user_id=user_id,
            subject=note.normalized_subject,
            topic=note.topic,
            metadata_json={"note_id": note.id}
        )

        mode = getattr(settings, "UPSC_NOTES_CONTENT_MODE", "private_local")
        if mode == "public_summary":
            blocks = [
                {"type": "heading", "level": 2, "text": "Study Note Summary & Key Concepts"},
                {"type": "paragraph", "text": note.description or note.title},
                {"type": "important_fact", "text": f"Grounded PWOnlyIAS study resource for {note.normalized_subject}."}
            ]

        avail = "available" if note.content_status == "ready" else "unavailable"
        if note.extraction_status == "image_only":
            avail = "unavailable"

        return {
            "id": note.id,
            "slug": note.slug,
            "title": note.title,
            "provider": "PWOnlyIAS",
            "subject": note.normalized_subject,
            "topic": note.topic,
            "description": note.description,
            "language": note.language,
            "prelims_relevant": note.prelims_relevant,
            "mains_relevant": note.mains_relevant,
            "estimated_reading_minutes": note.estimated_reading_minutes,
            "page_count": note.page_count,
            "content_blocks": blocks,
            "page_references": page_refs,
            "official_source_url": note.official_source_url,
            "official_pdf_url": note.official_pdf_url,
            "extraction_status": note.extraction_status,
            "content_status": note.content_status,
            "availability": avail,
            "saved": info["saved"],
            "progress_percentage": info["progress_percentage"]
        }

    def save_note(self, note_id: str, *, user_id="user_001"):
        with self.sessions() as session:
            note = session.get(UPSCNote, note_id)
            if not note:
                return False
            existing = session.scalar(select(SavedNote).where(SavedNote.user_id == user_id, SavedNote.note_id == note_id))
            if not existing:
                session.add(SavedNote(id=str(uuid.uuid4()), user_id=user_id, note_id=note_id))
                session.commit()
            return True

    def unsave_note(self, note_id: str, *, user_id="user_001"):
        with self.sessions() as session:
            existing = session.scalar(select(SavedNote).where(SavedNote.user_id == user_id, SavedNote.note_id == note_id))
            if not existing:
                return False
            session.delete(existing)
            session.commit()
            return True

    def update_progress(self, note_id: str, *, user_id="user_001", progress_percentage: float, last_position: int = 0):
        now = datetime.now(timezone.utc)
        completed_at = now if progress_percentage >= 95.0 else None
        with self.sessions() as session:
            prog = session.scalar(select(NoteReadingProgress).where(NoteReadingProgress.user_id == user_id, NoteReadingProgress.note_id == note_id))
            if prog:
                prog.progress_percentage = max(prog.progress_percentage, progress_percentage)
                prog.last_position = last_position
                prog.last_opened_at = now
                if completed_at and not prog.completed_at:
                    prog.completed_at = completed_at
            else:
                prog = NoteReadingProgress(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    note_id=note_id,
                    progress_percentage=progress_percentage,
                    last_position=last_position,
                    last_opened_at=now,
                    completed_at=completed_at
                )
                session.add(prog)
            session.commit()
            return {"note_id": note_id, "progress_percentage": prog.progress_percentage}

    @staticmethod
    def extract_html_blocks(text: str) -> list[dict]:
        blocks = []
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines:
            if line.startswith("# ") or line.startswith("## "):
                blocks.append({"type": "heading", "level": 2, "text": line.lstrip("# ").strip()})
            elif line.startswith("### "):
                blocks.append({"type": "heading", "level": 3, "text": line.lstrip("# ").strip()})
            elif line.startswith("- ") or line.startswith("* "):
                if blocks and blocks[-1].get("type") == "bullet_list":
                    blocks[-1]["items"].append(line[2:].strip())
                else:
                    blocks.append({"type": "bullet_list", "items": [line[2:].strip()]})
            elif re.match(r"^\d+\.\s", line):
                item_txt = re.sub(r"^\d+\.\s*", "", line)
                if blocks and blocks[-1].get("type") == "numbered_list":
                    blocks[-1]["items"].append(item_txt)
                else:
                    blocks.append({"type": "numbered_list", "items": [item_txt]})
            elif line.lower().startswith("note:") or line.lower().startswith("key fact:"):
                blocks.append({"type": "important_fact", "text": line})
            else:
                blocks.append({"type": "paragraph", "text": line})
        return blocks

    def _index(self, note: UPSCNote):
        try:
            blocks = note.content_blocks_json or []
            chunks = []
            for idx, block in enumerate(blocks):
                txt = block.get("text") or " ".join(block.get("items") or [])
                if not txt.strip():
                    continue
                chunks.append({
                    "text": f"{note.title}\nSubject: {note.normalized_subject}\nTopic: {note.topic}\n\n{txt}",
                    "title": note.title,
                    "publisher": "PWOnlyIAS",
                    "provider": "PWOnlyIAS",
                    "source_type": "upsc_note",
                    "note_id": note.id,
                    "collection_id": note.collection_id or "",
                    "subject": note.normalized_subject,
                    "topic": note.topic,
                    "language": note.language,
                    "prelims_relevant": str(note.prelims_relevant),
                    "mains_relevant": str(note.mains_relevant),
                    "source_page_url": note.official_source_url,
                    "official_pdf_url": note.official_pdf_url or "",
                    "page_start": block.get("page_start", 1),
                    "page_end": block.get("page_end", 1),
                    "checksum": note.content_checksum or ""
                })

            if not chunks:
                chunks = [{
                    "text": f"{note.title}\n{note.description}\nSubject: {note.normalized_subject}\nTopic: {note.topic}",
                    "title": note.title,
                    "publisher": "PWOnlyIAS",
                    "provider": "PWOnlyIAS",
                    "source_type": "upsc_note",
                    "note_id": note.id,
                    "subject": note.normalized_subject,
                    "topic": note.topic
                }]

            embeddings = EmbeddingService.generate_embeddings(chunks)
            VectorStore().store_current_affairs(note.id, chunks, embeddings)
        except Exception as err:
            log.warning(f"Chroma RAG indexing skipped for note {note.id}: {err}")
