from fastapi import APIRouter, HTTPException, Query
from src.mentor.manager import MentorDecisionEngine
from src.mentor.dashboard import MentorDashboardService
from src.schemas.mentor import NextActionResponse, RecommendationResponse, StatusPatch

router = APIRouter(); engine = MentorDecisionEngine()

@router.get("/dashboard")
def dashboard(): return MentorDashboardService(engine).get_dashboard()

@router.get("/actions/next", response_model=NextActionResponse)
def next_action(available_minutes: int | None = Query(default=None, ge=5)): return engine.get_next_action(available_minutes=available_minutes)

@router.get("/actions", response_model=list[RecommendationResponse])
def list_actions(status: str | None = None): return engine.list_actions(status=status)

@router.post("/actions/generate", response_model=list[RecommendationResponse])
def generate(available_minutes: int | None = Query(default=None, ge=5)): return engine.regenerate_actions(available_minutes=available_minutes)

def change(action_id: str, status: str):
    result = engine.update_action_status(action_id, status)
    if not result: raise HTTPException(status_code=404, detail="Recommendation not found")
    return result

@router.patch("/actions/{action_id}", response_model=RecommendationResponse)
def patch_action(action_id: str, payload: StatusPatch): return change(action_id, payload.status)
@router.post("/actions/{action_id}/accept", response_model=RecommendationResponse)
def accept(action_id: str): return change(action_id, "accepted")
@router.post("/actions/{action_id}/complete", response_model=RecommendationResponse)
def complete(action_id: str): return change(action_id, "completed")
@router.post("/actions/{action_id}/skip", response_model=RecommendationResponse)
def skip(action_id: str): return change(action_id, "skipped")
