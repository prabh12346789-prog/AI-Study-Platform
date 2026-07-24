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
    from src.core.config import settings
    from datetime import datetime, timezone
    if getattr(settings, "REPORT_DEMO_MODE", False):
        demo_topics = [
            {
                "id": "demo-mast-1",
                "user_id": "user_001",
                "subject": "Polity",
                "topic": "Constitutional Amendments",
                "mastery_score": 0.78,
                "forgetting_risk": 0.15,
                "risk_level": "low",
                "confidence_score": 0.9,
                "total_attempts": 10,
                "correct_attempts": 8,
                "incorrect_attempts": 2,
                "revision_count": 3,
                "last_attempt_at": datetime.now(timezone.utc),
                "last_revised_at": datetime.now(timezone.utc),
                "next_revision_at": datetime.now(timezone.utc),
                "explanation_json": ["Strong performance on practice quizzes.", "Regular revisions completed."],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "id": "demo-mast-2",
                "user_id": "user_001",
                "subject": "Ethics",
                "topic": "Attitude & Moral Influence",
                "mastery_score": 0.52,
                "forgetting_risk": 0.65,
                "risk_level": "medium",
                "confidence_score": 0.7,
                "total_attempts": 8,
                "correct_attempts": 4,
                "incorrect_attempts": 4,
                "revision_count": 1,
                "last_attempt_at": datetime.now(timezone.utc),
                "last_revised_at": datetime.now(timezone.utc),
                "next_revision_at": datetime.now(timezone.utc),
                "explanation_json": ["Lower scores on recent practice sessions.", "Needs conceptual reinforcement."],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "id": "demo-mast-3",
                "user_id": "user_001",
                "subject": "Environment",
                "topic": "Climate Change & COP",
                "mastery_score": 0.60,
                "forgetting_risk": 0.82,
                "risk_level": "high",
                "confidence_score": 0.8,
                "total_attempts": 12,
                "correct_attempts": 7,
                "incorrect_attempts": 5,
                "revision_count": 2,
                "last_attempt_at": datetime.now(timezone.utc),
                "last_revised_at": datetime.now(timezone.utc),
                "next_revision_at": datetime.now(timezone.utc),
                "explanation_json": ["High risk of memory decay. Not revised in 5 days."],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        ]
        if subject:
            demo_topics = [t for t in demo_topics if t["subject"] == subject]
        if topic:
            demo_topics = [t for t in demo_topics if t["topic"] == topic]
        if risk_level:
            demo_topics = [t for t in demo_topics if t["risk_level"] == risk_level]
        if weak_only:
            demo_topics = [t for t in demo_topics if t["mastery_score"] < 0.6]
        return demo_topics

    return manager.list_topic_mastery(subject=subject, topic=topic, risk_level=risk_level, weak_only=weak_only)


@router.get("/overview", response_model=MasteryOverview)
def overview():
    from src.core.config import settings
    from datetime import datetime, timezone
    if getattr(settings, "REPORT_DEMO_MODE", False):
        demo_topics = [
            {
                "id": "demo-mast-1",
                "user_id": "user_001",
                "subject": "Polity",
                "topic": "Constitutional Amendments",
                "mastery_score": 0.78,
                "forgetting_risk": 0.15,
                "risk_level": "low",
                "confidence_score": 0.9,
                "total_attempts": 10,
                "correct_attempts": 8,
                "incorrect_attempts": 2,
                "revision_count": 3,
                "last_attempt_at": datetime.now(timezone.utc),
                "last_revised_at": datetime.now(timezone.utc),
                "next_revision_at": datetime.now(timezone.utc),
                "explanation_json": ["Strong performance on practice quizzes.", "Regular revisions completed."],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "id": "demo-mast-2",
                "user_id": "user_001",
                "subject": "Ethics",
                "topic": "Attitude & Moral Influence",
                "mastery_score": 0.52,
                "forgetting_risk": 0.65,
                "risk_level": "medium",
                "confidence_score": 0.7,
                "total_attempts": 8,
                "correct_attempts": 4,
                "incorrect_attempts": 4,
                "revision_count": 1,
                "last_attempt_at": datetime.now(timezone.utc),
                "last_revised_at": datetime.now(timezone.utc),
                "next_revision_at": datetime.now(timezone.utc),
                "explanation_json": ["Lower scores on recent practice sessions.", "Needs conceptual reinforcement."],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "id": "demo-mast-3",
                "user_id": "user_001",
                "subject": "Environment",
                "topic": "Climate Change & COP",
                "mastery_score": 0.60,
                "forgetting_risk": 0.82,
                "risk_level": "high",
                "confidence_score": 0.8,
                "total_attempts": 12,
                "correct_attempts": 7,
                "incorrect_attempts": 5,
                "revision_count": 2,
                "last_attempt_at": datetime.now(timezone.utc),
                "last_revised_at": datetime.now(timezone.utc),
                "next_revision_at": datetime.now(timezone.utc),
                "explanation_json": ["High risk of memory decay. Not revised in 5 days."],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        ]
        return {
            "average_mastery": 0.68,
            "strong_topics": [demo_topics[0]],
            "weak_topics": [demo_topics[1]],
            "high_risk_topics": [demo_topics[2]],
            "due_for_revision": [demo_topics[2]],
            "subject_breakdown": [
                {"subject": "Polity", "mastery_score": 0.78},
                {"subject": "Economy", "mastery_score": 0.70},
                {"subject": "History", "mastery_score": 0.65},
                {"subject": "Environment", "mastery_score": 0.60},
                {"subject": "Ethics", "mastery_score": 0.52}
            ],
            "recent_changes": []
        }
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
