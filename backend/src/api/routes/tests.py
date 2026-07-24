from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from src.tests_engine.service import (
    UnifiedTestsService,
    PrelimsQuizCreate,
    MainsQuestionCreate,
    MainsAnswerSubmit
)

router = APIRouter(prefix="/tests", tags=["tests"])

def get_service():
    return UnifiedTestsService()

@router.get("/sources")
def get_sources_availability(svc: UnifiedTestsService = Depends(get_service)):
    return svc.get_sources_availability()

@router.post("/prelims/generate")
def generate_prelims(payload: PrelimsQuizCreate, svc: UnifiedTestsService = Depends(get_service)):
    try:
        return svc.generate_prelims_quiz(payload)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err

class PrelimsSubmitPayload(BaseModel):
    questions: list[dict]
    answers: dict[str, str]

@router.post("/prelims/{session_id}/submit")
def submit_prelims(session_id: str, payload: PrelimsSubmitPayload, svc: UnifiedTestsService = Depends(get_service)):
    try:
        return svc.submit_prelims_quiz(session_id, payload.questions, payload.answers)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err

@router.post("/mains/generate")
def generate_mains(payload: MainsQuestionCreate, svc: UnifiedTestsService = Depends(get_service)):
    try:
        return svc.generate_mains_question(payload)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err

@router.post("/mains/submit")
def submit_mains(payload: MainsAnswerSubmit, svc: UnifiedTestsService = Depends(get_service)):
    try:
        return svc.evaluate_mains_answer(payload)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
