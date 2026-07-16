from fastapi.testclient import TestClient

from src.activity.manager import ActivityManager
from src.api.routes import pdf
from src.main import app


def test_successful_pdf_upload_records_event(tmp_path, monkeypatch):
    store = ActivityManager(str(tmp_path / "activity.sqlite3"))
    monkeypatch.setattr(pdf, "activity_manager", store)

    async def successful_upload(file):
        return {"document_id": "document-1", "user_id": "user_001", "status": "processed"}

    monkeypatch.setattr(pdf.DocumentManager, "create_document", successful_upload)
    response = TestClient(app).post(
        "/pdf/upload", files={"file": ("notes.pdf", b"%PDF-test", "application/pdf")}
    )
    assert response.status_code == 200
    events = store.list_events()
    assert [event.event_type for event in events] == ["pdf_uploaded"]
    assert events[0].metadata_json == {"document_id": "document-1", "success": True}


def test_failed_pdf_upload_does_not_record_event(tmp_path, monkeypatch):
    store = ActivityManager(str(tmp_path / "activity.sqlite3"))
    monkeypatch.setattr(pdf, "activity_manager", store)

    async def failed_upload(file):
        raise RuntimeError("processing failed")

    monkeypatch.setattr(pdf.DocumentManager, "create_document", failed_upload)
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post(
        "/pdf/upload", files={"file": ("notes.pdf", b"bad", "application/pdf")}
    ).status_code == 500
    assert store.list_events() == []
