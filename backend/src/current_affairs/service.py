from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
import logging
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
from src.search.web_search import APPROVED_DOMAINS, TrustedSourcePolicy, WebSearch
from src.core.config import settings

log = logging.getLogger(__name__)


class ArticleSummary(BaseModel):
    what_happened: str = Field(min_length=20, max_length=900)
    background: str = Field(default="", max_length=900)
    why_it_matters: str = Field(default="", max_length=700)
    prelims_facts: list[str] = Field(default_factory=list, max_length=6)
    mains_relevance: list[str] = Field(default_factory=list, max_length=6)
    subject: str = "General Studies"
    topic: str = "Current Affairs"
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

    @staticmethod
    def default_queries(collection_date: date):
        stamp = collection_date.strftime("%d %B %Y")
        return [
            f"site:pib.gov.in India government schemes {stamp}",
            f"site:rbi.org.in RBI India economy {stamp}",
            f"site:parliamentofindia.nic.in Parliament India governance {stamp}",
            f"site:gov.in India environment science technology {stamp}",
            f"site:un.org India international institutions {stamp}",
        ]

    async def collect_for_date(self, collection_date: date, *, max_results=10, generate_brief=False, language="english", queries=None, urls=None):
        queries = list(queries) if queries else ([] if urls else self.default_queries(collection_date))
        urls = list(urls or [])
        if hasattr(self.web, "validate_configuration"):
            self.web.validate_configuration(direct_urls=bool(urls and not queries))
        provider_name = getattr(self.web, "provider_name", type(self.web).__name__)
        log.info("Current Affairs collection start date=%s enabled=%s provider=%s allowlist=%d max_results=%d queries=%r direct_urls=%d",
            collection_date.isoformat(), settings.ENABLE_WEB_SEARCH, provider_name,
            len(APPROVED_DOMAINS), max_results, queries, len(urls))
        collected = accepted = rejected = duplicates = 0; article_ids = []; errors = []; source_progress = []
        diagnostics = {"raw_results": 0, "approved_results": 0, "rejected_domains": 0,
            "rejected_redirects": 0, "extraction_attempts": 0, "extraction_successes": 0}
        zero_reasons = []
        work = [("query", query) for query in queries] + [("url", url) for url in urls]
        for kind, value in work:
            if collected >= max_results: break
            try:
                if kind == "url": found = await asyncio.to_thread(self.web.fetch_url, value, f"current affairs {collection_date.isoformat()}")
                else: found = await asyncio.to_thread(self.web.search, value)
            except Exception as error:
                errors.append(f"Trusted {kind} failed: {type(error).__name__}"); continue
            if found.get("error"): errors.append(str(found["error"]))
            source_progress.extend(found.get("source_progress", []))
            for key in diagnostics: diagnostics[key] += int(found.get(key, 0))
            diagnostics["approved_results"] += len(found.get("chunks", []))
            if found.get("zero_result_reason"): zero_reasons.append(found["zero_result_reason"])
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
                quality = chunk.get("article_quality") or WebSearch.article_quality(chunk)
                final_progress = {"url": chunk.get("source_url"), "page_type": quality["page_type"],
                    "quality_score": quality["quality_score"], "status": "accepted" if row.status == "active" else "rejected",
                    "reason": row.summary if row.status != "active" else "grounded article accepted",
                    "summarization": "accepted" if row.status == "active" else "rejected"}
                pending = next((item for item in source_progress if item.get("url") == chunk.get("source_url") and item.get("status") == "candidate"), None)
                if pending: pending.update(final_progress)
                else: source_progress.append(final_progress)
                if row.status == "active": accepted += 1
                else: rejected += 1
        brief_status, brief_error = "not_requested", None
        if generate_brief:
            try: self.generate_daily(collection_date, language); brief_status = "generated"
            except Exception as error: brief_status, brief_error = "failed", str(error)
        log.info("Current Affairs collection complete raw=%d approved=%d rejected_domains=%d extraction_attempts=%d extraction_successes=%d final_candidates=%d",
            diagnostics["raw_results"], diagnostics["approved_results"], diagnostics["rejected_domains"],
            diagnostics["extraction_attempts"], diagnostics["extraction_successes"], collected)
        return {"date": collection_date, "search_provider": provider_name if queries else "direct_url",
            "queries_executed": queries, **diagnostics, "zero_result_reason": "; ".join(dict.fromkeys(zero_reasons)) or None,
            "source_progress": source_progress,
            "extraction_failures": diagnostics["extraction_attempts"] - diagnostics["extraction_successes"],
            "collected": collected, "accepted": accepted, "rejected": rejected,
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
        quality = chunk.get("article_quality") or WebSearch.article_quality(chunk)
        status = "active" if policy and quality["is_article"] else "rejected"
        summary = None
        if status == "active":
            prompt = f"""Use ONLY the article body and metadata below. Return one strict JSON object with keys what_happened, background, why_it_matters, prelims_facts, mains_relevance, subject, topic, importance_level. prelims_facts and mains_relevance must be arrays of plain strings and may be empty. background and why_it_matters must be strings and may be empty. what_happened must state the grounded core event. Copy dates and quantities exactly when used; never calculate, extrapolate, or invent an end date or consequence. Omit an optional point instead of inferring it. importance_level must be low, medium, or high.\nTITLE: {chunk.get('source_title')}\nPUBLISHER: {chunk.get('publisher')}\nURL: {url}\nPUBLICATION DATE: {chunk.get('publication_date') or 'unavailable'}\nARTICLE BODY:\n{chunk['text']}"""
            try:
                raw = await self.llm.generate(prompt=prompt, mode="learn", depth="quick")
                summary = self._parse_summary(raw)
                if not self._summary_is_grounded(summary, chunk["text"]):
                    status = "rejected"; summary = None
            except (json.JSONDecodeError, ValidationError, RuntimeError): status = "rejected"
        if summary:
            summary_text = (f"What happened: {summary.what_happened}\nBackground: {summary.background}\n"
                f"Why it matters: {summary.why_it_matters}\nSource citation: {chunk.get('publisher')} — {url}")
            prelims = "\n".join(summary.prelims_facts); mains = "\n".join(summary.mains_relevance)
            classification = {"subject": summary.subject or classification["subject"], "topic": summary.topic or classification["topic"]}
            tags, importance = [summary.subject, summary.topic], summary.importance_level
        else:
            reason = "; ".join(quality["reasons"]) if not quality["is_article"] else "summary missing core grounded factual content"
            summary_text, prelims, mains, tags, importance = f"Rejected: {reason}.", "", "", [], "low"
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

    @staticmethod
    def _parse_summary(raw):
        cleaned = re.sub(r"```(?:json)?|```", "", raw.strip(), flags=re.I)
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end < start: raise json.JSONDecodeError("JSON object not found", cleaned, 0)
        candidate = cleaned[start:end + 1]
        try: data = json.loads(candidate)
        except json.JSONDecodeError:
            repaired = re.sub(r",\s*([}\]])", r"\1", candidate.replace("“", '"').replace("”", '"'))
            data = json.loads(repaired)
        for key in ("background", "why_it_matters"):
            if isinstance(data.get(key), list): data[key] = " ".join(str(value) for value in data[key] if value)
        for key in ("prelims_facts", "mains_relevance"):
            value = data.get(key, [])
            if isinstance(value, str): value = [value] if value else []
            if isinstance(value, list):
                value = [str(next(iter(item.values()))) if isinstance(item, dict) and item else str(item) for item in value]
            data[key] = value
        return ArticleSummary.model_validate(data)

    @staticmethod
    def _summary_is_grounded(summary, source_text):
        source = source_text.casefold()
        claims = " ".join([summary.what_happened, summary.background, summary.why_it_matters,
            *summary.prelims_facts, *summary.mains_relevance])
        if any(number not in source for number in re.findall(r"\b\d+(?:\.\d+)?%?\b", claims)): return False
        words = {word for word in re.findall(r"[a-z]{5,}", summary.what_happened.casefold())
            if word not in {"which", "their", "about", "would", "could", "announced", "stated"}}
        return len(summary.what_happened.strip()) >= 20 and (not words or sum(word in source for word in words) / len(words) >= .30)

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
        from src.current_affairs.quiz_service import CurrentAffairsQuizService
        quiz = CurrentAffairsQuizService(); attempts = quiz.attempts(None, user_id); retention = quiz.retention(user_id)
        latest = attempts[0] if attempts else None; next_revision = min((r.next_revision_at for r in retention if r.next_revision_at), default=None)
        return {"unread_important_stories": sum(row.importance_level == "high" and not opened for row, _, opened in items),
            "top_subject": subjects.most_common(1)[0][0] if subjects else None,
            "saved_articles": len(self.list_articles(user_id=user_id, saved_only=True)), "daily_brief_completed": completed,
            "today_quiz_completed": bool(latest and latest.completed_at.date() == today),
            "latest_quiz_score": latest.percentage if latest else None,
            "high_risk_article_count": sum(r.risk_level == "high" for r in retention), "next_revision": next_revision}
