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
from scripts.collect_current_affairs import build_parser, run_collection
from src.search.web_search import WebSearch
from src.current_affairs.models import CurrentAffairsArticle
from src.memory.storage import get_session_factory
from sqlalchemy import func, select


class SummaryLlm:
    async def generate(self, **_kwargs):
        return json.dumps({"what_happened": "The Reserve Bank announced a grounded policy development for the economy.",
            "background": "The measure follows the existing monetary policy framework.",
            "why_it_matters": "It affects inflation management and financial conditions.",
            "prelims_facts": ["RBI conducts monetary policy", "The repo rate is a policy instrument"],
            "mains_relevance": ["Discuss inflation control and growth trade-offs in monetary policy."],
            "subject": "Economy", "topic": "Monetary Policy", "importance_level": "high"})


def trusted_chunk(text=None, url="https://rbi.org.in/policy-update", publication_date=None):
    text = text or "\n".join([
        "The Reserve Bank announced a grounded monetary policy development affecting inflation and financial conditions.",
        "The measure follows the existing monetary policy framework and uses the repo rate as a policy instrument.",
        "RBI monetary policy decisions influence liquidity, economic growth, financial stability, and inflation management.",
        "The official update explains the decision and its implications for regulated banks and the Indian economy."])
    return {"text": text, "score": 1.0, "source_type": "web", "source_url": url,
        "source_title": "Monetary Policy Update", "publisher": "Reserve Bank of India", "domain": "rbi.org.in",
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "publication_date": publication_date or date.today().isoformat(),
        "source_category": "official_institution", "trust_level": "official", "content_hash": "hash-" + url,
        "metadata": {"paragraphs": text.splitlines(), "headings": ["Monetary Policy Update"], "link_text_length": 0}}


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
    reference = asyncio.run(service.ingest_chunk(trusted_chunk(url="https://britannica.com/place/India")))
    assert reference.status == "rejected" and reference.diagnostic_reason == "unapproved_current_affairs_source"


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


def test_unconfigured_provider_returns_clear_error(monkeypatch):
    monkeypatch.setattr(settings, "SEARCH_PROVIDER", "local_first")
    with __import__("pytest").raises(RuntimeError, match="Current Affairs search provider is not configured for live web discovery"):
        WebSearch(cache=SimpleNamespace()).validate_configuration()


def test_cli_query_and_direct_url_are_repeatable():
    args = build_parser().parse_args(["--date", "2026-07-15", "--query", "PIB query", "--query", "RBI query",
        "--url", "https://pib.gov.in/story", "--url", "https://rbi.org.in/story"])
    assert args.query == ["PIB query", "RBI query"]
    assert args.url == ["https://pib.gov.in/story", "https://rbi.org.in/story"]


def test_default_queries_are_date_aware_and_cover_required_areas():
    queries = CurrentAffairsService.default_queries(date(2026, 7, 15)); joined = " ".join(queries).casefold()
    assert len(queries) == 7 and "15 july 2026" in joined
    for term in ("pib.gov.in", "rbi.org.in", "mea.gov.in", "forumias.com", "insightsonindia.com", "drishtiias.com", "visionias.in"):
        assert term in joined


def test_raw_zero_results_are_explained(tmp_path):
    class Web:
        provider_name = "test_provider"
        def validate_configuration(self, **_kwargs): pass
        def search(self, _query): return {"chunks": [], "raw_results": 0, "zero_result_reason": "no search matches"}
    service, _ = setup(tmp_path); service.web = Web()
    result = asyncio.run(service.collect_for_date(date(2026, 7, 15), queries=["nothing"]));
    assert result["raw_results"] == 0 and result["zero_result_reason"] == "no search matches"


def test_direct_url_allowlist_and_extraction(monkeypatch):
    web = WebSearch(cache=SimpleNamespace())
    monkeypatch.setattr(web, "_fetch_approved", lambda candidate, *_args: (trusted_chunk(url=candidate["url"]), None))
    assert len(web.fetch_url("https://rbi.org.in/story", "RBI")["chunks"]) == 1
    rejected = web.fetch_url("https://example.com/story", "story")
    assert rejected["chunks"] == [] and rejected["rejected_domains"] == 1


