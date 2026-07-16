import asyncio
from datetime import date, datetime, timezone

from src.activity.manager import ActivityManager
from src.current_affairs.models import CurrentAffairsArticle
from src.current_affairs.personalization import PersonalizedCurrentAffairsService, normalized_title, title_similarity
from src.current_affairs.service import CurrentAffairsService
from src.current_affairs.source_policy import SOURCE_ADAPTERS, controlled_queries, source_adapter
from src.memory.storage import get_session_factory
from src.profile.manager import ProfileManager
from scripts import run_daily_current_affairs


def add_article(db, identifier, title, url, *, topic="Monetary Policy", importance="high"):
    factory = get_session_factory(str(db))
    with factory() as session:
        session.add(CurrentAffairsArticle(id=identifier, title=title, summary="Short original grounded summary with citation.",
            source_title=title, publisher=source_adapter(url).name, source_url=url, publication_date=date.today(),
            retrieved_at=datetime.now(timezone.utc), subject="Economy", topic=topic, syllabus_tags_json=["GS III"],
            importance_level=importance, relevance_prelims="RBI is India's central bank.",
            relevance_mains="Discuss inflation, growth, institutions, challenges, and policy trade-offs.",
            content_hash=f"hash-{identifier}", status="active"))
        session.commit()


def test_controlled_source_hierarchy_and_queries():
    tiers = {item.tier for item in SOURCE_ADAPTERS}
    assert {"primary", "daily_analysis", "mains_editorial", "monthly_revision"} <= tiers
    assert source_adapter("https://www.rbi.org.in/policy").tier == "primary"
    assert source_adapter("https://forumias.com/blog/9-pm-brief").tier == "daily_analysis"
    joined = " ".join(controlled_queries("16 July 2026"))
    for domain in ("pib.gov.in", "rbi.org.in", "mea.gov.in", "forumias.com", "insightsonindia.com", "drishtiias.com", "iasscore.in", "visionias.in"):
        assert domain in joined


def test_normalized_title_and_topic_similarity_group_duplicate_issue(tmp_path):
    db = tmp_path / "personalized.sqlite3"
    add_article(db, "official", "RBI announces monetary policy update", "https://rbi.org.in/policy-1")
    add_article(db, "analysis", "Monetary Policy Update: RBI announcement", "https://forumias.com/blog/policy-analysis")
    service = PersonalizedCurrentAffairsService(db_path=str(db))
    feed = service.feed(date_value=date.today())
    assert normalized_title("The RBI Update") == "rbi"
    assert title_similarity("RBI announces monetary policy update", "Monetary Policy Update RBI announcement") >= .5
    assert len(feed["issues"]) == 1
    assert feed["issues"][0]["source_tier"] == "primary"
    assert {item["tier"] for item in feed["issues"][0]["sources"]} == {"primary", "daily_analysis"}


def test_preferences_mode_weakness_and_saved_story_affect_feed_without_mastery(tmp_path):
    db = tmp_path / "ranking.sqlite3"; add_article(db, "a1", "RBI monetary policy", "https://rbi.org.in/a1")
    profiles = ProfileManager(str(db)); profiles.update({"preferred_language": "hindi", "preferred_depth": "detailed", "preferred_format": "structured"})
    activity = ActivityManager(str(db)); activity.record_event("question_asked", datetime.now(timezone.utc), subject="Economy", topic="Monetary Policy", metadata_json={"mode": "mains"})
    current = CurrentAffairsService(db_path=str(db), activity=activity, llm=object(), indexer=lambda *_: None)
    current.save("a1")
    feed = PersonalizedCurrentAffairsService(db_path=str(db), current_affairs=current, profiles=profiles).feed()
    assert (feed["effective_language"], feed["effective_depth"], feed["effective_format"], feed["exam_mode"]) == ("hindi", "detailed", "structured", "mains")
    assert feed["saved_stories"] and any("Previously saved" in reason for reason in feed["issues"][0]["reasons"])


def test_reindex_active_is_idempotent_upsert_boundary(tmp_path):
    db = tmp_path / "reindex.sqlite3"; add_article(db, "a1", "RBI policy", "https://rbi.org.in/a1")
    calls = []
    service = CurrentAffairsService(db_path=str(db), llm=object(), indexer=lambda article_id, chunks: calls.append(article_id))
    assert service.reindex_active()["indexed"] == 1
    assert service.reindex_active()["indexed"] == 1 and calls == ["a1", "a1"]


def test_daily_runner_skips_overlapping_run(tmp_path, monkeypatch):
    lock = tmp_path / "daily.lock"; lock.write_text("active", encoding="utf-8")
    monkeypatch.setattr(run_daily_current_affairs, "LOCK", lock)
    assert asyncio.run(run_daily_current_affairs.run())["status"] == "skipped"
