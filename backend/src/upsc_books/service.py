from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select, func

from src.activity.manager import ActivityManager
from src.core.config import settings
from src.memory.storage import get_session_factory
from src.rag.embeddings import EmbeddingService
from src.rag.vector_store import VectorStore
from src.pwonlyias.shared import is_valid_pwonlyias_source_url, extract_pdf_blocks, normalize_subject
from src.upsc_books.models import BookCollection, UPSCBook, BookChapter, SavedBook, BookReadingProgress

log = logging.getLogger(__name__)

import hashlib
import urllib.request
from urllib.parse import urljoin

OFFICIAL_BOOK_HUBS = [
    "https://pwonlyias.com/downloads/",
    "https://pwonlyias.com/upsc-free-study-material/",
    "https://pwonlyias.com/upsc-exam-study-material/",
    "https://pwonlyias.com/onlyias-all-books/",
    "https://pwonlyias.com/books/",
    "https://pwonlyias.com/udaan/",
    "https://pwonlyias.com/udaan-2-booklets/",
    "https://pwonlyias.com/ncert-wallah-books/",
]


def detect_chapters_from_blocks(blocks: list[dict]) -> list[dict]:
    chapters = []
    order = 1
    for b in blocks:
        if not isinstance(b, dict):
            continue
        b_type = b.get("type")
        txt = (b.get("text") or b.get("title") or "").strip()
        match = re.match(r"^(?:chapter|ch\.?)\s*(\d+|[ivxlcdm]+)[\s:]*(.*)$", txt, re.IGNORECASE)
        if match and (b_type == "heading" or b.get("level")):
            ch_title = txt
            p_start = b.get("page_start", 1)
            p_end = b.get("page_end", p_start)
            chapters.append({
                "title": ch_title,
                "slug": f"ch-{order}",
                "chapter_order": order,
                "page_start": p_start,
                "page_end": p_end
            })
            order += 1
    return chapters