def test_extraction_failure_does_not_stop_remaining_sources_and_success_is_summarized(tmp_path):
    class Web:
        provider_name = "test_provider"
        def validate_configuration(self, **_kwargs): pass
        def search(self, query):
            chunks = [] if query == "bad" else [trusted_chunk(url="https://rbi.org.in/success")]
            return {"chunks": chunks, "raw_results": 1, "extraction_attempts": 1,
                "extraction_successes": len(chunks), "zero_result_reason": None}
    service, _ = setup(tmp_path); service.web = Web()
    result = asyncio.run(service.collect_for_date(date(2026, 7, 15), queries=["bad", "good"]))
    assert result["extraction_failures"] == 1 and result["accepted"] == 1
    assert service.list_articles()[0][0].status == "active"


def test_homepage_and_index_rejected_before_summarization(tmp_path):
    class CountingLlm(SummaryLlm):
        calls = 0
        async def generate(self, **kwargs): self.calls += 1; return await super().generate(**kwargs)
    llm = CountingLlm(); service = CurrentAffairsService(db_path=str(tmp_path/"quality.sqlite3"), llm=llm, indexer=lambda *_: None)
    homepage = trusted_chunk(url="https://www.rbi.org.in/")
    index = trusted_chunk(url="https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx")
    assert asyncio.run(service.ingest_chunk(homepage)).status == "rejected"
    assert asyncio.run(service.ingest_chunk(index)).status == "rejected"
    assert llm.calls == 0


def test_article_quality_scoring_and_article_ranks_above_homepage():
    article = trusted_chunk(publication_date="2026-07-15")
    quality = WebSearch.article_quality(article)
    assert quality["is_article"] and quality["quality_score"] >= .75
    homepage = {"url": "https://www.rbi.org.in/", "title": "Home - Reserve Bank of India"}
    result = {"url": "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=60001", "title": "RBI policy update"}
    assert WebSearch._candidate_rank(result, "RBI policy update 15 July 2026") > WebSearch._candidate_rank(homepage, "RBI policy update 15 July 2026")
    assert WebSearch.page_type("https://insightsonindia.com/2026/07/16/upsc-editorials-quiz-16-july-2026/") == "index"
    assert WebSearch.page_type("https://example.gov.in/mains-answer-writing-practice/") == "index"


def test_optional_summary_fields_may_be_empty_and_fenced_extra_text_parses():
    raw = 'Result follows:\n```json\n{"what_happened":"RBI published an official monetary policy update.","prelims_facts":[],"mains_relevance":[],"subject":"Economy","topic":"Monetary Policy","importance_level":"medium"}\n```\nDone.'
    summary = CurrentAffairsService._parse_summary(raw)
    assert summary.background == "" and summary.prelims_facts == [] and summary.mains_relevance == []


def test_malformed_json_gets_one_safe_structural_repair():
    raw = '{"what_happened":"RBI published an official monetary policy update.","importance_level":"medium",}'
    assert CurrentAffairsService._parse_summary(raw).what_happened.startswith("RBI published")


def test_parser_normalizes_optional_empty_array_and_fact_objects():
    raw = json.dumps({"what_happened": "RBI published an official monetary policy update.",
        "background": [], "prelims_facts": [{"fact": "RBI conducts monetary policy."}],
        "importance_level": "medium"})
    summary = CurrentAffairsService._parse_summary(raw)
    assert summary.background == "" and summary.prelims_facts == ["RBI conducts monetary policy."]


def test_unsupported_factual_summary_is_rejected(tmp_path):
    class UnsupportedLlm:
        async def generate(self, **_kwargs):
            return json.dumps({"what_happened": "RBI raised the repo rate to 99 percent in the official update.",
                "importance_level": "high"})
    service = CurrentAffairsService(db_path=str(tmp_path/"unsupported.sqlite3"), llm=UnsupportedLlm(), indexer=lambda *_: None)
    assert asyncio.run(service.ingest_chunk(trusted_chunk())).status == "rejected"
    with get_session_factory(str(tmp_path/"unsupported.sqlite3"))() as session:
        assert session.scalar(select(func.count()).select_from(CurrentAffairsArticle)) == 0


def test_indexing_failure_does_not_commit_accepted_article(tmp_path):
    db = str(tmp_path / "index-failure.sqlite3")
    service = CurrentAffairsService(db_path=db, llm=SummaryLlm(), indexer=lambda *_: (_ for _ in ()).throw(RuntimeError("index unavailable")))
    row = asyncio.run(service.ingest_chunk(trusted_chunk()))
    assert row.status == "rejected" and row.diagnostic_reason == "embedding_indexing_failure"
    with get_session_factory(db)() as session:
        assert session.scalar(select(func.count()).select_from(CurrentAffairsArticle)) == 0


