from fastapi import APIRouter, HTTPException, Query

from src.schemas.video import VideoRecommendationResponse, VideoResponse
from src.video.manager import VideoRecommendationService

router = APIRouter(); service = VideoRecommendationService()

@router.get("", response_model=list[VideoResponse])
def list_videos(subject: str | None = None, topic: str | None = None, language: str | None = None,
                difficulty: str | None = None, max_duration_seconds: int | None = Query(default=None, gt=0)):
    try: return service.list_videos(subject=subject, topic=topic, language=language, difficulty=difficulty, max_duration_seconds=max_duration_seconds)
    except ValueError as error: raise HTTPException(status_code=422, detail=str(error)) from error

@router.get("/recommendations", response_model=list[VideoRecommendationResponse])
def recommendations(subject: str | None = None, topic: str | None = None, language: str | None = None,
                    difficulty: str | None = None, max_duration_seconds: int | None = Query(default=None, gt=0),
                    preferred_content_type: str | None = None, explicit_request: bool = False,
                    mastery_score: float | None = None, forgetting_risk: float | None = None, repeated_mistakes: int = 0):
    try: return service.recommend(subject=subject, topic=topic, language=language, difficulty=difficulty,
        max_duration_seconds=max_duration_seconds, preferred_content_type=preferred_content_type,
        explicit_request=explicit_request, mastery_score=mastery_score, forgetting_risk=forgetting_risk,
        repeated_mistakes=repeated_mistakes)
    except ValueError as error: raise HTTPException(status_code=422, detail=str(error)) from error

@router.get("/{video_id}", response_model=VideoResponse)
def get_video(video_id: str):
    row = service.get_video(video_id)
    if not row or not row.active or not row.verified: raise HTTPException(status_code=404, detail="Trusted video not found")
    return row

@router.post("/{video_id}/open", response_model=VideoResponse)
def open_video(video_id: str):
    row = service.open_video(video_id)
    if not row: raise HTTPException(status_code=404, detail="Trusted video not found")
    return row

@router.post("/{video_id}/dismiss", response_model=VideoResponse)
def dismiss_video(video_id: str):
    row = service.dismiss_video(video_id)
    if not row: raise HTTPException(status_code=404, detail="Trusted video not found")
    return row
