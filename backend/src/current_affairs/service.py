from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import or_, select

from src.activity.manager import ActivityManager
from src.activity.taxonomy import SubjectTopicClassifier
from src.ai.factory import get_llm
from src.current_affairs.models import CurrentAffairsArticle, DailyCurrentAffairsBrief, SavedCurrentAffairs
from src.memory.storage import get_session_factory
from src.rag.embeddings import EmbeddingService
from src.rag.vector_store import VectorStore
from src.search.web_search import TrustedSourcePolicy, WebSearch


class ArticleSummary(BaseModel):
    what_happened: str = Field(min_length=20, max_length=900)
    background: str = Field(min_length=10, max_length=900)
    why_it_matters: str = Field(min_length=10, max_length=700)
    prelims_facts: list[str] = Field(min_length=1, max_length=6)
    mains_relevance: str = Field(min_length=10, max_length=700)
    syllabus_tags: list[str] = Field(min_length=1, max_length=6)
    importance_level: str = Field(pattern="^(low|medium|high)$")


class CurrentAffairsService:
    def __init__(self, db_path=None, web_search=None, llm=None, activity=None, indexer=None):
        self.sessions = get_session_factory(db_path); self.web = web_search or WebSearch(); self.llm = llm or get_llm()
        self.activity = activity or ActivityManager(db_path); self.classifier = SubjectTopicClassifier(); self.indexer = indexer

    @staticmethod
    def _parse_date(value):
        if not value: return None
        try: return date.fromisoformat(str(value)[:10])
        except ValueError: return None

    async def collect(self, queries: list[str]):
        results = []
        for query in queries:
            found = await asyncio.to_thread(self.web.search, query)
            for chunk in found.get("chunks", []):
                results.append(await self.ingest_chunk(chunk))
        return results

    async def collect_for_date(self, collection_date: date, *, max_results=10, generate_brief=False, language="english"):
        queries = [
            f"site:pib.gov.in {collection_date.isoformat()} important government developments",
            f"site:rbi.org.in OR site:sebi.gov.in {collection_date.isoformat()} economy policy developments",
            f"site:gov.in OR site:parliamentofindia.nic.in {collection_date.isoformat()} UPSC developments",
            f"site:un.org {collection_date.isoformat()} India international developments",
        ]
        collected = accepted = rejected = duplicates = 0; article_ids = []; errors = []
        for query in queries:
            if collected >= max_results: break
            try: found = await asyncio.to_thread(self.web.search, query)
            except Exception as error:
                errors.append(f"Trusted search failed: {type(error).__name__}"); continue
            if found.get("error"): errors.append(str(found["error"]))
            for chunk in found.get("chunks", []):
                if collected >= max_results: break
                collected += 1
                if not chunk.get("publication_date"): chunk = {**chunk, "publication_date": collection_date.isoformat()}
                with self.sessions() as session:
                    existing = session.scalar(select(CurrentAffairsArticle).where(or_(
                        CurrentAffairsArticle.source_url == chunk.get("source_url", ""),
                        CurrentAffairsArticle.content_hash == (chunk.get("content_hash") or ""))))
                if existing:
                    duplicates += 1; article_ids.append(existing.id); continue
                row = await self.ingest_chunk(chunk); article_ids.append(row.id)
                if row.status == "active": accepted += 1
                else: rejected += 1
        brief_status, brief_error = "not_requested", None
        if generate_brief:
            try: self.generate_daily(collection_date, language); brief_status = "generated"
            except Exception as error: brief_status, brief_error = "failed", str(error)
        return {"date": collection_date, "collected": collected, "accepted": accepted, "rejected": rejected,
            "duplicates": duplicates, "article_ids": list(dict.fromkeys(article_ids)), "collection_errors": errors,
            "daily_brief": brief_status, "brief_error": brief_error}

    async def ingest_chunk(self, chunk: dict):
        url = chunk.get("source_url", ""); policy = TrustedSourcePolicy.classify(url)
        content_hash = chunk.get("content_hash") or hashlib.sha256(chunk.get("text", "").encode()).hexdigest()
        with self.sessions() as session:
            existing = session.scalar(select(CurrentAffairsArticle).where(or_(
                CurrentAffairsArticle.source_url == url, CurrentAffairsArticle.content_hash == content_hash)))
            if existing: return existing
        classification = self.classifier.classify(chunk.get("text", ""))
        status = "active" if policy and len(chunk.get("text", "").strip()) >= 100 else "rejected"
        summary = None
        if status == "active":
            prompt = f"""Using ONLY the trusted source text below, create JSON with keys what_happened, background, why_it_matters, prelims_facts, mains_relevance, syllabus_tags, importance_level. Do not add unsupported facts. Importance must be low, medium, or high.\nSOURCE: {chunk.get('publisher')} | {url}\nTEXT:\n{chunk['text']}"""
            try:
                raw = await self.llm.generate(prompt=prompt, mode="learn", depth="quick")
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
                summary = ArticleSummary.model_validate(json.loads(raw))
            except (json.JSONDecodeError, ValidationError, RuntimeError): status = "rejected"
        if summary:
            summary_text = (f"What happened: {summary.what_happened}\nBackground: {summary.background}\n"
                f"Why it matters: {summary.why_it_matters}\nSource citation: {chunk.get('publisher')} — {url}")
            prelims = "\n".join(summary.prelims_facts); mains = summary.mains_relevance
            tags, importance = summary.syllabus_tags, summary.importance_level
        else:
            summary_text, prelims, mains, tags, importance = "Rejected: insufficient trusted grounded extraction.", "", "", [], "low"
        row = CurrentAffairsArticle(id=str(uuid.uuid4()), title=chunk.get("source_title") or "Unavailable source",
            summary=summary_text, source_title=chunk.get("source_title") or "Unavailable source",
            publisher=chunk.get("publisher") or (policy[0] if policy else "Unapproved publisher"), source_url=url or f"rejected:{uuid.uuid4()}",
            source_type="current_affairs", publication_date=self._parse_date(chunk.get("publication_date")),
            retrieved_at=datetime.fromisoformat(chunk["retrieved_at"]) if chunk.get("retrieved_at") else datetime.now(timezone.utc),
            subject=str(classification["subject"]), topic=str(classification["topic"]), syllabus_tags_json=tags,
            importance_level=importance, relevance_prelims=prelims, relevance_mains=mains,
            content_hash=content_hash, status=status)
        with self.sessions() as session: session.add(row); session.commit(); session.refresh(row)
        if row.status == "active": await asyncio.to_thread(self._index, row)
        return row

    def _index(self, row):
        chunk = {"text": f"{row.title}\n{row.summary}\nPrelims: {row.relevance_prelims}\nMains: {row.relevance_mains}",
            "title": row.title, "publisher": row.publisher, "source_url": row.source_url,
            "publication_date": row.publication_date.isoformat() if row.publication_date else "",
            "subject": row.subject, "topic": row.topic, "retrieved_at": row.retrieved_at.isoformat(), "content_hash": row.content_hash}
        if self.indexer: self.indexer(row.id, [chunk]); return
        embeddings = EmbeddingService.generate_embeddings([chunk]); VectorStore().store_current_affairs(row.id, [chunk], embeddings)

    def list_articles(self, *, user_id="user_001", date_value=None, date_from=None, date_to=None, subject=None,
                      topic=None, importance=None, publisher=None, saved_only=False, search=None, include_rejected=False):
        with self.sessions() as session:
            saved_ids = set(session.scalars(select(SavedCurrentAffairs.article_id).where(SavedCurrentAffairs.user_id == user_id)))
            query = select(CurrentAffairsArticle)
            if not include_rejected: query = query.where(CurrentAffairsArticle.status == "active")
            if date_value: query = query.where(CurrentAffairsArticle.publication_date == date_value)
            if date_from: query = query.where(CurrentAffairsArticle.publication_date >= date_from)
            if date_to: query = query.where(CurrentAffairsArticle.publication_date <= date_to)
            if subject: query = query.where(CurrentAffairsArticle.subject == subject)
            if topic: query = query.where(CurrentAffairsArticle.topic == topic)
            if importance: query = query.where(CurrentAffairsArticle.importance_level == importance)
            if publisher: query = query.where(CurrentAffairsArticle.publisher == publisher)
            if saved_only: query = query.where(CurrentAffairsArticle.id.in_(saved_ids))
            if search:
                pattern = f"%{search}%"; query = query.where(or_(CurrentAffairsArticle.title.ilike(pattern), CurrentAffairsArticle.summary.ilike(pattern)))
            rows = list(session.scalars(query.order_by(CurrentAffairsArticle.publication_date.desc(), CurrentAffairsArticle.retrieved_at.desc())))
        opened = {e.metadata_json.get("article_id") for e in self.activity.list_events(user_id=user_id, event_type="current_affairs_opened") if e.metadata_json}
        return [(row, row.id in saved_ids, row.id in opened) for row in rows]

    def get_article(self, article_id, *, user_id="user_001", record_open=True):
        with self.sessions() as session: row = session.get(CurrentAffairsArticle, article_id)
        if not row or row.status != "active": return None
        if record_open: self.activity.record_event("current_affairs_opened", datetime.now(timezone.utc), user_id=user_id,
            subject=row.subject, topic=row.topic, metadata_json={"article_id": row.id})
        return row

    def save(self, article_id, *, user_id="user_001"):
        row = self.get_article(article_id, user_id=user_id, record_open=False)
        if not row: return False
        with self.sessions() as session:
            existing = session.scalar(select(SavedCurrentAffairs).where(SavedCurrentAffairs.user_id == user_id, SavedCurrentAffairs.article_id == article_id))
            if not existing: session.add(SavedCurrentAffairs(id=str(uuid.uuid4()), user_id=user_id, article_id=article_id)); session.commit()
        self.activity.record_event("current_affairs_saved", datetime.now(timezone.utc), user_id=user_id,
            subject=row.subject, topic=row.topic, metadata_json={"article_id": row.id})
        return True

    def unsave(self, article_id, *, user_id="user_001"):
        with self.sessions() as session:
            row = session.scalar(select(SavedCurrentAffairs).where(SavedCurrentAffairs.user_id == user_id, SavedCurrentAffairs.article_id == article_id))
            if not row: return False
            session.delete(row); session.commit(); return True

    def generate_daily(self, brief_date: date, language="english"):
        articles = [item[0] for item in self.list_articles(date_value=brief_date)]
        if not articles: raise ValueError("No accepted current-affairs articles exist for this date")
        subjects = defaultdict(list)
        for article in articles: subjects[article.subject].append(article.id)
        ranked = sorted(articles, key=lambda item: ({"high": 3, "medium": 2, "low": 1}[item.importance_level], item.retrieved_at), reverse=True)
        values = {"title": f"Daily Current Affairs — {brief_date.isoformat()}",
            "overview": f"{len(articles)} trusted stories across {len(subjects)} UPSC subject area(s).",
            "article_ids_json": [item.id for item in ranked], "subject_breakdown_json": dict(subjects),
            "prelims_points_json": [point for item in ranked for point in item.relevance_prelims.splitlines() if point][:12],
            "mains_points_json": [item.relevance_mains for item in ranked if item.relevance_mains][:8]}
        with self.sessions() as session:
            row = session.scalar(select(DailyCurrentAffairsBrief).where(DailyCurrentAffairsBrief.brief_date == brief_date, DailyCurrentAffairsBrief.language == language))
            if row:
                for key, value in values.items(): setattr(row, key, value)
            else: row = DailyCurrentAffairsBrief(id=str(uuid.uuid4()), brief_date=brief_date, language=language, **values); session.add(row)
            session.commit(); session.refresh(row); return row

    def get_daily(self, brief_date: date, language="english", *, user_id="user_001", record_completed=True):
        with self.sessions() as session:
            row = session.scalar(select(DailyCurrentAffairsBrief).where(DailyCurrentAffairsBrief.brief_date == brief_date, DailyCurrentAffairsBrief.language == language))
        if row and record_completed: self.activity.record_event("daily_brief_completed", datetime.now(timezone.utc), user_id=user_id,
            metadata_json={"brief_id": row.id, "brief_date": brief_date.isoformat()})
        return row

    def dashboard_summary(self, *, user_id="user_001"):
        today = date.today(); items = self.list_articles(date_value=today, user_id=user_id)
        subjects = Counter(row.subject for row, _, _ in items)
        completed = any((event.metadata_json or {}).get("brief_date") == today.isoformat()
            for event in self.activity.list_events(user_id=user_id, event_type="daily_brief_completed"))
        return {"unread_important_stories": sum(row.importance_level == "high" and not opened for row, _, opened in items),
            "top_subject": subjects.most_common(1)[0][0] if subjects else None,
            "saved_articles": len(self.list_articles(user_id=user_id, saved_only=True)), "daily_brief_completed": completed}
