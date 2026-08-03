from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Sequence

from sqlalchemy import or_, select

from src.core.config import settings
from src.current_affairs.adapters import BaseSourceAdapter, MEAAdapter, PIBAdapter, RBIAdapter
from src.current_affairs.models import CurrentAffairsArticle, CurrentAffairsIngestionRun
from src.current_affairs.relevance import classify_subject, evaluate_relevance, generate_extractive_summary
from src.memory.storage import get_session_factory
from src.rag.embeddings import EmbeddingService
from src.rag.vector_store import VectorStore

log = logging.getLogger(__name__)

# Global in-memory lock for concurrent execution prevention in the current process
_INGESTION_LOCK = asyncio.Lock()


class OfficialCurrentAffairsIngestionService:
    def __init__(self, db_path: str | None = None):
        self.sessions = get_session_factory(db_path)

    @staticmethod
    def get_adapters(sources: list[str] | None = None) -> list[BaseSourceAdapter]:
        available = {
            "pib": PIBAdapter,
            "rbi": RBIAdapter,
            "mea": MEAAdapter,
        }
        if not sources:
            return [cls() for cls in available.values()]

        adapters = []
        for s in sources:
            s_key = s.strip().lower()
            if s_key in available:
                adapters.append(available[s_key]())
            else:
                log.warning("Unknown source adapter requested: %s", s)
        return adapters or [PIBAdapter()]

    def cleanup_stale_runs(self, max_stale_minutes: int = 30):
        with self.sessions() as session:
            stale_threshold = datetime.now(timezone.utc).timestamp() - (max_stale_minutes * 60)
            runs = list(session.scalars(
                select(CurrentAffairsIngestionRun).where(CurrentAffairsIngestionRun.status == "running")
            ))
            for run in runs:
                started_ts = run.started_at.timestamp() if run.started_at else 0
                if started_ts < stale_threshold:
                    run.status = "stale"
                    run.completed_at = datetime.now(timezone.utc)
                    run.error_summary = "Run timed out and marked stale"
            session.commit()

    def get_active_run(self) -> CurrentAffairsIngestionRun | None:
        self.cleanup_stale_runs()
        with self.sessions() as session:
            return session.scalar(
                select(CurrentAffairsIngestionRun).where(CurrentAffairsIngestionRun.status == "running")
            )

    def get_last_successful_run(self) -> CurrentAffairsIngestionRun | None:
        with self.sessions() as session:
            return session.scalar(
                select(CurrentAffairsIngestionRun)
                .where(CurrentAffairsIngestionRun.status.in_(["completed", "completed_with_errors"]))
                .order_by(CurrentAffairsIngestionRun.completed_at.desc())
            )

    async def run_ingestion(
        self,
        sources: list[str] | None = None,
        trigger_type: str = "manual",
    ) -> dict:
        # Check in-memory lock
        if _INGESTION_LOCK.locked():
            active = self.get_active_run()
            return {
                "status": "already_running",
                "run_id": active.id if active else None,
                "message": "Ingestion job is already running",
            }

        async with _INGESTION_LOCK:
            # Check DB active run
            active_db_run = self.get_active_run()
            if active_db_run:
                return {
                    "status": "already_running",
                    "run_id": active_db_run.id,
                    "message": "Ingestion job is already running in DB",
                }

            run_id = str(uuid.uuid4())
            now_utc = datetime.now(timezone.utc)
            run = CurrentAffairsIngestionRun(
                id=run_id,
                started_at=now_utc,
                status="running",
                trigger_type=trigger_type,
                source_results={},
                fetched_count=0,
                accepted_count=0,
                duplicate_count=0,
                rejected_count=0,
                summarized_count=0,
                indexed_count=0,
                failed_count=0,
            )

            with self.sessions() as session:
                session.add(run)
                session.commit()

            log.info("Starting Current Affairs ingestion run_id=%s trigger=%s sources=%s", run_id, trigger_type, sources)

            adapters = self.get_adapters(sources)
            source_results = {}
            total_fetched = total_accepted = total_duplicates = total_rejected = total_summarized = total_indexed = total_failed = 0
            errors = []

            for adapter in adapters:
                s_name = adapter.source_name
                s_info = {
                    "fetched": 0,
                    "accepted": 0,
                    "duplicates": 0,
                    "rejected": 0,
                    "status": "ok",
                    "error": None,
                }
                try:
                    items = await adapter.fetch_items()
                    s_info["fetched"] = len(items)
                    total_fetched += len(items)

                    for item in items:
                        title = item.get("title", "")
                        desc = item.get("feed_description", "") or item.get("raw_public_text", "")
                        source_url = item.get("source_url", "")
                        pub_date_str = item.get("published_at", str(date.today()))

                        # 1. Relevance check
                        is_relevant, rejection_reason = evaluate_relevance(title, desc)
                        if not is_relevant:
                            s_info["rejected"] += 1
                            total_rejected += 1
                            continue

                        # 2. Content hash & deduplication check
                        hash_raw = f"{adapter.source_id}:{title.strip().casefold()}:{pub_date_str}"
                        content_hash = hashlib.sha256(hash_raw.encode()).hexdigest()

                        with self.sessions() as session:
                            existing = session.scalar(
                                select(CurrentAffairsArticle).where(
                                    or_(
                                        CurrentAffairsArticle.source_url == source_url,
                                        CurrentAffairsArticle.content_hash == content_hash,
                                    )
                                )
                            )
                            if existing:
                                s_info["duplicates"] += 1
                                total_duplicates += 1
                                continue

                        # 3. Classification & Extractive Summary
                        classification = classify_subject(title, desc)
                        summary_text = generate_extractive_summary(
                            title=title,
                            description=desc,
                            subject=classification["subject"],
                            gs_paper=classification["gs_paper"],
                            source_name=adapter.source_name,
                            source_url=source_url,
                        )

                        # Parse date object
                        pub_date_obj = None
                        try:
                            pub_date_obj = date.fromisoformat(pub_date_str[:10])
                        except Exception:
                            pub_date_obj = date.today()

                        art_id = str(uuid.uuid4())
                        article = CurrentAffairsArticle(
                            id=art_id,
                            title=title,
                            summary=summary_text,
                            source_title=title,
                            publisher=adapter.source_name,
                            source_url=source_url,
                            source_type="current_affairs",
                            publication_date=pub_date_obj,
                            retrieved_at=datetime.now(timezone.utc),
                            subject=classification["subject"],
                            topic=classification["subject"],
                            syllabus_tags_json=[classification["subject"], classification["gs_paper"]],
                            importance_level="medium",
                            relevance_prelims=title,
                            relevance_mains=summary_text,
                            content_hash=content_hash,
                            status="active",
                            extraction_status="completed",
                            summary_method="extractive",
                            summary_model="extractive_fallback",
                            summary_generated_at=datetime.now(timezone.utc),
                            gs_paper=classification["gs_paper"],
                            relevance_reason=classification["relevance_reason"],
                            classification_method=classification["classification_method"],
                            is_demo=False,
                        )

                        with self.sessions() as session:
                            session.add(article)
                            session.commit()

                        s_info["accepted"] += 1
                        total_accepted += 1
                        total_summarized += 1

                        # 4. Chroma vector store indexing
                        try:
                            self._index_article(article)
                            with self.sessions() as session:
                                db_art = session.get(CurrentAffairsArticle, art_id)
                                if db_art:
                                    db_art.indexed_at = datetime.now(timezone.utc)
                                    session.commit()
                            total_indexed += 1
                        except Exception as idx_err:
                            log.warning("Chroma indexing deferred/failed for %s: %s", art_id, idx_err)

                except Exception as source_err:
                    s_info["status"] = "failed"
                    s_info["error"] = str(source_err)
                    total_failed += 1
                    errors.append(f"{s_name}: {source_err}")
                    log.error("Source adapter %s failed: %s", s_name, source_err)

                source_results[s_name] = s_info

            # Finalize run
            completed_at = datetime.now(timezone.utc)
            final_status = "completed" if not errors else "completed_with_errors"

            with self.sessions() as session:
                db_run = session.get(CurrentAffairsIngestionRun, run_id)
                if db_run:
                    db_run.completed_at = completed_at
                    db_run.status = final_status
                    db_run.source_results = source_results
                    db_run.fetched_count = total_fetched
                    db_run.accepted_count = total_accepted
                    db_run.duplicate_count = total_duplicates
                    db_run.rejected_count = total_rejected
                    db_run.summarized_count = total_summarized
                    db_run.indexed_count = total_indexed
                    db_run.failed_count = total_failed
                    db_run.error_summary = "; ".join(errors) if errors else None
                    session.commit()

            return {
                "run_id": run_id,
                "status": final_status,
                "fetched": total_fetched,
                "accepted": total_accepted,
                "duplicates": total_duplicates,
                "rejected": total_rejected,
                "summarized": total_summarized,
                "indexed": total_indexed,
                "failed": total_failed,
                "source_results": source_results,
                "errors": errors,
            }

    def _index_article(self, article: CurrentAffairsArticle):
        chunk = {
            "text": f"{article.title}\n{article.summary}\nSubject: {article.subject}\nGS Paper: {article.gs_paper}",
            "title": article.title,
            "publisher": article.publisher,
            "source_url": article.source_url,
            "publication_date": article.publication_date.isoformat() if article.publication_date else "",
            "subject": article.subject,
            "topic": article.topic,
            "retrieved_at": article.retrieved_at.isoformat() if article.retrieved_at else "",
            "content_hash": article.content_hash,
            "is_demo": False,
            "source_type": "current_affairs",
        }
        embeddings = EmbeddingService.generate_embeddings([chunk])
        VectorStore().store_current_affairs(article.id, [chunk], embeddings)

    def get_dates_metadata(self) -> dict:
        with self.sessions() as session:
            record_dates = list(session.scalars(
                select(CurrentAffairsArticle.publication_date)
                .where(
                    CurrentAffairsArticle.status == "active",
                    CurrentAffairsArticle.publication_date.isnot(None),
                    ~CurrentAffairsArticle.id.like("test-%"),
                    ~CurrentAffairsArticle.id.like("demo-%"),
                    ~CurrentAffairsArticle.id.like("sample-%"),
                )
            ))

        formatted_dates = sorted({d.isoformat() for d in record_dates if d}, reverse=True)
        today_str = date.today().isoformat()
        today_count = sum(1 for d in record_dates if d and d.isoformat() == today_str)

        return {
            "available_dates": formatted_dates,
            "latest_available_date": formatted_dates[0] if formatted_dates else today_str,
            "earliest_available_date": formatted_dates[-1] if formatted_dates else today_str,
            "today_record_count": today_count,
            "total_active_records": len(record_dates),
        }

    def get_sync_status(self) -> dict:
        last_run = self.get_last_successful_run()
        with self.sessions() as session:
            accepted_count = session.query(CurrentAffairsArticle).filter(
                CurrentAffairsArticle.status == "active",
                ~CurrentAffairsArticle.id.like("test-%"),
                ~CurrentAffairsArticle.id.like("demo-%"),
            ).count()

        return {
            "last_synchronized_at": last_run.completed_at.isoformat() if last_run and last_run.completed_at else None,
            "sources_checked": ["PIB", "RBI", "MEA"],
            "successful_sources": [k for k, v in (last_run.source_results if last_run else {}).items() if v.get("status") == "ok"],
            "unavailable_sources": [k for k, v in (last_run.source_results if last_run else {}).items() if v.get("status") != "ok"],
            "accepted_article_count": accepted_count,
            "last_run_status": last_run.status if last_run else "no_runs_yet",
        }
