import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from src.tests_engine.service import (
    UnifiedTestsService,
    PrelimsQuizCreate,
    MainsQuestionCreate,
    MainsAnswerSubmit
)

router = APIRouter(prefix="/tests", tags=["tests"])
log = logging.getLogger(__name__)

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
    except Exception as err:
        log.exception("Prelims quiz generation failed")
        raise HTTPException(
            status_code=503,
            detail="The local quiz model is unavailable or timed out. Confirm Ollama is running, then try again.",
        ) from err

class PrelimsSubmitPayload(BaseModel):
    questions: list[dict]
    answers: dict[str, str]

@router.post("/prelims/{session_id}/submit")
def submit_prelims(session_id: str, payload: PrelimsSubmitPayload, svc: UnifiedTestsService = Depends(get_service)):
    try:
        return svc.submit_prelims_quiz(session_id, payload.questions, payload.answers)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err

@router.post("/current-affairs/{quiz_id}/abandon")
def abandon_current_affairs_quiz(quiz_id: str, svc: UnifiedTestsService = Depends(get_service)):
    try:
        quiz = svc.current_affairs_quizzes.abandon(quiz_id)
        return {"quiz_id": quiz.id, "status": quiz.status, "reason": quiz.invalid_reason}
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err

@router.get("/current-affairs/active")
def active_current_affairs_quiz(svc: UnifiedTestsService = Depends(get_service)):
    quiz = svc.current_affairs_quizzes.active_quiz()
    return {"quiz_id": quiz.id, "status": quiz.status} if quiz else None

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