class UPSCBooksService:
    def __init__(self, db_path=None, activity=None):
        self.sessions = get_session_factory(db_path)
        self.activity = activity or ActivityManager(db_path)

    def import_from_official_source_page(self, source_page_url: str) -> dict:
        if not is_valid_pwonlyias_source_url(source_page_url):
            raise ValueError("Source URL must belong to official PWOnlyIAS domain")

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) UPSC-AI-Mentor/1.0"}
        req = urllib.request.Request(source_page_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status != 200:
                raise ValueError("Could not reach official source page")
            final_url = resp.geturl()
            if not is_valid_pwonlyias_source_url(final_url):
                raise ValueError("Source page redirected to non-PWOnlyIAS domain")
            html = resp.read().decode("utf-8", errors="ignore")

        # Search for PDF links or download anchors
        pdf_urls = re.findall(r'href=["\'](https?://[^"\']+\.pdf)["\']', html, re.IGNORECASE)
        if not pdf_urls:
            download_anchors = re.findall(r'href=["\'](https?://[^"\']+)["\'][^>]*>(?:[^<]*(?:download|pdf|book|booklet)[^<]*)</a>', html, re.IGNORECASE)
            pdf_urls = [u for u in download_anchors if u.lower().endswith(".pdf")]

        if not pdf_urls:
            raise ValueError("No verified public PDF link found on official PWOnlyIAS source page")

        pdf_url = pdf_urls[0]
        if not is_valid_pwonlyias_source_url(pdf_url):
            raise ValueError("Discovered PDF URL is not on official PWOnlyIAS domain")

        pdf_req = urllib.request.Request(pdf_url, headers=headers)
        with urllib.request.urlopen(pdf_req, timeout=12) as pdf_resp:
            if pdf_resp.status != 200:
                raise ValueError("Could not download discovered PDF")
            pdf_bytes = pdf_resp.read()

        blocks, p_count, status = extract_pdf_blocks(pdf_bytes)
        if status not in ("ready", "image_only"):
            raise ValueError("PDF content extraction failed or invalid signature")

        raw_title = pdf_url.split("/")[-1].replace(".pdf", "").replace("-", " ").title()
        subject = normalize_subject(raw_title)
        b_id = f"book-{hashlib.md5(pdf_url.encode()).hexdigest()[:12]}"
        chs = detect_chapters_from_blocks(blocks)

        with self.sessions() as session:
            obj = UPSCBook(
                id=b_id, provider="PWOnlyIAS", title=raw_title, slug=b_id,
                normalized_subject=subject, official_source_url=source_page_url,
                official_pdf_url=pdf_url, canonical_url=pdf_url,
                content_status="ready" if status == "ready" else "unavailable",
                extraction_status=status, page_count=p_count,
                content_blocks_json=blocks
            )
            session.merge(obj)
            for c in chs:
                session.merge(BookChapter(
                    id=f"ch-{b_id}-{c['chapter_order']}", book_id=b_id,
                    title=c["title"], slug=c["slug"], chapter_order=c["chapter_order"],
                    page_start=c["page_start"], page_end=c["page_end"]
                ))
            session.commit()
            self._index(obj)

        return {"id": b_id, "title": raw_title, "subject": subject, "page_count": p_count, "chapters": len(chs)}

    def discover_books(self, limit: int = 2, dry_run: bool = False) -> dict:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) UPSC-AI-Mentor/1.0"}
        discovered = []
        visited_detail_pages = set()

        for hub_url in OFFICIAL_BOOK_HUBS[:3]:
            if len(discovered) >= limit:
                break
            if not is_valid_pwonlyias_source_url(hub_url):
                continue
            try:
                req = urllib.request.Request(hub_url, headers=headers)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status != 200:
                        continue
                    html = resp.read().decode("utf-8", errors="ignore")

                # Find candidate detail pages on pwonlyias.com
                detail_links = re.findall(r'href=["\'](https?://(?:[a-zA-Z0-9-]+\.)*pwonlyias\.com/[^"\']+)["\']', html, re.IGNORECASE)
                for detail_url in detail_links:
                    if len(discovered) >= limit or len(visited_detail_pages) >= 10:
                        break
                    if detail_url in visited_detail_pages or detail_url.endswith((".css", ".js", ".png", ".jpg", ".jpeg")):
                        continue
                    visited_detail_pages.add(detail_url)

                    try:
                        d_req = urllib.request.Request(detail_url, headers=headers)
                        with urllib.request.urlopen(d_req, timeout=5) as d_resp:
                            if d_resp.status != 200:
                                continue
                            d_html = d_resp.read().decode("utf-8", errors="ignore")

                        pdf_urls = re.findall(r'href=["\'](https?://[^"\']+\.pdf)["\']', d_html, re.IGNORECASE)
                        for pdf_url in pdf_urls:
                            if len(discovered) >= limit:
                                break
                            if not is_valid_pwonlyias_source_url(pdf_url):
                                continue
                            try:
                                pdf_req = urllib.request.Request(pdf_url, headers=headers)
                                with urllib.request.urlopen(pdf_req, timeout=8) as pdf_resp:
                                    if pdf_resp.status != 200:
                                        continue
                                    pdf_final_url = pdf_resp.geturl()
                                    pdf_bytes = pdf_resp.read()

                                    blocks, p_count, status = extract_pdf_blocks(pdf_bytes)
                                    if status not in ("ready", "image_only"):
                                        continue

                                    title = pdf_url.split("/")[-1].replace(".pdf", "").replace("-", " ").title()
                                    b_id = f"book-{hashlib.md5(pdf_url.encode()).hexdigest()[:12]}"
                                    chs = detect_chapters_from_blocks(blocks)
                                    subj = normalize_subject(title)

                                    book_record = {
                                        "id": b_id,
                                        "title": title,
                                        "slug": b_id,
                                        "normalized_subject": subj,
                                        "official_source_url": detail_url,
                                        "official_pdf_url": pdf_final_url,
                                        "content_status": "ready" if status == "ready" else "unavailable",
                                        "extraction_status": status,
                                        "page_count": p_count,
                                        "chapters_detected": len(chs)
                                    }

                                    if not dry_run:
                                        with self.sessions() as session:
                                            obj = UPSCBook(
                                                id=b_id, provider="PWOnlyIAS", title=title, slug=b_id,
                                                normalized_subject=subj, official_source_url=detail_url,
                                                official_pdf_url=pdf_final_url, canonical_url=pdf_final_url,
                                                content_status="ready" if status == "ready" else "unavailable",
                                                extraction_status=status, page_count=p_count,
                                                content_blocks_json=blocks
                                            )
                                            session.merge(obj)
                                            for c in chs:
                                                session.merge(BookChapter(
                                                    id=f"ch-{b_id}-{c['chapter_order']}", book_id=b_id,
                                                    title=c["title"], slug=c["slug"], chapter_order=c["chapter_order"],
                                                    page_start=c["page_start"], page_end=c["page_end"]
                                                ))
                                            session.commit()
                                            self._index(obj)
                                    discovered.append(book_record)
                            except Exception as e:
                                log.warning(f"PDF download failed for {pdf_url}: {e}")
                    except Exception as e:
                        log.warning(f"Detail page check failed for {detail_url}: {e}")
            except Exception as e:
                log.warning(f"Hub check failed for {hub_url}: {e}")

        return {"discovered_count": len(discovered), "items": discovered}

    def list_subjects(self, section: str | None = None):
        with self.sessions() as session:
            query = session.query(
                UPSCBook.normalized_subject,
                func.count(UPSCBook.id).label("count")
            ).filter(
                UPSCBook.active == True,
                ~UPSCBook.title.ilike("%Isolated Test Book%"),
                ~UPSCBook.title.ilike("%Prog Book%"),
                ~UPSCBook.id.like("test-%"),
                ~UPSCBook.id.like("demo-%"),
                ~UPSCBook.id.like("sample-%"),
                ~UPSCBook.id.like("isolated-%"),
                ~UPSCBook.id.like("prog-%")
            )
            if section == "prelims":
                query = query.filter(UPSCBook.prelims_relevant == True, UPSCBook.resource_kind == "study_book")
            elif section == "mains":
                query = query.filter(UPSCBook.mains_relevant == True, UPSCBook.resource_kind == "study_book")
            elif section == "qa_bank":
                query = query.filter(UPSCBook.resource_kind == "qa_bank")

            rows = query.group_by(UPSCBook.normalized_subject).all()
            return [{"subject": r[0], "book_count": r[1]} for r in rows if r[0]]

    def list_collections(self, subject=None, language=None, exam_stage=None, search=None):
        with self.sessions() as session:
            query = select(BookCollection).filter(BookCollection.active == True)
            if language:
                query = query.filter(BookCollection.language == language)
            if exam_stage:
                query = query.filter(BookCollection.exam_stage == exam_stage)
            if search:
                pat = f"%{search}%"
                query = query.filter(or_(BookCollection.title.ilike(pat), BookCollection.description.ilike(pat)))
            return list(session.scalars(query.order_by(BookCollection.created_at.desc())))

    def list_books(self, *, user_id="user_001", subject=None, collection_id=None,
                   language=None, prelims_only=False, mains_only=False, search=None, saved_only=False,
                   section=None):
        with self.sessions() as session:
            saved_ids = set(session.scalars(select(SavedBook.book_id).where(SavedBook.user_id == user_id)))
            query = select(UPSCBook).filter(
                UPSCBook.active == True,
                ~UPSCBook.title.ilike("%Isolated Test Book%"),
                ~UPSCBook.title.ilike("%Prog Book%"),
                ~UPSCBook.id.like("test-%"),
                ~UPSCBook.id.like("demo-%"),
                ~UPSCBook.id.like("sample-%"),
                ~UPSCBook.id.like("isolated-%"),
                ~UPSCBook.id.like("prog-%")
            )
            if subject:
                query = query.filter(UPSCBook.normalized_subject == subject)
            if collection_id:
                query = query.filter(UPSCBook.collection_id == collection_id)
            if language:
                query = query.filter(UPSCBook.language == language)
            
            if section == "prelims":
                query = query.filter(UPSCBook.prelims_relevant == True, UPSCBook.resource_kind == "study_book")
            elif section == "mains":
                query = query.filter(UPSCBook.mains_relevant == True, UPSCBook.resource_kind == "study_book")
            elif section == "qa_bank":
                query = query.filter(UPSCBook.resource_kind == "qa_bank")
            else:
                if prelims_only:
                    query = query.filter(UPSCBook.prelims_relevant == True)
                if mains_only:
                    query = query.filter(UPSCBook.mains_relevant == True)

            if saved_only:
                query = query.filter(UPSCBook.id.in_(saved_ids))
            if search:
                pat = f"%{search}%"
                query = query.filter(or_(UPSCBook.title.ilike(pat), UPSCBook.description.ilike(pat)))

            rows = list(session.scalars(query.order_by(UPSCBook.created_at.desc())))
            progress_rows = {p.book_id: p for p in session.scalars(select(BookReadingProgress).where(BookReadingProgress.user_id == user_id))}

        result = []
        for r in rows:
            prog = progress_rows.get(r.id)
            result.append({
                "book": r,
                "saved": r.id in saved_ids,
                "progress_percentage": prog.progress_percentage if prog else 0.0,
                "last_opened_at": prog.last_opened_at.isoformat() if prog else None
            })
        return result

    def get_book(self, book_id: str, *, user_id="user_001"):
        with self.sessions() as session:
            book = session.get(UPSCBook, book_id)
            if not book or not book.active:
                return None
            saved = bool(session.scalar(select(SavedBook).where(SavedBook.user_id == user_id, SavedBook.book_id == book_id)))
            prog = session.scalar(select(BookReadingProgress).where(BookReadingProgress.user_id == user_id, BookReadingProgress.book_id == book_id))
            chapters = list(session.scalars(select(BookChapter).where(BookChapter.book_id == book_id).order_by(BookChapter.chapter_order.asc())))
            return {
                "book": book,
                "saved": saved,
                "progress_percentage": prog.progress_percentage if prog else 0.0,
                "last_position": prog.last_position if prog else 0,
                "chapters": chapters
            }

    def get_book_content(self, book_id: str, *, user_id="user_001", chapter_id: str | None = None):
        info = self.get_book(book_id, user_id=user_id)
        if not info:
            return None
        book: UPSCBook = info["book"]

        blocks = book.content_blocks_json or []
        chapters = info["chapters"]

        if chapter_id and chapters:
            target_ch = next((c for c in chapters if c.id == chapter_id), None)
            if target_ch:
                blocks = [b for b in blocks if isinstance(b, dict) and b.get("page_ref") and target_ch.page_start <= b.get("page_ref") <= target_ch.page_end]

        page_refs = sorted(list({
            str(b["page_ref"]) for b in blocks if isinstance(b, dict) and b.get("page_ref") is not None
        }))

        self.activity.record_event(
            "upsc_book_opened",
            datetime.now(timezone.utc),
            user_id=user_id,
            subject=book.normalized_subject,
            topic=book.title,
            metadata_json={"book_id": book.id, "chapter_id": chapter_id}
        )

        mode = getattr(settings, "UPSC_BOOKS_CONTENT_MODE", "private_local")
        if mode == "public_summary":
            blocks = [
                {"type": "heading", "level": 2, "text": "Book Study Summary & Key Concepts"},
                {"type": "paragraph", "text": book.description or book.title},
                {"type": "important_fact", "text": f"Grounded {book.provider} study book for {book.normalized_subject}."}
            ]

        avail = "available" if book.content_status == "ready" else "unavailable"
        if book.extraction_status == "image_only":
            avail = "unavailable"

        return {
            "id": book.id,
            "slug": book.slug,
            "title": book.title,
            "provider": book.provider,
            "subject": book.normalized_subject,
            "description": book.description,
            "language": book.language,
            "prelims_relevant": book.prelims_relevant,
            "mains_relevant": book.mains_relevant,
            "resource_kind": getattr(book, "resource_kind", "study_book"),
            "estimated_reading_minutes": book.estimated_reading_minutes,
            "page_count": book.page_count,
            "chapters": [{"id": c.id, "title": c.title, "chapter_order": c.chapter_order, "page_start": c.page_start, "page_end": c.page_end} for c in chapters],
            "content_blocks": blocks,
            "page_references": page_refs,
            "official_source_url": book.official_source_url,
            "official_pdf_url": book.official_pdf_url,
            "extraction_status": book.extraction_status,
            "content_status": book.content_status,
            "indexing_status": book.indexing_status,
            "availability": avail,
            "saved": info["saved"],
            "progress_percentage": info["progress_percentage"]
        }

    def save_book(self, book_id: str, *, user_id="user_001"):
        with self.sessions() as session:
            book = session.get(UPSCBook, book_id)
            if not book:
                return False
            existing = session.scalar(select(SavedBook).where(SavedBook.user_id == user_id, SavedBook.book_id == book_id))
            if not existing:
                session.add(SavedBook(id=str(uuid.uuid4()), user_id=user_id, book_id=book_id))
                session.commit()
            return True

    def unsave_book(self, book_id: str, *, user_id="user_001"):
        with self.sessions() as session:
            existing = session.scalar(select(SavedBook).where(SavedBook.user_id == user_id, SavedBook.book_id == book_id))
            if not existing:
                return False
            session.delete(existing)
            session.commit()
            return True

    def update_progress(self, book_id: str, *, user_id="user_001", chapter_id: str | None = None, progress_percentage: float, last_position: int = 0):
        now = datetime.now(timezone.utc)
        completed_at = now if progress_percentage >= 95.0 else None
        with self.sessions() as session:
            prog = session.scalar(select(BookReadingProgress).where(BookReadingProgress.user_id == user_id, BookReadingProgress.book_id == book_id))
            if prog:
                prog.progress_percentage = max(prog.progress_percentage, progress_percentage)
                if chapter_id:
                    prog.chapter_id = chapter_id
                prog.last_position = last_position
                prog.last_opened_at = now
                if completed_at and not prog.completed_at:
                    prog.completed_at = completed_at
            else:
                prog = BookReadingProgress(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    book_id=book_id,
                    chapter_id=chapter_id,
                    progress_percentage=progress_percentage,
                    last_position=last_position,
                    last_opened_at=now,
                    completed_at=completed_at
                )
                session.add(prog)
            session.commit()
            return {"book_id": book_id, "progress_percentage": prog.progress_percentage}

    def _index(self, book: UPSCBook):
        try:
            blocks = book.content_blocks_json or []
            chunks = []
            for idx, block in enumerate(blocks):
                txt = block.get("text") or " ".join(block.get("items") or [])
                if not txt.strip():
                    continue
                chunks.append({
                    "text": f"{book.title}\nSubject: {book.normalized_subject}\n\n{txt}",
                    "title": book.title,
                    "publisher": book.provider,
                    "provider": book.provider,
                    "source_type": "upsc_book",
                    "book_id": book.id,
                    "collection_id": book.collection_id or "",
                    "subject": book.normalized_subject,
                    "language": book.language,
                    "prelims_relevant": str(book.prelims_relevant),
                    "mains_relevant": str(book.mains_relevant),
                    "source_page_url": book.official_source_url,
                    "official_pdf_url": book.official_pdf_url or "",
                    "page_start": block.get("page_start", 1),
                    "page_end": block.get("page_end", 1),
                    "checksum": book.content_checksum or ""
                })

            if not chunks:
                chunks = [{
                    "text": f"{book.title}\n{book.description}\nSubject: {book.normalized_subject}",
                    "title": book.title,
                    "publisher": book.provider,
                    "provider": book.provider,
                    "source_type": "upsc_book",
                    "book_id": book.id,
                    "subject": book.normalized_subject
                }]

            # Clear old vector chunks belonging to this book
            try:
                VectorStore().collection.delete(where={"document_id": book.id})
            except Exception as e:
                log.warning(f"Failed to clear old vector chunks for book {book.id}: {e}")

            embeddings = EmbeddingService.generate_embeddings(chunks)
            VectorStore().store_current_affairs(book.id, chunks, embeddings)
        except Exception as err:
            log.warning(f"Chroma RAG indexing skipped for book {book.id}: {err}")
            raise err
