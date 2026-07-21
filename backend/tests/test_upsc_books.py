import pytest
import uuid
from fastapi.testclient import TestClient
from src.main import app
from src.upsc_notes.service import is_valid_pwonlyias_source_url
from src.upsc_books.service import UPSCBooksService, detect_chapters_from_blocks
from src.upsc_books.models import UPSCBook, BookChapter

client = TestClient(app)


def test_isolated_test_book_and_synthetic_ids_excluded():
    svc = UPSCBooksService()
    with svc.sessions() as session:
        session.add(UPSCBook(
            id="test-isolated-001", provider="PWOnlyIAS", title="Isolated Test Book", slug="isolated-test-book",
            normalized_subject="Indian Polity and Governance", official_source_url="https://pwonlyias.com/test",
            canonical_url="https://pwonlyias.com/test-isolated-001"
        ))
        session.commit()

    res = client.get("/upsc-books")
    assert res.status_code == 200
    data = res.json()
    assert not any("Isolated Test Book" in b["title"] for b in data)
    assert not any(b["id"].startswith("test-") for b in data)


def test_import_from_official_source_page_validates_domain():
    svc = UPSCBooksService()
    with pytest.raises(ValueError, match="PWOnlyIAS"):
        svc.import_from_official_source_page("https://evilbooks.com/book-page")


def test_subject_filter_and_zero_result_behavior():
    svc = UPSCBooksService()
    book_id = f"real-book-{uuid.uuid4()}"
    with svc.sessions() as session:
        session.add(UPSCBook(
            id=book_id, provider="PWOnlyIAS", title="Real Polity Reference Book", slug=f"slug-{book_id}",
            normalized_subject="Indian Polity and Governance", official_source_url="https://pwonlyias.com/books/polity-real",
            canonical_url=f"https://pwonlyias.com/books/polity-real-{book_id}", content_status="ready",
            extraction_status="ready", content_blocks_json=[{"type": "paragraph", "text": "Polity content"}]
        ))
        session.commit()

    # Query matching subject
    res_match = client.get("/upsc-books?subject=Indian%20Polity%20and%20Governance")
    assert res_match.status_code == 200
    books_polity = res_match.json()
    assert any(b["id"] == book_id for b in books_polity)

    # Query zero-result subject
    res_empty = client.get("/upsc-books?subject=Ethics")
    assert res_empty.status_code == 200
    assert res_empty.json() == []


def test_chapter_detection_only_on_explicit_headings():
    uncertain_blocks = [
        {"type": "heading", "level": 2, "text": "Overview"},
        {"type": "paragraph", "text": "Text"}
    ]
    assert detect_chapters_from_blocks(uncertain_blocks) == []

    explicit_blocks = [
        {"type": "heading", "level": 2, "text": "Chapter 1: Constitutional Pillars", "page_start": 1, "page_end": 15}
    ]
    chs = detect_chapters_from_blocks(explicit_blocks)
    assert len(chs) == 1
    assert chs[0]["title"] == "Chapter 1: Constitutional Pillars"


def test_no_local_paths_exposed_in_api():
    res = client.get("/upsc-books")
    assert res.status_code == 200
    txt = str(res.json())
    assert "C:\\" not in txt and "/tmp/" not in txt
