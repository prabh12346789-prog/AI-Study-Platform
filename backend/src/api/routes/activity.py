from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status

from src.activity.manager import ActivityManager
from src.mastery.manager import MasteryManager
from src.schemas.activity import ActivityEventCreate, ActivityEventResponse, ActivitySummary

router = APIRouter()
store = ActivityManager()
mastery_manager = MasteryManager()


@router.post("/events", response_model=ActivityEventResponse, status_code=status.HTTP_201_CREATED)
def create_event(payload: ActivityEventCreate):
    try:
        values = payload.model_dump()
        values["metadata_json"] = values.pop("metadata")
        event = store.record_event(**values)
        mastery_manager.process_activity_event(event)
        return event
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/events", response_model=list[ActivityEventResponse])
def list_events(
    user_id: str | None = None, conversation_id: str | None = None,
    event_type: str | None = None, subject: str | None = None,
    topic: str | None = None, date_from: datetime | None = None,
    date_to: datetime | None = None, limit: int = Query(default=100, ge=1, le=500),
):
    return store.list_events(
        user_id=user_id, conversation_id=conversation_id, event_type=event_type,
        subject=subject, topic=topic, date_from=date_from, date_to=date_to, limit=limit,
    )


@router.get("/summary", response_model=ActivitySummary)
def activity_summary(
    period: Literal["today", "7d"] = "today",
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    from src.core.config import settings
    if getattr(settings, "REPORT_DEMO_MODE", False):
        now = datetime.now(timezone.utc)
        # Build a 7-day daily breakdown so the Study Progress chart fills up
        daily_breakdown = []
        # Realistic per-day study seconds: varies to look like a real learner
        day_seconds = [4200, 5400, 2700, 6300, 4800, 7200, 5100]
        for i in range(6, -1, -1):
            d = now - timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            daily_breakdown.append({
                "date": date_str,
                "study_seconds": day_seconds[6 - i],
                "event_count": day_seconds[6 - i] // 900
            })
        today_seconds = daily_breakdown[-1]["study_seconds"]
        return {
            "demo_mode": True,
            "total_study_seconds": 35700 if period == "7d" else today_seconds,
            "questions_asked": 24 if period == "7d" else 4,
            "answers_generated": 24 if period == "7d" else 4,
            "pdfs_uploaded": 3 if period == "7d" else 1,
            "subjects_studied": 5 if period == "7d" else 3,
            "top_subject": "Polity",
            "top_topic": "Constitutional Amendments",
            "daily_breakdown": daily_breakdown,
            "subject_breakdown": [
                {"name": "Polity & Governance", "study_seconds": 10800 if period == "7d" else 2160, "event_count": 8 if period == "7d" else 2},
                {"name": "Indian Economy", "study_seconds": 8400 if period == "7d" else 1680, "event_count": 6 if period == "7d" else 1},
                {"name": "Modern History", "study_seconds": 6600 if period == "7d" else 900, "event_count": 5 if period == "7d" else 1},
                {"name": "Environment & Ecology", "study_seconds": 5400 if period == "7d" else 0, "event_count": 4 if period == "7d" else 0},
                {"name": "Ethics & Integrity", "study_seconds": 4500 if period == "7d" else 360, "event_count": 3 if period == "7d" else 0},
            ],
            "topic_breakdown": [
                {"name": "Constitutional Amendments", "study_seconds": 5400 if period == "7d" else 3600, "event_count": 4 if period == "7d" else 2},
                {"name": "Banking Reforms", "study_seconds": 4500 if period == "7d" else 1800, "event_count": 3 if period == "7d" else 1},
                {"name": "Climate Policy", "study_seconds": 3600 if period == "7d" else 900, "event_count": 3 if period == "7d" else 1},
                {"name": "Freedom Movement", "study_seconds": 2700 if period == "7d" else 600, "event_count": 2 if period == "7d" else 1},
            ],
            "recent_events": [
                {
                    "id": "demo-act-evt-1",
                    "user_id": "user_001",
                    "event_type": "study_time_logged",
                    "conversation_id": None,
                    "subject": "Polity",
                    "topic": "Constitutional Amendments",
                    "duration_seconds": 3600,
                    "metadata_json": {},
                    "occurred_at": now,
                    "created_at": now
                },
                {
                    "id": "demo-act-evt-2",
                    "user_id": "user_001",
                    "event_type": "current_affairs_test_completed",
                    "conversation_id": None,
                    "subject": "History",
                    "topic": "Freedom Movement",
                    "duration_seconds": 600,
                    "metadata_json": {"score": 4, "total": 5},
                    "occurred_at": now - timedelta(days=1),
                    "created_at": now - timedelta(days=1)
                },
                {
                    "id": "demo-act-evt-3",
                    "user_id": "user_001",
                    "event_type": "question_asked",
                    "conversation_id": None,
                    "subject": "Economy",
                    "topic": "Banking Reforms",
                    "duration_seconds": None,
                    "metadata_json": {},
                    "occurred_at": now - timedelta(hours=2),
                    "created_at": now - timedelta(hours=2)
                },
                {
                    "id": "demo-act-evt-4",
                    "user_id": "user_001",
                    "event_type": "prelims_test_completed",
                    "conversation_id": None,
                    "subject": "Polity",
                    "topic": "Fundamental Rights",
                    "duration_seconds": 720,
                    "metadata_json": {"score": 7, "total": 10},
                    "occurred_at": now - timedelta(hours=5),
                    "created_at": now - timedelta(hours=5)
                }
            ]
        }

    now = datetime.now(timezone.utc)
    start = date_from
    if start is None:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) if period == "today" else now - timedelta(days=7)
    return store.summarize(date_from=start, date_to=date_to or now)


@router.get("/events/{event_id}", response_model=ActivityEventResponse)
def get_event(event_id: str):
    event = store.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Activity event '{event_id}' not found")
    return event


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: str):
    if not store.delete_event(event_id):
        raise HTTPException(status_code=404, detail=f"Activity event '{event_id}' not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
