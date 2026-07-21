from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from src.upsc_notes.service import UPSCNotesService

router = APIRouter()


def service():
    return UPSCNotesService()


class ProgressUpdatePayload(BaseModel):
    progress_percentage: float = Field(ge=0.0, le=100.0)
    last_position: int = Field(default=0, ge=0)


def note_response(item: dict):
    r = item["note"]
    return {
        "id": r.id,
        "collection_id": r.collection_id,
        "provider": "PWOnlyIAS",
        "title": r.title,
        "slug": r.slug,
        "subject": r.normalized_subject,
        "original_subject": r.original_subject,
        "topic": r.topic,
        "description": r.description,
        "language": r.language,
        "prelims_relevant": r.prelims_relevant,
        "mains_relevant": r.mains_relevant,
        "official_source_url": r.official_source_url,
        "official_pdf_url": r.official_pdf_url,
        "publication_year": r.publication_year,
        "content_status": r.content_status,
        "extraction_status": r.extraction_status,
        "page_count": r.page_count,
        "estimated_reading_minutes": r.estimated_reading_minutes,
        "saved": item["saved"],
        "progress_percentage": item["progress_percentage"],
        "last_opened_at": item.get("last_opened_at")
    }


@router.get("/subjects")
def list_subjects():
    return service().list_subjects()


@router.get("/collections")
def list_collections(subject: str | None = None, language: str | None = None,
                     exam_stage: str | None = None, search: str | None = None):
    return service().list_collections(subject=subject, language=language, exam_stage=exam_stage, search=search)


@router.get("/saved")
def list_saved():
    items = service().list_notes(saved_only=True)
    return [note_response(item) for item in items]


@router.get("")
def list_notes(subject: str | None = None, collection_id: str | None = None, topic: str | None = None,
               language: str | None = None, prelims_only: bool = False, mains_only: bool = False,
               search: str | None = None, saved_only: bool = False):
    items = service().list_notes(
        subject=subject, collection_id=collection_id, topic=topic, language=language,
        prelims_only=prelims_only, mains_only=mains_only, search=search, saved_only=saved_only
    )
    return [note_response(item) for item in items]


@router.get("/{note_id}")
def get_note(note_id: str):
    info = service().get_note(note_id)
    if not info:
        raise HTTPException(status_code=404, detail="UPSC Note not found")
    return note_response(info)


@router.get("/{note_id}/content")
def get_note_content(note_id: str):
    content = service().get_note_content(note_id)
    if not content:
        raise HTTPException(status_code=404, detail="UPSC Note content not found")
    return content


@router.post("/{note_id}/save", status_code=204)
def save_note(note_id: str):
    if not service().save_note(note_id):
        raise HTTPException(status_code=404, detail="UPSC Note not found")
    return Response(status_code=204)


@router.delete("/{note_id}/save", status_code=204)
def unsave_note(note_id: str):
    if not service().unsave_note(note_id):
        raise HTTPException(status_code=404, detail="Saved note not found")
    return Response(status_code=204)


@router.post("/{note_id}/progress")
@router.put("/{note_id}/progress")
def update_progress(note_id: str, payload: ProgressUpdatePayload):
    return service().update_progress(note_id, progress_percentage=payload.progress_percentage, last_position=payload.last_position)
