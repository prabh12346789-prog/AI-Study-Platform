import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.activity.models import ActivityEvent
from src.mastery.models import LearningEvidence, TopicMastery
from src.memory.storage import get_session_factory

EVIDENCE_TYPES = {
    "quiz_correct", "quiz_incorrect", "revision_completed", "answer_self_rating",
    "mains_answer_score", "recall_success", "recall_failure",
}
DELTAS = {
    "quiz_correct": .10, "quiz_incorrect": -.10, "revision_completed": .03,
    "recall_success": .14, "recall_failure": -.16,
}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class MasteryManager:
    def __init__(self, db_path: str | None = None):
        self._session_factory = get_session_factory(db_path=db_path)

    def record_evidence(
        self, *, subject: str, topic: str, evidence_type: str,
        user_id: str = "user_001", score: float | None = None,
        confidence: float | None = None, occurred_at: datetime | None = None,
        source: str = "manual", metadata_json: dict | None = None,
        source_activity_event_id: str | None = None,
    ) -> TopicMastery:
        if evidence_type not in EVIDENCE_TYPES:
            raise ValueError(f"Unsupported learning evidence type: {evidence_type}")
        for name, value in (("score", score), ("confidence", confidence)):
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        with self._session_factory() as session:
            if source_activity_event_id and session.scalar(select(LearningEvidence).where(
                LearningEvidence.source_activity_event_id == source_activity_event_id
            )):
                existing = session.scalar(select(TopicMastery).where(
                    TopicMastery.user_id == user_id, TopicMastery.subject == subject, TopicMastery.topic == topic
                ))
                return existing
            safe_metadata = {
                key: value for key, value in (metadata_json or {}).items()
                if key not in {"answer", "full_answer", "question", "content"}
            } or None
            session.add(LearningEvidence(
                id=str(uuid.uuid4()), user_id=user_id, subject=subject, topic=topic,
                evidence_type=evidence_type, score=score, confidence=confidence,
                occurred_at=occurred_at or datetime.now(timezone.utc), source=source,
                metadata_json=safe_metadata, source_activity_event_id=source_activity_event_id,
            ))
            session.commit()
        return self.recalculate_topic(user_id=user_id, subject=subject, topic=topic)

    def recalculate_topic(self, *, user_id: str, subject: str, topic: str) -> TopicMastery:
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            evidence = list(session.scalars(select(LearningEvidence).where(
                LearningEvidence.user_id == user_id, LearningEvidence.subject == subject,
                LearningEvidence.topic == topic,
            ).order_by(LearningEvidence.occurred_at)))
            mastery = session.scalar(select(TopicMastery).where(
                TopicMastery.user_id == user_id, TopicMastery.subject == subject, TopicMastery.topic == topic
            ))
            if mastery is None:
                mastery = TopicMastery(id=str(uuid.uuid4()), user_id=user_id, subject=subject, topic=topic)
                session.add(mastery)
            value = .5
            correct = incorrect = revisions = 0
            attempts = []
            confidences = []
            reasons = []
            recent_failures = 0
            for item in evidence:
                age_days = max(0, (now - _aware(item.occurred_at)).days)
                recency = max(.35, 1 / (1 + age_days / 30))
                confidence = item.confidence if item.confidence is not None else .7
                delta = DELTAS.get(item.evidence_type, 0)
                if item.evidence_type == "mains_answer_score" and item.score is not None:
                    delta = (item.score - .5) * .18
                elif item.evidence_type == "answer_self_rating" and item.score is not None:
                    delta = (item.score - .5) * .08
                value += delta * recency * confidence
                confidences.append(confidence)
                if item.evidence_type in {"quiz_correct", "recall_success"}: correct += 1
                if item.evidence_type in {"quiz_incorrect", "recall_failure"}: incorrect += 1
                if item.evidence_type != "revision_completed": attempts.append(item)
                if item.evidence_type == "revision_completed": revisions += 1
                if item.evidence_type in {"quiz_incorrect", "recall_failure"} and age_days <= 14: recent_failures += 1
            value = max(0.0, min(1.0, value))
            last_attempt = max((item.occurred_at for item in attempts), default=None)
            revisions_list = [item for item in evidence if item.evidence_type == "revision_completed"]
            last_revision = max((item.occurred_at for item in revisions_list), default=None)
            revision_age = (now - _aware(last_revision)).days if last_revision else 30
            risk = .55 * (1 - value) + min(.4, revision_age / 45) + min(.2, recent_failures * .08)
            if last_revision and revision_age <= 7: risk -= .15
            risk = max(0.0, min(1.0, risk))
            interval = 2 if risk >= .65 else 5 if risk >= .35 else 14
            basis = _aware(last_revision or last_attempt or now)
            mastery.mastery_score = value
            mastery.forgetting_risk = risk
            mastery.confidence_score = min(1.0, (sum(confidences) / len(confidences) if confidences else 0) * min(1, len(evidence) / 5))
            mastery.total_attempts = len(attempts)
            mastery.correct_attempts = correct
            mastery.incorrect_attempts = incorrect
            mastery.revision_count = revisions
            mastery.last_attempt_at = last_attempt
            mastery.last_revised_at = last_revision
            mastery.next_revision_at = basis + timedelta(days=interval)
            reasons.extend([f"{correct} correct attempts", f"{incorrect} incorrect attempts", f"{revisions} revisions"])
            reasons.append(f"Estimated risk uses mastery, revision age ({revision_age} days), and recent failures ({recent_failures})")
            mastery.explanation_json = reasons
            session.commit(); session.refresh(mastery)
            return mastery

    def get_topic_mastery(self, mastery_id: str) -> TopicMastery | None:
        with self._session_factory() as session: return session.get(TopicMastery, mastery_id)

    def list_topic_mastery(self, *, user_id: str = "user_001", subject: str | None = None,
                           topic: str | None = None, risk_level: str | None = None,
                           weak_only: bool = False) -> list[TopicMastery]:
        with self._session_factory() as session:
            query = select(TopicMastery).where(TopicMastery.user_id == user_id)
            if subject: query = query.where(TopicMastery.subject == subject)
            if topic: query = query.where(TopicMastery.topic == topic)
            if weak_only: query = query.where(TopicMastery.mastery_score < .5)
            rows = list(session.scalars(query.order_by(TopicMastery.forgetting_risk.desc(), TopicMastery.mastery_score)))
            return [row for row in rows if risk_level is None or row.risk_level == risk_level]

    def delete_topic_mastery(self, mastery_id: str) -> bool:
        with self._session_factory() as session:
            mastery = session.get(TopicMastery, mastery_id)
            if not mastery: return False
            session.query(LearningEvidence).filter_by(user_id=mastery.user_id, subject=mastery.subject, topic=mastery.topic).delete()
            session.delete(mastery); session.commit(); return True

    def process_activity_event(self, event: ActivityEvent) -> TopicMastery | None:
        if not event.subject or not event.topic: return None
        if event.event_type == "quiz_answered":
            correct = bool((event.metadata_json or {}).get("correct"))
            return self.record_evidence(
                subject=event.subject, topic=event.topic,
                evidence_type="quiz_correct" if correct else "quiz_incorrect",
                confidence=(event.metadata_json or {}).get("confidence"), occurred_at=event.occurred_at,
                source="activity", source_activity_event_id=event.id,
            )
        if event.event_type == "revision_completed":
            return self.record_evidence(subject=event.subject, topic=event.topic,
                evidence_type="revision_completed", occurred_at=event.occurred_at,
                source="activity", source_activity_event_id=event.id)
        return None

    def get_mastery_overview(self, user_id: str = "user_001") -> dict:
        rows = self.list_topic_mastery(user_id=user_id)
        subjects: defaultdict[str, list[float]] = defaultdict(list)
        for row in rows: subjects[row.subject].append(row.mastery_score)
        now = datetime.now(timezone.utc)
        return {
            "average_mastery": sum(row.mastery_score for row in rows) / len(rows) if rows else 0,
            "strong_topics": [row for row in rows if row.mastery_score >= .7],
            "weak_topics": [row for row in rows if row.mastery_score < .5],
            "high_risk_topics": [row for row in rows if row.risk_level == "high"],
            "due_for_revision": [row for row in rows if row.next_revision_at and _aware(row.next_revision_at) <= now],
            "subject_breakdown": [{"subject": key, "mastery_score": sum(values) / len(values)} for key, values in subjects.items()],
            "recent_changes": sorted(rows, key=lambda row: row.updated_at, reverse=True)[:5],
        }
