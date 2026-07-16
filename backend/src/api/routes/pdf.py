from fastapi import APIRouter, UploadFile, File
from datetime import datetime, timezone

from src.activity.manager import ActivityManager
from src.rag.manager import DocumentManager
from src.schemas.pdf import PdfDocumentResponse

router = APIRouter()
activity_manager = ActivityManager()


@router.get("/documents", response_model=list[PdfDocumentResponse])
def list_pdf_documents():
    return DocumentManager.list_documents()


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):

    metadata = await DocumentManager.create_document(file)
    activity_manager.record_event(
        "pdf_uploaded",
        datetime.now(timezone.utc),
        user_id=metadata.get("user_id", "user_001"),
        metadata_json={
            "document_id": metadata.get("document_id"),
            "success": True,
        },
    )

    return metadata
