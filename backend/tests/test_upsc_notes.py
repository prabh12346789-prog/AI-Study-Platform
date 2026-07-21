import pytest
import uuid
from fastapi.testclient import TestClient
from src.main import app
from src.upsc_notes.service import UPSCNotesService, normalize_subject
from src.upsc_notes.models import UPSCNote

client = TestClient(app)


def test_subject_normalization():
    assert normalize_subject("Polity") == "Indian Polity and Governance"
    assert normalize_subject("Economy") == "Indian Economy"
    assert normalize_subject("Environment & Ecology") == "Environment and Ecology"
    assert normalize_subject("Science & Tech") == "Science and Technology"
    assert normalize_subject("IR") == "International Relations"
    assert normalize_subject("Unknown Custom Topic") == "Unknown Custom Topic"


def test_html_block_extraction():
    raw_text = "# Main Title\n\nParagraph text.\n\n- Bullet 1\n- Bullet 2\n\n1. Step 1\n2. Step 2"
    blocks = UPSCNotesService.extract_html_blocks(raw_text)
    assert len(blocks) >= 3
    assert blocks[0]["type"] == "heading"
    assert blocks[1]["type"] == "paragraph"
    assert blocks[2]["type"] == "bullet_list"
    assert len(blocks[2]["items"]) == 2


def test_get_subjects_endpoint():
    res = client.get("/upsc-notes/subjects")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert any(s["subject"] == "Indian Polity and Governance" for s in data)


def test_get_notes_list_endpoint():
    res = client.get("/upsc-notes")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    for item in data:
        assert item["provider"] == "PWOnlyIAS"
        assert "official_source_url" in item
        assert "C:\\" not in str(item)


def test_get_note_content_endpoint():
    res = client.get("/upsc-notes/note-polity-01/content")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "note-polity-01"
    assert data["provider"] == "PWOnlyIAS"
    assert data["subject"] == "Indian Polity and Governance"
    assert len(data["content_blocks"]) > 0
    assert "C:\\" not in str(data) and "/tmp/" not in str(data)


def test_save_and_unsave_note_endpoint():
    res_save = client.post("/upsc-notes/note-polity-01/save")
    assert res_save.status_code == 204

    res_check = client.get("/upsc-notes/note-polity-01")
    assert res_check.status_code == 200
    assert res_check.json()["saved"] is True

    res_unsave = client.delete("/upsc-notes/note-polity-01/save")
    assert res_unsave.status_code == 204

    res_check2 = client.get("/upsc-notes/note-polity-01")
    assert res_check2.json()["saved"] is False


def test_update_reading_progress_endpoint():
    note_id = f"test-prog-{uuid.uuid4()}"
    from src.upsc_notes.service import UPSCNotesService
    from src.upsc_notes.models import UPSCNote
    svc = UPSCNotesService()
    with svc.sessions() as session:
        session.add(UPSCNote(
            id=note_id, title="Prog Test", slug=f"prog-{note_id}", normalized_subject="History",
            topic="Test", official_source_url="https://pwonlyias.com/test", canonical_url=f"https://pwonlyias.com/test-{note_id}"
        ))
        session.commit()

    res = client.post(f"/upsc-notes/{note_id}/progress", json={"progress_percentage": 45.5, "last_position": 2})
    assert res.status_code == 200
    assert res.json()["progress_percentage"] == 45.5

    res_check = client.get(f"/upsc-notes/{note_id}")
    assert res_check.json()["progress_percentage"] == 45.5


def test_source_url_validation():
    from src.upsc_notes.service import is_valid_pwonlyias_source_url
    assert is_valid_pwonlyias_source_url("https://pwonlyias.com/udaan/") is True
    assert is_valid_pwonlyias_source_url("https://www.pwonlyias.com/books/") is True
    assert is_valid_pwonlyias_source_url("https://notes.pwonlyias.com/sample") is True

    # Rejections
    assert is_valid_pwonlyias_source_url("https://evilpwonlyias.com") is False
    assert is_valid_pwonlyias_source_url("https://pwonlyias.com.evil.com") is False
    assert is_valid_pwonlyias_source_url("https://pwonlyias-com.example.com") is False
    assert is_valid_pwonlyias_source_url("https://user:pass@pwonlyias.com") is False
    assert is_valid_pwonlyias_source_url("http://localhost/notes") is False
    assert is_valid_pwonlyias_source_url("http://127.0.0.1/notes") is False
    assert is_valid_pwonlyias_source_url("http://192.168.1.1/notes") is False
    assert is_valid_pwonlyias_source_url("javascript:alert(1)") is False
    assert is_valid_pwonlyias_source_url("file:///C:/secret.txt") is False


def test_pdf_validation_and_signature():
    from src.upsc_notes.service import extract_pdf_blocks

    # Non-PDF or HTML content rejected
    blocks, page_count, status = extract_pdf_blocks(b"<html><body>Not a PDF</body></html>")
    assert status == "failed"
    assert blocks == []

    # Corrupt PDF signature
    blocks, page_count, status = extract_pdf_blocks(b"random corrupt data")
    assert status == "failed"

    # Oversized payload
    blocks, page_count, status = extract_pdf_blocks(b"%PDF-1.4 " + b"X" * (51 * 1024 * 1024), max_size_mb=50)
    assert status == "failed"

