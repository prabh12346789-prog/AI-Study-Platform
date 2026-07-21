import pytest
import uuid
import datetime
from fastapi.testclient import TestClient
from src.main import app
from src.current_affairs.service import CurrentAffairsService
from src.current_affairs.models import CurrentAffairsArticle
from src.current_affairs.quiz_service import CurrentAffairsQuizService
from src.schemas.current_affairs_quiz import QuizCreate
from src.core.config import settings

client = TestClient(app)

def test_html_block_extraction():
    text = "# Main Title\n\nThis is a paragraph.\n\n## Section 1\n\n- Point 1\n- Point 2"
    blocks = CurrentAffairsService.extract_html_blocks(text)
    assert len(blocks) >= 3
    assert blocks[0]["type"] == "heading"
    assert blocks[1]["type"] == "paragraph"
    assert blocks[3]["type"] == "bullet_list"
    assert len(blocks[3]["items"]) == 2

def test_reader_api_content_endpoint():
    svc = CurrentAffairsService()
    today = datetime.date.today()
    art_id = f"test-reader-{uuid.uuid4()}"
    with svc.sessions() as session:
        art = CurrentAffairsArticle(
            id=art_id,
            title="PWOnlyIAS Internal Reader Test",
            summary="Testing internal webpage reader content delivery.",
            source_title="PWOnlyIAS Internal Reader",
            publisher="PWOnlyIAS",
            source_url=f"https://pwonlyias.com/test-{art_id}",
            source_type="current_affairs",
            publication_date=today,
            retrieved_at=datetime.datetime.now(datetime.timezone.utc),
            subject="Polity and Governance",
            topic="Constitutional Amendments",
            syllabus_tags_json=["GS-2"],
            importance_level="high",
            relevance_prelims="Key fact 1",
            relevance_mains="Dimension 1",
            content_hash=f"hash-{art_id}",
            status="active",
            extraction_status="ready",
            content_blocks_json=[{"type": "paragraph", "text": "Structured content paragraph."}]
        )
        session.add(art)
        session.commit()

    res = client.get(f"/current-affairs/{art_id}/content")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == art_id
    assert data["provider"] == "PWOnlyIAS"
    assert data["availability"] == "available"
    assert len(data["content_blocks"]) > 0
    assert "C:\\" not in str(data) and "/tmp/" not in str(data)

def test_public_summary_content_mode(monkeypatch):
    monkeypatch.setattr(settings, "CURRENT_AFFAIRS_CONTENT_MODE", "public_summary")
    svc = CurrentAffairsService()
    today = datetime.date.today()
    art_id = f"test-mode-{uuid.uuid4()}"
    with svc.sessions() as session:
        art = CurrentAffairsArticle(
            id=art_id,
            title="PWOnlyIAS Mode Test",
            summary="Grounded summary.",
            source_title="PWOnlyIAS Mode",
            publisher="PWOnlyIAS",
            source_url=f"https://pwonlyias.com/mode-{art_id}",
            source_type="current_affairs",
            publication_date=today,
            retrieved_at=datetime.datetime.now(datetime.timezone.utc),
            subject="Economy",
            topic="Banking Reforms",
            syllabus_tags_json=["GS-3"],
            importance_level="medium",
            relevance_prelims="Fact A",
            relevance_mains="Dimension B",
            content_hash=f"hash-{art_id}",
            status="active",
            extraction_status="ready",
            content_blocks_json=[{"type": "paragraph", "text": "Full text"}]
        )
        session.add(art)
        session.commit()

    data = svc.get_article_content(art_id)
    assert data["content_blocks"][0]["text"] == "Structured Study Summary"

def test_quiz_service_excludes_failed_extractions():
    svc = CurrentAffairsQuizService()
    today = datetime.date.today()
    art_id = f"test-failed-{uuid.uuid4()}"
    with svc.sessions() as session:
        art = CurrentAffairsArticle(
            id=art_id,
            title="PWOnlyIAS Image Only PDF",
            summary="Scanned image PDF.",
            source_title="PWOnlyIAS Scanned PDF",
            publisher="PWOnlyIAS",
            source_url=f"https://pwonlyias.com/scanned-{art_id}",
            source_type="current_affairs",
            publication_date=today,
            retrieved_at=datetime.datetime.now(datetime.timezone.utc),
            subject="Environment and Ecology",
            topic="Forest Conservation",
            syllabus_tags_json=["GS-3"],
            importance_level="high",
            relevance_prelims="Fact",
            relevance_mains="Dimension",
            content_hash=f"hash-{art_id}",
            status="active",
            extraction_status="image_only"
        )
        session.add(art)
        session.commit()

    articles = svc._articles(today, today)
    assert not any(a.id == art_id for a in articles)

def test_backfill_records():
    svc = CurrentAffairsService()
    today = datetime.date.today()
    art_id = f"test-backfill-{uuid.uuid4()}"
    with svc.sessions() as session:
        art = CurrentAffairsArticle(
            id=art_id,
            title="PWOnlyIAS Pending Backfill",
            summary="Summary to backfill.",
            source_title="PWOnlyIAS Pending",
            publisher="PWOnlyIAS",
            source_url=f"https://pwonlyias.com/pending-{art_id}",
            source_type="current_affairs",
            publication_date=today,
            retrieved_at=datetime.datetime.now(datetime.timezone.utc),
            subject="History",
            topic="Freedom Movement",
            syllabus_tags_json=["GS-1"],
            importance_level="high",
            relevance_prelims="Prelims fact",
            relevance_mains="Mains analysis",
            content_hash=f"hash-{art_id}",
            status="active",
            extraction_status="pending",
            content_blocks_json=None
        )
        session.add(art)
        session.commit()

    res = svc.backfill_records(limit=10, dry_run=False)
    assert res["processed"] >= 1

    with svc.sessions() as session:
        updated = session.get(CurrentAffairsArticle, art_id)
        assert updated.extraction_status == "ready"
        assert len(updated.content_blocks_json) > 0
