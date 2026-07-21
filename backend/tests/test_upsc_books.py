import pytest
import uuid
from fastapi.testclient import TestClient
from src.main import app
from src.upsc_notes.service import is_valid_pwonlyias_source_url
from src.upsc_books.service import UPSCBooksService, detect_chapters_from_blocks
from src.upsc_books.models import UPSCBook, BookChapter

client = TestClient(app)


def test_pwonlyias_source_url_validation_reused():
    assert is_valid_pwonlyias_source_url("https://pwonlyias.com/books/polity") is True
    assert is_valid_pwonlyias_source_url("https://evilbooks.com") is False
    assert is_valid_pwonlyias_source_url("https://pwonlyias.com.evil.com") is False
    assert is_valid_pwonlyias_source_url("http://127.0.0.1/book.pdf") is False


def test_synthetic_development_ids_absent():
    res = client.get("/upsc-books/book-polity-01")
    assert res.status_code == 404


def test_chapter_detection_only_on_explicit_headings():
    # Uncertain headings produce no chapters
    uncertain_blocks = [
        {"type": "heading", "level": 2, "text": "Introduction"},
        {"type": "paragraph", "text": "Some text."}
    ]
    assert detect_chapters_from_blocks(uncertain_blocks) == []

    # Explicit chapter heading produces chapter
    explicit_blocks = [
        {"type": "heading", "level": 2, "text": "Chapter 1: Preamble", "page_start": 1, "page_end": 10},
        {"type": "paragraph", "text": "Preamble content."}
    ]
    chs = detect_chapters_from_blocks(explicit_blocks)
    assert len(chs) == 1
    assert chs[0]["title"] == "Chapter 1: Preamble"
    assert chs[0]["chapter_order"] == 1


def test_isolated_book_fixture_flow():
    book_id = f"test-book-{uuid.uuid4()}"
    svc = UPSCBooksService()
    with svc.sessions() as session:
        session.add(UPSCBook(
            id=book_id, provider="PWOnlyIAS", title="Isolated Test Book", slug=f"slug-{book_id}",
            normalized_subject="Indian Polity and Governance", official_source_url="https://pwonlyias.com/books/isolated",
            canonical_url=f"https://pwonlyias.com/books/isolated-{book_id}", content_status="ready",
            extraction_status="ready", content_blocks_json=[{"type": "paragraph", "text": "Content"}]
        ))
        session.add(BookChapter(
            id=f"ch-{book_id}", book_id=book_id, title="Chapter 1: Intro", slug="ch-1", chapter_order=1, page_start=1, page_end=5
        ))
        session.commit()

    # Get detail
    res_detail = client.get(f"/upsc-books/{book_id}")
    assert res_detail.status_code == 200
    data = res_detail.json()
    assert data["id"] == book_id
    assert data["provider"] == "PWOnlyIAS"
    assert len(data["chapters"]) == 1
    assert "C:\\" not in str(data) and "/tmp/" not in str(data)

    # Get content
    res_content = client.get(f"/upsc-books/{book_id}/content")
    assert res_content.status_code == 200
    assert len(res_content.json()["content_blocks"]) > 0

    # Save & unsave
    assert client.post(f"/upsc-books/{book_id}/save").status_code == 204
    assert client.get(f"/upsc-books/{book_id}").json()["saved"] is True
    assert client.delete(f"/upsc-books/{book_id}/save").status_code == 204
    assert client.get(f"/upsc-books/{book_id}").json()["saved"] is False

    # Progress
    res_prog = client.post(f"/upsc-books/{book_id}/progress", json={"chapter_id": f"ch-{book_id}", "progress_percentage": 50.0, "last_position": 10})
    assert res_prog.status_code == 200
    assert res_prog.json()["progress_percentage"] == 50.0
