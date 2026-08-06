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
    period: Literal["today", "7d", "30d", "90d", "1y", "all"] = "today",
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    now = datetime.now(timezone.utc)
    start = date_from
    if start is None:
        days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365, "all": 36500}
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) if period == "today" else now - timedelta(days=days[period])
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
