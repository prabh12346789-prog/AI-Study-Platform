from fastapi import APIRouter, HTTPException, Response, status

from src.mastery.manager import MasteryManager
from src.schemas.mastery import EvidenceCreate, MasteryOverview, RiskLevel, TopicMasteryResponse

router = APIRouter()
manager = MasteryManager()


@router.post("/evidence", response_model=TopicMasteryResponse, status_code=status.HTTP_201_CREATED)
def record_evidence(payload: EvidenceCreate):
    values = payload.model_dump(); values["metadata_json"] = values.pop("metadata")
    try: return manager.record_evidence(**values)
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/topics", response_model=list[TopicMasteryResponse])
def list_topics(subject: str | None = None, topic: str | None = None,
                risk_level: RiskLevel | None = None, weak_only: bool = False):
    return manager.list_topic_mastery(subject=subject, topic=topic, risk_level=risk_level, weak_only=weak_only)


@router.get("/overview", response_model=MasteryOverview)
def overview():
    return manager.get_mastery_overview()


@router.get("/topics/{mastery_id}", response_model=TopicMasteryResponse)
def get_topic(mastery_id: str):
    result = manager.get_topic_mastery(mastery_id)
    if not result: raise HTTPException(status_code=404, detail="Topic mastery not found")
    return result


@router.post("/topics/{mastery_id}/recalculate", response_model=TopicMasteryResponse)
def recalculate(mastery_id: str):
    result = manager.get_topic_mastery(mastery_id)
    if not result: raise HTTPException(status_code=404, detail="Topic mastery not found")
    return manager.recalculate_topic(user_id=result.user_id, subject=result.subject, topic=result.topic)


@router.delete("/topics/{mastery_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(mastery_id: str):
    if not manager.delete_topic_mastery(mastery_id): raise HTTPException(status_code=404, detail="Topic mastery not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
