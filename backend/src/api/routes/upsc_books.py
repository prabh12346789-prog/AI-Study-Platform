from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from src.upsc_books.service import UPSCBooksService

router = APIRouter()


def service():
    return UPSCBooksService()


class BookProgressUpdatePayload(BaseModel):
    chapter_id: str | None = None
    progress_percentage: float = Field(ge=0.0, le=100.0)
    last_position: int = Field(default=0, ge=0)


def book_response(item: dict):
    r = item["book"]
    return {
        "id": r.id,
        "collection_id": r.collection_id,
        "provider": "PWOnlyIAS",
        "title": r.title,
        "slug": r.slug,
        "subject": r.normalized_subject,
        "original_subject": r.original_subject,
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
    items = service().list_books(saved_only=True)
    return [book_response(item) for item in items]


@router.get("")
def list_books(subject: str | None = None, collection_id: str | None = None,
               language: str | None = None, prelims_only: bool = False, mains_only: bool = False,
               search: str | None = None, saved_only: bool = False):
    items = service().list_books(
        subject=subject, collection_id=collection_id, language=language,
        prelims_only=prelims_only, mains_only=mains_only, search=search, saved_only=saved_only
    )
    return [book_response(item) for item in items]


@router.get("/{book_id}")
def get_book(book_id: str):
    info = service().get_book(book_id)
    if not info:
        raise HTTPException(status_code=404, detail="UPSC Book not found")
    resp = book_response(info)
    resp["chapters"] = [{"id": c.id, "title": c.title, "chapter_order": c.chapter_order, "page_start": c.page_start, "page_end": c.page_end} for c in info["chapters"]]
    return resp


@router.get("/{book_id}/content")
def get_book_content(book_id: str, chapter_id: str | None = None):
    content = service().get_book_content(book_id, chapter_id=chapter_id)
    if not content:
        raise HTTPException(status_code=404, detail="UPSC Book content not found")
    return content


@router.post("/{book_id}/save", status_code=204)
def save_book(book_id: str):
    if not service().save_book(book_id):
        raise HTTPException(status_code=404, detail="UPSC Book not found")
    return Response(status_code=204)


@router.delete("/{book_id}/save", status_code=204)
def unsave_book(book_id: str):
    if not service().unsave_book(book_id):
        raise HTTPException(status_code=404, detail="Saved book not found")
    return Response(status_code=204)


@router.post("/{book_id}/progress")
@router.put("/{book_id}/progress")
def update_progress(book_id: str, payload: BookProgressUpdatePayload):
    return service().update_progress(book_id, chapter_id=payload.chapter_id, progress_percentage=payload.progress_percentage, last_position=payload.last_position)
