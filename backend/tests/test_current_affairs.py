import asyncio
import json
from types import SimpleNamespace
from datetime import date, datetime, timezone

from src.current_affairs.service import CurrentAffairsService
from src.mastery.manager import MasteryManager
from src.rag.retriever import Retriever
from src.rag.vector_store import VectorStore
from src.search.local_search import LocalSearch
from fastapi.testclient import TestClient
from src.main import app
from src.core.config import settings
from src.api.routes import current_affairs as route
from scripts.collect_current_affairs import run_collection


class SummaryLlm:
    async def generate(self, **_kwargs):
        return json.dumps({"what_happened": "The Reserve Bank announced a grounded policy development for the economy.",
            "background": "The measure follows the existing monetary policy framework.",
            "why_it_matters": "It affects inflation management and financial conditions.",
            "prelims_facts": ["RBI conducts monetary policy", "The repo rate is a policy instrument"],
            "mains_relevance": "Discuss inflation control and growth trade-offs in monetary policy.",
            "syllabus_tags": ["GS III", "Indian Economy"], "importance_level": "high"})


def trusted_chunk(text=None, url="https://rbi.org.in/policy-update", publication_date=None):
    text = text or ("RBI monetary policy inflation repo rate economy financial stability. " * 8)
    return {"text": text, "score": 1.0, "source_type": "web", "source_url": url,
        "source_title": "Monetary Policy Update", "publisher": "Reserve Bank of India", "domain": "rbi.org.in",
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "publication_date": publication_date or date.today().isoformat(),
        "source_category": "official_institution", "trust_level": "official", "content_hash": "hash-" + url}


def setup(tmp_path):
    indexed = []
    service = CurrentAffairsService(db_path=str(tmp_path/"ca.sqlite3"), llm=SummaryLlm(),
        indexer=lambda article_id, chunks: indexed.append((article_id, chunks)))
    return service, indexed


def test_approved_grounded_article_classified_and_indexed(tmp_path):
    service, indexed = setup(tmp_path); row = asyncio.run(service.ingest_chunk(trusted_chunk()))
    assert row.status == "active" and row.importance_level == "high"
    assert row.subject == "Economy" and row.topic == "Monetary Policy"
    assert "What happened:" in row.summary and "Source citation:" in row.summary
    assert indexed[0][0] == row.id and "Prelims:" in indexed[0][1][0]["text"]


def test_unapproved_and_insufficient_extraction_are_rejected(tmp_path):
    service, indexed = setup(tmp_path)
    unapproved = asyncio.run(service.ingest_chunk(trusted_chunk(url="https://unknown.example/story")))
    insufficient = asyncio.run(service.ingest_chunk(trusted_chunk(text="too short", url="https://rbi.org.in/short")))
    assert unapproved.status == insufficient.status == "rejected" and indexed == []
    assert service.list_articles() == []


def test_duplicate_url_or_hash_is_prevented(tmp_path):
    service, indexed = setup(tmp_path); first = asyncio.run(service.ingest_chunk(trusted_chunk()))
    second = asyncio.run(service.ingest_chunk(trusted_chunk()))
    assert first.id == second.id and len(indexed) == 1


def test_daily_brief_and_date_subject_filters(tmp_path):
    service, _ = setup(tmp_path); row = asyncio.run(service.ingest_chunk(trusted_chunk()))
    assert service.list_articles(date_value=date.today(), subject="Economy")[0][0].id == row.id
    assert service.list_articles(subject="Geography") == []
    brief = service.generate_daily(date.today())
    assert brief.article_ids_json == [row.id] and brief.prelims_points_json and brief.mains_points_json
    assert brief.subject_breakdown_json["Economy"] == [row.id]


def test_save_unsave_open_activity_user_isolation_and_no_mastery(tmp_path):
    service, _ = setup(tmp_path); row = asyncio.run(service.ingest_chunk(trusted_chunk()))
    assert service.save(row.id, user_id="user_001") and service.list_articles(saved_only=True, user_id="user_001")
    assert service.list_articles(saved_only=True, user_id="other") == []
    assert service.get_article(row.id, user_id="user_001")
    assert service.activity.list_events(event_type="current_affairs_opened")
    assert service.activity.list_events(event_type="current_affairs_saved")
    assert MasteryManager(str(tmp_path/"ca.sqlite3")).list_topic_mastery() == []
    assert service.unsave(row.id, user_id="user_001") and service.list_articles(saved_only=True) == []


