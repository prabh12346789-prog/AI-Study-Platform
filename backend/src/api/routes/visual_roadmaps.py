from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse

from src.schemas.visual_roadmap import RoadmapStructure, VisualRoadmapCreate
from src.schemas.roadmap_quiz import QuizCreate, QuizResponse, QuizResult, QuizSubmission
from src.visual_roadmap.quiz_service import RoadmapQuizService
from src.visual_roadmap.service import InsufficientContextError, RoadmapGenerationError, VisualRoadmapService

router = APIRouter()


def service(): return VisualRoadmapService()


def response(row):
    return {
        "id": row.id, "status": row.status, "title": row.title, "subject": row.subject, "topic": row.topic,
        "visual_type": row.visual_type, "language": row.language, "conversation_id": row.conversation_id,
        "structure": RoadmapStructure.model_validate(row.structure_json), "sources": row.source_metadata_json,
        "svg_url": f"/visual-roadmaps/{row.id}/svg", "created_at": row.created_at, "updated_at": row.updated_at,
    }


def quiz_response(row):
    return {"id": row.id, "roadmap_id": row.roadmap_id, "difficulty": row.difficulty, "questions": row.questions_json}


@router.post("/{roadmap_id}/quiz", response_model=QuizResponse)
def create_quiz(roadmap_id: str, payload: QuizCreate):
    try: return quiz_response(RoadmapQuizService().generate(roadmap_id, **payload.model_dump()))
    except ValueError as error: raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/{roadmap_id}/quiz", response_model=QuizResponse)
def get_quiz(roadmap_id: str):
    row = RoadmapQuizService().get(roadmap_id)
    if not row: raise HTTPException(status_code=404, detail="Roadmap quiz not found")
    return quiz_response(row)


@router.post("/{roadmap_id}/quiz/submit", response_model=QuizResult)
def submit_quiz(roadmap_id: str, payload: QuizSubmission):
    try: return RoadmapQuizService().submit(roadmap_id, payload.answers)
    except ValueError as error: raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("")
async def create_roadmap(payload: VisualRoadmapCreate):
    try: return response(await service().create(payload))
    except InsufficientContextError as error: raise HTTPException(status_code=422, detail={"code": "insufficient_context", "message": str(error)}) from error
    except RoadmapGenerationError as error: raise HTTPException(status_code=422, detail={
        "code": error.code, "message": str(error), "model": error.model,
        "action": f"ollama pull {error.model}" if error.code == "generation_model_missing" and error.model else None,
    }) from error
    except ValueError as error: raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("")
def list_roadmaps(subject: str | None = None, topic: str | None = None,
                  visual_type: str | None = Query(default=None), language: str | None = None):
    return [response(row) for row in service().list(subject=subject, topic=topic, visual_type=visual_type, language=language)]


@router.get("/{roadmap_id}")
def get_roadmap(roadmap_id: str):
    try: row = service().get(roadmap_id, opened=True)
    except ValueError as error: raise HTTPException(status_code=422, detail=str(error)) from error
    if not row: raise HTTPException(status_code=404, detail="Visual roadmap not found")
    return response(row)


@router.get("/{roadmap_id}/svg")
def get_svg(roadmap_id: str):
    row = service().get(roadmap_id, opened=True)
    if not row: raise HTTPException(status_code=404, detail="Visual roadmap not found")
    return FileResponse(row.svg_path, media_type="image/svg+xml", filename=f"{row.id}-roadmap.svg")


@router.post("/{roadmap_id}/save", status_code=204)
def save_roadmap(roadmap_id: str):
    svc = service(); row = svc.get(roadmap_id)
    if not row: raise HTTPException(status_code=404, detail="Visual roadmap not found")
    svc.activity.record_event("visual_roadmap_saved", datetime.now(timezone.utc), subject=row.subject, topic=row.topic,
        conversation_id=row.conversation_id, metadata_json={"roadmap_id": row.id, "visual_type": row.visual_type, "language": row.language})
    return Response(status_code=204)


@router.delete("/{roadmap_id}", status_code=204)
def delete_roadmap(roadmap_id: str):
    try: deleted = service().delete(roadmap_id)
    except ValueError as error: raise HTTPException(status_code=422, detail=str(error)) from error
    if not deleted: raise HTTPException(status_code=404, detail="Visual roadmap not found")
    return Response(status_code=204)