def test_feed_discovery_returns_approved_article_metadata(monkeypatch):
    rss = """<rss><channel><item><title>RBI Policy Statement</title><link>https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=60774</link><pubDate>Wed, 15 Jul 2026 10:00:00 GMT</pubDate></item></channel></rss>"""
    response = SimpleNamespace(text=rss, raise_for_status=lambda: None)
    monkeypatch.setattr("src.search.web_search.requests.get", lambda *args, **kwargs: response)
    result = WebSearch(cache=SimpleNamespace()).discover_feeds()
    assert result["candidates"]
    candidate = result["candidates"][0]
    assert candidate["discovery_method"] == "rss_atom" and candidate["title"] == "RBI Policy Statement"


def test_source_listing_discovery_prefers_article_identifiers(monkeypatch):
    html = '''<a href="/">RBI Home</a><a href="/Scripts/BS_PressReleaseDisplay.aspx">Press release archive</a><a href="/Scripts/BS_PressReleaseDisplay.aspx?prid=60774">Directions issued to Bhavani Sahakari Bank</a>'''
    response = SimpleNamespace(text=html, url="https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx", raise_for_status=lambda: None)
    monkeypatch.setattr("src.search.web_search.requests.get", lambda *args, **kwargs: response)
    result = WebSearch(cache=SimpleNamespace()).discover_listings()
    assert len(result["candidates"]) == 1  # identical canonical articles from listings are deduplicated
    assert all(item["discovery_method"] == "source_listing" and "prid=60774" in item["url"] for item in result["candidates"])


def test_source_specific_extraction_and_article_url_ranking(monkeypatch):
    paragraph = "The Reserve Bank of India published an official policy decision affecting regulated institutions, liquidity, inflation management, financial stability, and economic conditions. "
    html = f'''<html><head><meta property="og:title" content="RBI publishes monetary policy decision"><meta property="article:published_time" content="2026-07-15"><link rel="canonical" href="https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=60774"></head><body><div class="article-content"><p>{paragraph}</p><p>{paragraph}Further official details were provided.</p><p>{paragraph}Implementation follows the published framework.</p></div></body></html>'''
    response = SimpleNamespace(text=html, url="https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=60774", status_code=200, raise_for_status=lambda: None)
    monkeypatch.setattr("src.search.web_search.requests.get", lambda *args, **kwargs: response)
    found = WebSearch(cache=SimpleNamespace()).fetch_candidate({"url": response.url, "title": "RBI policy", "snippet": "", "discovery_method": "rss_atom"}, "RBI monetary policy")
    assert found["chunks"][0]["extraction_adapter"] == "source_specific"
    assert found["chunks"][0]["source_title"] == "RBI publishes monetary policy decision"
    article = {"url": response.url, "title": "RBI policy", "publication_date": "2026-07-15", "discovery_method": "rss_atom"}
    assert WebSearch._candidate_rank(article, "RBI policy") > WebSearch._candidate_rank({"url": "https://rbi.org.in/", "title": "RBI"}, "RBI policy")


def test_structured_rejection_breakdown_is_returned(tmp_path):
    class Web:
        provider_name = "test"
        def validate_configuration(self, **kwargs): pass
        def search(self, query): return {"chunks": [], "raw_results": 2, "source_progress": [
            {"url": "https://bad.example", "status": "rejected", "rejection_code": "unapproved_domain"},
            {"url": "https://rbi.org.in/", "status": "rejected", "rejection_code": "homepage_index_archive_search_page"}]}
    service, _ = setup(tmp_path); service.web = Web()
    result = asyncio.run(service.collect_for_date(date.today(), queries=["test"]))
    assert result["rejection_breakdown"]["homepage_index_archive_search_page"] == 1
    assert result["rejection_breakdown"]["unapproved_domain"] == 1
    assert result["rejection_breakdown"]["embedding_indexing_failure"] == 0


def test_rejected_page_does_not_stop_valid_article_and_brief_generates(tmp_path):
    class Web:
        provider_name = "test_provider"
        def validate_configuration(self, **_kwargs): pass
        def search(self, _query): return {"chunks": [trusted_chunk(url="https://rbi.org.in/"), trusted_chunk(url="https://rbi.org.in/article")], "raw_results": 2}
    service, _ = setup(tmp_path); service.web = Web()
    result = asyncio.run(service.collect_for_date(date.today(), queries=["RBI"], generate_brief=True))
    assert result["accepted"] == 1 and result["rejected"] == 1 and result["daily_brief"] == "generated"