def test_daily_completion_and_dashboard_summary(tmp_path):
    service, _ = setup(tmp_path); asyncio.run(service.ingest_chunk(trusted_chunk())); service.generate_daily(date.today())
    assert not service.dashboard_summary()["daily_brief_completed"]
    assert service.get_daily(date.today())
    summary = service.dashboard_summary()
    assert summary["daily_brief_completed"] and summary["unread_important_stories"] == 1 and summary["top_subject"] == "Economy"


def test_rag_metadata_and_retrieval_identify_current_affairs():
    class Collection:
        def upsert(self, **kwargs): self.kwargs = kwargs
    store = VectorStore.__new__(VectorStore); store.collection = Collection()
    chunk = {"text": "Economy development", "title": "Update", "publisher": "RBI", "source_url": "https://rbi.org.in/x",
        "publication_date": "2026-07-15", "subject": "Economy", "topic": "Monetary Policy",
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "content_hash": "abc"}
    store.store_current_affairs("a1", [chunk], [[.1, .2]])
    metadata = store.collection.kwargs["metadatas"][0]
    assert metadata["source_type"] == "current_affairs" and metadata["article_id"] == "a1"
    formatted = Retriever._format_results({"ids": [["x"]], "documents": [["Economy development"]],
        "metadatas": [[metadata]], "distances": [[0.01]]})
    assert formatted[0]["metadata"]["source_type"] == "current_affairs"
    class R:
        def retrieve(self, _q): return formatted
    local = LocalSearch(); local.retriever = R(); result = local.search("important Economy developments this week")
    assert result["sources"][0]["source_type"] == "current_affairs" and result["sources"][0]["publisher"] == "RBI"


class ApiService:
    async def collect_for_date(self, collection_date, **_kwargs):
        return {"date": collection_date, "collected": 1, "accepted": 1, "rejected": 0, "duplicates": 0,
            "article_ids": ["a1"], "collection_errors": [], "daily_brief": "not_requested", "brief_error": None}


def test_collect_api_validation_and_admin_key(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_ADMIN_KEY", "test-key"); monkeypatch.setattr(route, "service", lambda: ApiService())
    client = TestClient(app); valid = {"date": "2026-07-15", "max_results": 10, "generate_brief": False, "language": "english"}
    assert client.post("/current-affairs/collect", json=valid).status_code == 403
    assert client.post("/current-affairs/collect", headers={"X-Internal-Key": "wrong"}, json=valid).status_code == 403
    assert client.post("/current-affairs/collect", headers={"X-Internal-Key": "test-key"}, json=valid).status_code == 200
    assert client.post("/current-affairs/collect", headers={"X-Internal-Key": "test-key"}, json={}).status_code == 422
    assert client.post("/current-affairs/collect", headers={"X-Internal-Key": "test-key"}, json={**valid, "date": "15-07-2026"}).status_code == 422
    assert client.post("/current-affairs/collect", headers={"X-Internal-Key": "test-key"}, json={**valid, "max_results": 0}).status_code == 422
    monkeypatch.setattr(settings, "INTERNAL_ADMIN_KEY", None)
    assert client.post("/current-affairs/collect", json=valid).status_code == 503


def test_collection_survives_brief_failure_and_deduplicates(tmp_path):
    service, _ = setup(tmp_path)
    class Web:
        def search(self, _query): return {"chunks": [trusted_chunk()]}
    service.web = Web(); service.generate_daily = lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("brief unavailable"))
    first = asyncio.run(service.collect_for_date(date.today(), max_results=1, generate_brief=True))
    second = asyncio.run(service.collect_for_date(date.today(), max_results=1))
    assert first["accepted"] == 1 and first["daily_brief"] == "failed" and first["brief_error"] == "brief unavailable"
    assert second["duplicates"] == 1 and second["accepted"] == 0


def test_local_script_calls_existing_service():
    class Service:
        def __init__(self): self.called = None
        async def collect_for_date(self, value, **kwargs):
            self.called = (value, kwargs); return {"date": value, "collected": 0, "accepted": 0, "rejected": 0,
                "duplicates": 0, "article_ids": [], "collection_errors": [], "daily_brief": "not_requested", "brief_error": None}
    service = Service(); args = SimpleNamespace(date=date(2026, 7, 15), max_results=10, generate_brief=False, language="english")
    result = asyncio.run(run_collection(args, service))
    assert service.called[0] == args.date and service.called[1]["max_results"] == 10 and result["date"] == args.date
