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
from src.current_affairs.source_policy import controlled_queries, source_adapter

log = logging.getLogger(__name__)

REJECTION_DIAGNOSTICS = (
    "search_result_rejected_before_url_processing", "unapproved_domain", "redirect_to_unapproved_domain",
    "homepage_index_archive_search_page", "duplicate_canonical_url", "duplicate_content_hash",
    "extraction_http_failure", "blocked_challenge_response", "insufficient_clean_text",
    "missing_article_specific_title", "insufficient_substantive_paragraphs",
    "excessive_boilerplate_navigation", "invalid_implausible_publication_date", "summarization_failure",
    "unsupported_factual_claims", "embedding_indexing_failure", "unapproved_current_affairs_source",
)


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
        return controlled_queries(stamp)

    def reindex_active(self):
        with self.sessions() as session:
            rows = list(session.scalars(select(CurrentAffairsArticle).where(CurrentAffairsArticle.status == "active")))
        indexed, errors = 0, []
        for row in rows:
            try:
                self._index(row); indexed += 1
            except Exception as error:
                errors.append({"article_id": row.id, "error": type(error).__name__})
        return {"accepted": len(rows), "indexed": indexed, "errors": errors}

    def archive_misclassified_active(self):
        with self.sessions() as session:
            rows = list(session.scalars(select(CurrentAffairsArticle).where(CurrentAffairsArticle.status == "active")))
            invalid = [row for row in rows if WebSearch.page_type(row.source_url) != "article" or source_adapter(row.source_url) is None]
            for row in invalid: row.status = "archived"
            session.commit()
        if invalid:
            try:
                store = VectorStore()
                for row in invalid: store.collection.delete(where={"article_id": row.id})
            except Exception as error:
                log.warning("Current Affairs invalid-vector cleanup failed: %s", type(error).__name__)
        return [row.id for row in invalid]

    async def collect_for_date(self, collection_date: date, *, max_results=10, generate_brief=False, language="english", queries=None, urls=None):
        self.archive_misclassified_active()
        use_source_discovery = queries is None and not urls
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
        discovered = {"candidates": [], "source_progress": []}
        if use_source_discovery and hasattr(self.web, "discover_feeds"):
            discovered = await asyncio.to_thread(self.web.discover_feeds, max_results)
            source_progress.extend(discovered.get("source_progress", []))
            if hasattr(self.web, "discover_listings"):
                listings = await asyncio.to_thread(self.web.discover_listings, max_results)
                discovered["candidates"].extend(listings.get("candidates", []))
                source_progress.extend(listings.get("source_progress", []))
        work = [("candidate", candidate) for candidate in discovered.get("candidates", [])]
        work += [("query", query) for query in queries] + [("url", url) for url in urls]
        for kind, value in work:
            if collected >= max_results: break
            try:
                if kind == "url": found = await asyncio.to_thread(self.web.fetch_url, value, f"current affairs {collection_date.isoformat()}")
                elif kind == "candidate": found = await asyncio.to_thread(self.web.fetch_candidate, value, f"current affairs {collection_date.isoformat()}")
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
                    existing = session.scalar(select(CurrentAffairsArticle).where(
                        or_(CurrentAffairsArticle.source_url == chunk.get("source_url", ""),
                            CurrentAffairsArticle.content_hash == (chunk.get("content_hash") or "")),
                        CurrentAffairsArticle.status == "active"))
                if existing:
                    duplicates += 1; article_ids.append(existing.id)
                    duplicate_code = "duplicate_canonical_url" if existing.source_url == chunk.get("source_url") else "duplicate_content_hash"
                    source_progress.append({"url": chunk.get("source_url"), "status": "duplicate",
                        "rejection_code": duplicate_code, "reason": duplicate_code, "summarization": "not attempted"})
                    continue
                row = await self.ingest_chunk(chunk)
                if row.status == "active": article_ids.append(row.id)
                quality = chunk.get("article_quality") or WebSearch.article_quality(chunk)
                final_progress = {"url": chunk.get("source_url"), "page_type": quality["page_type"],
                    "quality_score": quality["quality_score"], "status": "accepted" if row.status == "active" else "rejected",
                    "rejection_code": None if row.status == "active" else getattr(row, "diagnostic_reason", "summarization_failure"),
                    "reason": row.summary if row.status != "active" else "grounded article accepted",
                    "summarization": "accepted" if row.status == "active" else "rejected"}
                pending = next((item for item in source_progress if item.get("url") == chunk.get("source_url") and item.get("status") == "candidate"), None)
                if pending: pending.update(final_progress)
                else: source_progress.append(final_progress)
                if row.status == "active": accepted += 1
                else: rejected += 1
        brief_status, brief_error, brief_date = "not_requested", None, None
        if generate_brief:
            try:
                target_date = collection_date
                if not self.list_articles(date_value=target_date) and article_ids:
                    with self.sessions() as session:
                        dates = list(session.scalars(select(CurrentAffairsArticle.publication_date).where(
                            CurrentAffairsArticle.id.in_(article_ids), CurrentAffairsArticle.status == "active")))
                    target_date = max((value for value in dates if value), default=collection_date)
                self.generate_daily(target_date, language); brief_status = "generated"; brief_date = target_date
            except Exception as error: brief_status, brief_error = "failed", str(error)
        log.info("Current Affairs collection complete raw=%d approved=%d rejected_domains=%d extraction_attempts=%d extraction_successes=%d final_candidates=%d",
            diagnostics["raw_results"], diagnostics["approved_results"], diagnostics["rejected_domains"],
            diagnostics["extraction_attempts"], diagnostics["extraction_successes"], collected)
        rejection_breakdown = Counter({code: 0 for code in REJECTION_DIAGNOSTICS})
        rejection_breakdown.update(item.get("rejection_code") for item in source_progress if item.get("rejection_code"))
        return {"date": collection_date, "search_provider": provider_name if queries else "direct_url",
            "queries_executed": queries, **diagnostics, "zero_result_reason": "; ".join(dict.fromkeys(zero_reasons)) or None,
            "source_progress": source_progress,
            "rejection_breakdown": dict(sorted(rejection_breakdown.items())),
            "extraction_failures": diagnostics["extraction_attempts"] - diagnostics["extraction_successes"],
            "collected": collected, "accepted": accepted, "rejected": rejected,
            "duplicates": duplicates, "article_ids": list(dict.fromkeys(article_ids)), "collection_errors": errors,
            "daily_brief": brief_status, "brief_date": brief_date, "brief_error": brief_error}

    async def ingest_chunk(self, chunk: dict):
        url = chunk.get("source_url", ""); policy = TrustedSourcePolicy.classify(url)
        content_hash = chunk.get("content_hash") or hashlib.sha256(chunk.get("text", "").encode()).hexdigest()
        with self.sessions() as session:
            existing = session.scalar(select(CurrentAffairsArticle).where(or_(
                CurrentAffairsArticle.source_url == url, CurrentAffairsArticle.content_hash == content_hash)))
            if existing and existing.status == "active": return existing
            if existing:
                session.delete(existing); session.commit()
        classification = self.classifier.classify(chunk.get("text", ""))
        quality = chunk.get("article_quality") or WebSearch.article_quality(chunk)
        adapter = source_adapter(url)
        status = "active" if policy and adapter and quality["is_article"] else "rejected"
        rejection_code = None if status == "active" else "unapproved_current_affairs_source" if policy and not adapter else WebSearch.rejection_code("; ".join(quality["reasons"]))
        summary = None
        if status == "active":
            prompt = f"""Use ONLY the article body and metadata below. Return one strict JSON object with keys what_happened, background, why_it_matters, prelims_facts, mains_relevance, subject, topic, importance_level. prelims_facts and mains_relevance must be arrays of plain strings and may be empty. background and why_it_matters must be strings and may be empty. what_happened must state the grounded core event. Copy dates and quantities exactly when used; never calculate, extrapolate, or invent an end date or consequence. Omit an optional point instead of inferring it. importance_level must be low, medium, or high.\nTITLE: {chunk.get('source_title')}\nPUBLISHER: {chunk.get('publisher')}\nURL: {url}\nPUBLICATION DATE: {chunk.get('publication_date') or 'unavailable'}\nARTICLE BODY:\n{chunk['text']}"""
            try:
                raw = await self.llm.generate(prompt=prompt, mode="learn", depth="quick")
                summary = self._parse_summary(raw)
                if not self._summary_is_grounded(summary, chunk["text"]):
                    status = "rejected"; summary = None; rejection_code = "unsupported_factual_claims"
            except (json.JSONDecodeError, ValidationError, RuntimeError):
                status = "rejected"; rejection_code = "summarization_failure"
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
        row.diagnostic_reason = rejection_code
        if row.status != "active": return row
        try:
            await asyncio.to_thread(self._index, row)
        except Exception:
            row.status = "rejected"; row.summary = "Rejected: embedding/indexing failure."
            row.diagnostic_reason = "embedding_indexing_failure"
            return row
        with self.sessions() as session: session.add(row); session.commit(); session.refresh(row)
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
                      topic=None, importance=None, publisher=None, saved_only=False, search=None, include_rejected=False,
                      cadence=None, content_type=None, week_label=None, month=None, year=None):
        # 1. Database Sourcing with Fallback
        with self.sessions() as session:
            saved_ids = set(session.scalars(select(SavedCurrentAffairs.article_id).where(SavedCurrentAffairs.user_id == user_id)))
            
            # Common query setup
            base_query = select(CurrentAffairsArticle)
            if not include_rejected: base_query = base_query.where(CurrentAffairsArticle.status == "active")
            base_query = base_query.where(
                ~CurrentAffairsArticle.title.ilike("%Pending Backfill%"),
                ~CurrentAffairsArticle.title.ilike("%Image Only PDF%"),
                ~CurrentAffairsArticle.title.ilike("%Mode Test%"),
                ~CurrentAffairsArticle.title.ilike("%Internal Reader Test%"),
                ~CurrentAffairsArticle.title.ilike("%July Week 3%"),
                ~CurrentAffairsArticle.title.ilike("%July 2026%"),
                ~CurrentAffairsArticle.id.like("test-%"),
                ~CurrentAffairsArticle.id.like("demo-%"),
                ~CurrentAffairsArticle.id.like("sample-%"),
                ~CurrentAffairsArticle.id.like("isolated-%"),
                ~CurrentAffairsArticle.id.like("prog-%")
            )
            if date_value: base_query = base_query.where(CurrentAffairsArticle.publication_date == date_value)
            if date_from: base_query = base_query.where(CurrentAffairsArticle.publication_date >= date_from)
            if date_to: base_query = base_query.where(CurrentAffairsArticle.publication_date <= date_to)
            if subject: base_query = base_query.where(CurrentAffairsArticle.subject == subject)
            if topic: base_query = base_query.where(CurrentAffairsArticle.topic == topic)
            if importance: base_query = base_query.where(CurrentAffairsArticle.importance_level == importance)
            if cadence: base_query = base_query.where(CurrentAffairsArticle.cadence == cadence)
            if content_type: base_query = base_query.where(CurrentAffairsArticle.content_type == content_type)
            if week_label: base_query = base_query.where(CurrentAffairsArticle.week_label == week_label)
            if month: base_query = base_query.where(CurrentAffairsArticle.month == month)
            if year: base_query = base_query.where(CurrentAffairsArticle.year == year)
            if saved_only: base_query = base_query.where(CurrentAffairsArticle.id.in_(saved_ids))
            if search:
                pattern = f"%{search}%"; base_query = base_query.where(or_(CurrentAffairsArticle.title.ilike(pattern), CurrentAffairsArticle.summary.ilike(pattern)))
            
            # Fallback sourcing execution
            if publisher:
                query = base_query.where(CurrentAffairsArticle.publisher == publisher)
                rows = list(session.scalars(query.order_by(CurrentAffairsArticle.publication_date.desc(), CurrentAffairsArticle.retrieved_at.desc())))
            else:
                # Try PWOnlyIAS first
                query_pw = base_query.where(CurrentAffairsArticle.publisher == "PWOnlyIAS")
                rows = list(session.scalars(query_pw.order_by(CurrentAffairsArticle.publication_date.desc(), CurrentAffairsArticle.retrieved_at.desc())))
                if not rows:
                    # Fallback to other sources
                    rows = list(session.scalars(base_query.order_by(CurrentAffairsArticle.publication_date.desc(), CurrentAffairsArticle.retrieved_at.desc())))

        # 2. Demo Mode dummy dataset support
        from src.core.config import settings
        DEMO_MODE = getattr(settings, "REPORT_DEMO_MODE", False)
        dummy_rows = []
        if DEMO_MODE:
            dummy_data = [
                {
                    "id": "dmy-art-001",
                    "title": "India-France Bilateral Trade Agreement: Strengthening Strategic Partnership",
                    "summary": "India and France have signed a landmark bilateral trade agreement aimed at doubling trade volume by 2030. The partnership focuses on technology transfer, defense co-production, and green energy initiatives.",
                    "source_title": "Press Information Bureau",
                    "publisher": "PIB",
                    "source_url": "https://pib.gov.in/dummy-1",
                    "publication_date": date(2026, 7, 24),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "International Relations",
                    "topic": "Bilateral Relations",
                    "importance_level": "high",
                    "cadence": "daily",
                    "content_type": "article",
                    "status": "active"
                },
                {
                    "id": "dmy-art-002",
                    "title": "RBI Directive on Digital Lending: Protecting Borrowers and Enhancing Transparency",
                    "summary": "The Reserve Bank of India has issued new guidelines for digital lending platforms. The directive mandates clear disclosure of annual percentage rates, prevents unauthorized credit limit increases, and strengthens grievance redressal.",
                    "source_title": "Reserve Bank of India",
                    "publisher": "RBI",
                    "source_url": "https://rbi.org.in/dummy-2",
                    "publication_date": date(2026, 7, 23),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Economy",
                    "topic": "Banking Reforms",
                    "importance_level": "medium",
                    "cadence": "daily",
                    "content_type": "article",
                    "status": "active"
                },
                {
                    "id": "dmy-art-003",
                    "title": "Weekly Current Affairs Digest: Science & Tech Breakthroughs",
                    "summary": "A comprehensive roundup of scientific developments this week, including India's launch of the Aditya-L1 solar observatory research module and advancements in indigenously developed semiconductor designs.",
                    "source_title": "ForumIAS Daily",
                    "publisher": "ForumIAS",
                    "source_url": "https://forumias.com/dummy-3",
                    "publication_date": date(2026, 7, 20),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Science and Technology",
                    "topic": "Space Missions",
                    "importance_level": "high",
                    "cadence": "weekly",
                    "content_type": "article",
                    "status": "active"
                },
                {
                    "id": "dmy-art-004",
                    "title": "Weekly Environmental Policy Roundup: Focus on Wetland Conservation",
                    "summary": "This week's roundup highlights new Ramsar site designations in India and the implementation of the National Wetland Conservation Programme across key ecological zones.",
                    "source_title": "InsightsIAS Editorial",
                    "publisher": "InsightsIAS",
                    "source_url": "https://insightsias.com/dummy-4",
                    "publication_date": date(2026, 7, 19),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Environment and Ecology",
                    "topic": "Wetland Conservation",
                    "importance_level": "medium",
                    "cadence": "weekly",
                    "content_type": "article",
                    "status": "active"
                },
                {
                    "id": "dmy-art-005",
                    "title": "Monthly Polity and Governance Review: June-July 2026",
                    "summary": "An in-depth monthly analysis of key bills introduced in Parliament, landmark judicial rulings on federal relations, and administrative reforms in civil services recruitment.",
                    "source_title": "Drishti IAS Current Manthan",
                    "publisher": "Drishti IAS",
                    "source_url": "https://drishtiias.com/dummy-5",
                    "publication_date": date(2026, 7, 15),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Polity and Governance",
                    "topic": "Constitutional Amendments",
                    "importance_level": "high",
                    "cadence": "monthly",
                    "content_type": "article",
                    "status": "active"
                },
                {
                    "id": "dmy-art-006",
                    "title": "Monthly Economics & Infrastructure Bulletin",
                    "summary": "Monthly report on GST collection trends, infrastructure development under PM Gati Shakti, and foreign direct investment inflows in the manufacturing sector.",
                    "source_title": "ForumIAS Monthly",
                    "publisher": "ForumIAS",
                    "source_url": "https://forumias.com/dummy-6",
                    "publication_date": date(2026, 7, 10),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Economy",
                    "topic": "Infrastructure",
                    "importance_level": "medium",
                    "cadence": "monthly",
                    "content_type": "article",
                    "status": "active"
                },
                {
                    "id": "dmy-art-007",
                    "title": "Mains Q&A: Public Interest Litigation and Judicial Activism",
                    "summary": "Question: Critically analyze the evolution of Public Interest Litigation (PIL) in India.\n\nAnswer: Discusses origin, landmark judgments, benefits in ensuring justice for marginalized groups, and concerns regarding judicial overreach.",
                    "source_title": "Drishti IAS Mains Focus",
                    "publisher": "Drishti IAS",
                    "source_url": "https://drishtiias.com/dummy-7",
                    "publication_date": date(2026, 7, 22),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Polity and Governance",
                    "topic": "Judicial System",
                    "importance_level": "high",
                    "cadence": "daily",
                    "content_type": "prelims_qa",
                    "status": "active"
                },
                {
                    "id": "dmy-art-008",
                    "title": "Mains Q&A: India's Net-Zero Targets by 2070",
                    "summary": "Question: Discuss the feasibility of India reaching net-zero carbon emissions by 2070.\n\nAnswer: Examines renewable energy transition, electric vehicle policies, coal reliance, industrial challenges, and global climate commitments.",
                    "source_title": "InsightsIAS Q&A",
                    "publisher": "InsightsIAS",
                    "source_url": "https://insightsias.com/dummy-8",
                    "publication_date": date(2026, 7, 21),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Environment and Ecology",
                    "topic": "Climate Change",
                    "importance_level": "high",
                    "cadence": "daily",
                    "content_type": "prelims_qa",
                    "status": "active"
                },
                {
                    "id": "dmy-art-009",
                    "title": "Temple Architecture of the Chola Dynasty: Cultural Legacy",
                    "summary": "An analysis of Dravidian temple architecture under the Cholas, highlighting unique features of the Brihadisvara Temple, socio-economic roles of temples, and bronze sculpture achievements.",
                    "source_title": "Ministry of External Affairs (MEA)",
                    "publisher": "MEA",
                    "source_url": "https://mea.gov.in/dummy-9",
                    "publication_date": date(2026, 7, 20),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "History",
                    "topic": "Art and Culture",
                    "importance_level": "medium",
                    "cadence": "daily",
                    "content_type": "article",
                    "status": "active"
                },
                {
                    "id": "dmy-art-010",
                    "title": "Monsoon Variability and El Nino Southern Oscillation (ENSO)",
                    "summary": "A study on the impact of El Nino and La Nina events on Indian summer monsoon rainfall, forecasting technologies, and agricultural adaptation strategies.",
                    "source_title": "Press Information Bureau",
                    "publisher": "PIB",
                    "source_url": "https://pib.gov.in/dummy-10",
                    "publication_date": date(2026, 7, 18),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Geography",
                    "topic": "Climatology",
                    "importance_level": "medium",
                    "cadence": "daily",
                    "content_type": "article",
                    "status": "active"
                }
            ]
            for d in dummy_data:
                # Apply same filters to dummy items
                if publisher and d["publisher"] != publisher: continue
                if date_value and d["publication_date"] != date_value: continue
                if date_from and d["publication_date"] < date_from: continue
                if date_to and d["publication_date"] > date_to: continue
                if subject and d["subject"] != subject: continue
                if topic and d["topic"] != topic: continue
                if importance and d["importance_level"] != importance: continue
                if cadence and d["cadence"] != cadence: continue
                if content_type and d["content_type"] != content_type: continue
                if search:
                    pattern = search.lower()
                    if pattern not in d["title"].lower() and pattern not in d["summary"].lower():
                        continue
                
                # Convert dict to model instance
                art = CurrentAffairsArticle(
                    id=d["id"],
                    title=d["title"],
                    summary=d["summary"],
                    source_title=d["source_title"],
                    publisher=d["publisher"],
                    source_url=d["source_url"],
                    source_type="current_affairs",
                    publication_date=d["publication_date"],
                    retrieved_at=d["retrieved_at"],
                    subject=d["subject"],
                    topic=d["topic"],
                    syllabus_tags_json=[],
                    importance_level=d["importance_level"],
                    cadence=d["cadence"],
                    content_type=d["content_type"],
                    status=d["status"],
                    relevance_prelims="Grounded facts for prelims practice",
                    relevance_mains="Grounded facts for mains analysis",
                    content_hash=d["id"],
                    pdf_availability="unknown",
                    extraction_status="completed",
                    content_blocks_json=[{"type": "paragraph", "text": d["summary"], "page_ref": 1}],
                    qa_pairs_json=[],
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                dummy_rows.append(art)

        # Merge dummy data with real data
        rows = dummy_rows + rows

        # Deduplicate rows by canonical URL or title + publication_date
        unique_rows = []
        seen = set()
        for row in rows:
            identity = row.source_url or f"{row.title.strip().lower()}_{row.publication_date}"
            if identity not in seen:
                seen.add(identity)
                unique_rows.append(row)

        opened = {e.metadata_json.get("article_id") for e in self.activity.list_events(user_id=user_id, event_type="current_affairs_opened") if e.metadata_json}
        return [(row, row.id in saved_ids, row.id in opened) for row in unique_rows]

    def get_article(self, article_id, *, user_id="user_001", record_open=True):
        from src.core.config import settings
        if getattr(settings, "REPORT_DEMO_MODE", False) and article_id.startswith("dmy-"):
            # Dummy data lookup
            dummy_data = [
                {
                    "id": "dmy-art-001",
                    "title": "India-France Bilateral Trade Agreement: Strengthening Strategic Partnership",
                    "summary": "India and France have signed a landmark bilateral trade agreement aimed at doubling trade volume by 2030. The partnership focuses on technology transfer, defense co-production, and green energy initiatives.",
                    "source_title": "Press Information Bureau",
                    "publisher": "PIB",
                    "source_url": "https://pib.gov.in/dummy-1",
                    "publication_date": date(2026, 7, 24),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "International Relations",
                    "topic": "Bilateral Relations",
                    "importance_level": "high",
                    "cadence": "daily",
                    "content_type": "article",
                    "status": "active"
                },
                {
                    "id": "dmy-art-002",
                    "title": "RBI Directive on Digital Lending: Protecting Borrowers and Enhancing Transparency",
                    "summary": "The Reserve Bank of India has issued new guidelines for digital lending platforms. The directive mandates clear disclosure of annual percentage rates, prevents unauthorized credit limit increases, and strengthens grievance redressal.",
                    "source_title": "Reserve Bank of India",
                    "publisher": "RBI",
                    "source_url": "https://rbi.org.in/dummy-2",
                    "publication_date": date(2026, 7, 23),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Economy",
                    "topic": "Banking Reforms",
                    "importance_level": "medium",
                    "cadence": "daily",
                    "content_type": "article",
                    "status": "active"
                },
                {
                    "id": "dmy-art-003",
                    "title": "Weekly Current Affairs Digest: Science & Tech Breakthroughs",
                    "summary": "A comprehensive roundup of scientific developments this week, including India's launch of the Aditya-L1 solar observatory research module and advancements in indigenously developed semiconductor designs.",
                    "source_title": "ForumIAS Daily",
                    "publisher": "ForumIAS",
                    "source_url": "https://forumias.com/dummy-3",
                    "publication_date": date(2026, 7, 20),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Science and Technology",
                    "topic": "Space Missions",
                    "importance_level": "high",
                    "cadence": "weekly",
                    "content_type": "article",
                    "status": "active"
                },
                {
                    "id": "dmy-art-004",
                    "title": "Weekly Environmental Policy Roundup: Focus on Wetland Conservation",
                    "summary": "This week's roundup highlights new Ramsar site designations in India and the implementation of the National Wetland Conservation Programme across key ecological zones.",
                    "source_title": "InsightsIAS Editorial",
                    "publisher": "InsightsIAS",
                    "source_url": "https://insightsias.com/dummy-4",
                    "publication_date": date(2026, 7, 19),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Environment and Ecology",
                    "topic": "Wetland Conservation",
                    "importance_level": "medium",
                    "cadence": "weekly",
                    "content_type": "article",
                    "status": "active"
                },
                {
                    "id": "dmy-art-005",
                    "title": "Monthly Polity and Governance Review: June-July 2026",
                    "summary": "An in-depth monthly analysis of key bills introduced in Parliament, landmark judicial rulings on federal relations, and administrative reforms in civil services recruitment.",
                    "source_title": "Drishti IAS Current Manthan",
                    "publisher": "Drishti IAS",
                    "source_url": "https://drishtiias.com/dummy-5",
                    "publication_date": date(2026, 7, 15),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Polity and Governance",
                    "topic": "Constitutional Amendments",
                    "importance_level": "high",
                    "cadence": "monthly",
                    "content_type": "article",
                    "status": "active"
                },
                {
                    "id": "dmy-art-006",
                    "title": "Monthly Economics & Infrastructure Bulletin",
                    "summary": "Monthly report on GST collection trends, infrastructure development under PM Gati Shakti, and foreign direct investment inflows in the manufacturing sector.",
                    "source_title": "ForumIAS Monthly",
                    "publisher": "ForumIAS",
                    "source_url": "https://forumias.com/dummy-6",
                    "publication_date": date(2026, 7, 10),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Economy",
                    "topic": "Infrastructure",
                    "importance_level": "medium",
                    "cadence": "monthly",
                    "content_type": "article",
                    "status": "active"
                },
                {
                    "id": "dmy-art-007",
                    "title": "Mains Q&A: Public Interest Litigation and Judicial Activism",
                    "summary": "Question: Critically analyze the evolution of Public Interest Litigation (PIL) in India.\n\nAnswer: Discusses origin, landmark judgments, benefits in ensuring justice for marginalized groups, and concerns regarding judicial overreach.",
                    "source_title": "Drishti IAS Mains Focus",
                    "publisher": "Drishti IAS",
                    "source_url": "https://drishtiias.com/dummy-7",
                    "publication_date": date(2026, 7, 22),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Polity and Governance",
                    "topic": "Judicial System",
                    "importance_level": "high",
                    "cadence": "daily",
                    "content_type": "prelims_qa",
                    "status": "active"
                },
                {
                    "id": "dmy-art-008",
                    "title": "Mains Q&A: India's Net-Zero Targets by 2070",
                    "summary": "Question: Discuss the feasibility of India reaching net-zero carbon emissions by 2070.\n\nAnswer: Examines renewable energy transition, electric vehicle policies, coal reliance, industrial challenges, and global climate commitments.",
                    "source_title": "InsightsIAS Q&A",
                    "publisher": "InsightsIAS",
                    "source_url": "https://insightsias.com/dummy-8",
                    "publication_date": date(2026, 7, 21),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Environment and Ecology",
                    "topic": "Climate Change",
                    "importance_level": "high",
                    "cadence": "daily",
                    "content_type": "prelims_qa",
                    "status": "active"
                },
                {
                    "id": "dmy-art-009",
                    "title": "Temple Architecture of the Chola Dynasty: Cultural Legacy",
                    "summary": "An analysis of Dravidian temple architecture under the Cholas, highlighting unique features of the Brihadisvara Temple, socio-economic roles of temples, and bronze sculpture achievements.",
                    "source_title": "Ministry of External Affairs (MEA)",
                    "publisher": "MEA",
                    "source_url": "https://mea.gov.in/dummy-9",
                    "publication_date": date(2026, 7, 20),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "History",
                    "topic": "Art and Culture",
                    "importance_level": "medium",
                    "cadence": "daily",
                    "content_type": "article",
                    "status": "active"
                },
                {
                    "id": "dmy-art-010",
                    "title": "Monsoon Variability and El Nino Southern Oscillation (ENSO)",
                    "summary": "A study on the impact of El Nino and La Nina events on Indian summer monsoon rainfall, forecasting technologies, and agricultural adaptation strategies.",
                    "source_title": "Press Information Bureau",
                    "publisher": "PIB",
                    "source_url": "https://pib.gov.in/dummy-10",
                    "publication_date": date(2026, 7, 18),
                    "retrieved_at": datetime.now(timezone.utc),
                    "subject": "Geography",
                    "topic": "Climatology",
                    "importance_level": "medium",
                    "cadence": "daily",
                    "content_type": "article",
                    "status": "active"
                }
            ]
            for d in dummy_data:
                if d["id"] == article_id:
                    row = CurrentAffairsArticle(
                        id=d["id"],
                        title=d["title"],
                        summary=d["summary"],
                        source_title=d["source_title"],
                        publisher=d["publisher"],
                        source_url=d["source_url"],
                        source_type="current_affairs",
                        publication_date=d["publication_date"],
                        retrieved_at=d["retrieved_at"],
                        subject=d["subject"],
                        topic=d["topic"],
                        syllabus_tags_json=[],
                        importance_level=d["importance_level"],
                        cadence=d["cadence"],
                        content_type=d["content_type"],
                        status=d["status"],
                        relevance_prelims="Grounded facts for prelims practice",
                        relevance_mains="Grounded facts for mains analysis",
                        content_hash=d["id"],
                        pdf_availability="unknown",
                        extraction_status="completed",
                        content_blocks_json=[{"type": "paragraph", "text": d["summary"], "page_ref": 1}],
                        qa_pairs_json=[],
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc)
                    )
                    return row

        with self.sessions() as session: row = session.get(CurrentAffairsArticle, article_id)
        if not row or row.status != "active": return None
        if record_open: self.activity.record_event("current_affairs_opened", datetime.now(timezone.utc), user_id=user_id,
            subject=row.subject, topic=row.topic, metadata_json={"article_id": row.id})
        return row

    def get_article_content(self, article_id, *, user_id="user_001"):
        row = self.get_article(article_id, user_id=user_id, record_open=True)
        if not row: return None
        with self.sessions() as session:
            saved = bool(session.scalar(select(SavedCurrentAffairs).where(
                SavedCurrentAffairs.user_id == user_id, SavedCurrentAffairs.article_id == article_id)))

        blocks = row.content_blocks_json or []
        page_refs = sorted(list({
            str(b["page_ref"]) for b in blocks if isinstance(b, dict) and b.get("page_ref") is not None
        }))

        mode = getattr(settings, "CURRENT_AFFAIRS_CONTENT_MODE", "private_local")
        if mode == "public_summary":
            blocks = [
                {"type": "heading", "level": 2, "text": "Structured Study Summary"},
                {"type": "paragraph", "text": row.summary or ""},
                {"type": "heading", "level": 3, "text": "Prelims Key Facts"},
                {"type": "paragraph", "text": row.relevance_prelims or ""},
                {"type": "heading", "level": 3, "text": "Mains Analytical Dimensions"},
                {"type": "paragraph", "text": row.relevance_mains or ""}
            ]

        ext_status = row.extraction_status or "ready"
        if ext_status == "completed": ext_status = "ready"
        avail = "available" if ext_status in ("ready", "completed") else "unavailable"
        if ext_status == "image_only": avail = "unavailable"

        return {
            "id": row.id,
            "slug": row.slug or row.id,
            "title": row.title,
            "provider": "PWOnlyIAS",
            "cadence": row.cadence or "daily",
            "subjects": [row.subject] if row.subject else ["General Studies"],
            "publication_date": str(row.publication_date) if row.publication_date else None,
            "coverage_period": row.week_label or (f"{row.month}/{row.year}" if row.month and row.year else "Current"),
            "description": row.summary,
            "content_blocks": blocks,
            "page_references": page_refs,
            "source_page_url": row.source_url,
            "official_pdf_url": row.pdf_url,
            "extraction_status": ext_status,
            "availability": avail,
            "saved": saved
        }

    @staticmethod
    def extract_html_blocks(text: str) -> list[dict]:
        blocks = []
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines:
            if line.startswith("## ") or line.startswith("# "):
                blocks.append({"type": "heading", "level": 2, "text": line.lstrip("# ").strip()})
            elif line.startswith("### "):
                blocks.append({"type": "heading", "level": 3, "text": line.lstrip("# ").strip()})
            elif line.startswith("- ") or line.startswith("* "):
                if blocks and blocks[-1].get("type") == "bullet_list":
                    blocks[-1]["items"].append(line[2:].strip())
                else:
                    blocks.append({"type": "bullet_list", "items": [line[2:].strip()]})
            else:
                blocks.append({"type": "paragraph", "text": line})
        return blocks

    @staticmethod
    def extract_pdf_blocks(pdf_file_path: str) -> tuple[list[dict], str]:
        from pypdf import PdfReader
        reader = PdfReader(pdf_file_path)
        blocks, full_text = [], []
        for idx, page in enumerate(reader.pages, start=1):
            txt = page.extract_text() or ""
            if txt.strip():
                full_text.append(txt)
                lines = [line.strip() for line in txt.splitlines() if line.strip()]
                for line in lines:
                    if len(line) < 80 and line.isupper():
                        blocks.append({"type": "heading", "level": 2, "text": line, "page_start": idx, "page_end": idx, "page_ref": idx})
                    else:
                        blocks.append({"type": "paragraph", "text": line, "page_start": idx, "page_end": idx, "page_ref": idx})
        combined = "\n".join(full_text)
        status = "ready" if combined.strip() else "image_only"
        return blocks, status

    def backfill_records(self, limit=10, dry_run=False):
        with self.sessions() as session:
            query = select(CurrentAffairsArticle).where(
                CurrentAffairsArticle.publisher == "PWOnlyIAS",
                or_(CurrentAffairsArticle.content_blocks_json == None, CurrentAffairsArticle.extraction_status != "ready")
            ).limit(limit)
            rows = list(session.scalars(query))
        processed = 0
        for row in rows:
            blocks = self.extract_html_blocks(f"{row.title}\n\n{row.summary}\n\nKey Facts:\n{row.relevance_prelims}\n\nMains Dimensions:\n{row.relevance_mains}")
            row.content_blocks_json = blocks
            row.extraction_status = "ready"
            row.content_checksum = hashlib.sha256(json.dumps(blocks).encode()).hexdigest()
            row.indexed_at = datetime.now(timezone.utc)
            if not dry_run:
                with self.sessions() as session:
                    session.add(row); session.commit()
                try: self._index(row)
                except Exception as error: log.warning("Backfill index failed for %s: %s", row.id, error)
            processed += 1
        return {"total_found": len(rows), "processed": processed, "dry_run": dry_run}

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
        grouped = []
        for article in articles:
            words = set(re.findall(r"[a-z0-9]+", article.title.casefold())) - {"the", "a", "an", "of", "for", "to", "and", "in", "on", "india"}
            duplicate = False
            for existing in grouped:
                other = set(re.findall(r"[a-z0-9]+", existing.title.casefold())) - {"the", "a", "an", "of", "for", "to", "and", "in", "on", "india"}
                similarity = len(words & other) / len(words | other) if words and other else 0
                if article.topic == existing.topic and similarity >= .5: duplicate = True; break
            if not duplicate: grouped.append(article)
        articles = grouped
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
        from src.core.config import settings
        if getattr(settings, "REPORT_DEMO_MODE", False):
            return {
                "unread_important_stories": 3,
                "top_subject": "International Relations",
                "saved_articles": 2,
                "daily_brief_completed": True,
                "today_quiz_completed": True,
                "latest_quiz_score": 80.0,
                "high_risk_article_count": 1,
                "next_revision": "2026-07-24T10:00:00Z",
                "demo_mode": True
            }

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
