import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.activity.manager import ActivityManager
from src.mastery.manager import MasteryManager, _aware
from src.mastery.models import LearningEvidence
from src.memory.storage import get_session_factory
from src.mentor.models import MentorRecommendation
from src.profile.manager import ProfileManager

ACTION_TYPES = {"revise_topic", "take_quiz", "review_explanation", "practise_recall", "practise_mains_answer"}
STATUSES = {"pending", "accepted", "completed", "skipped", "expired"}


class MentorDecisionEngine:
    def __init__(self, db_path: str | None = None, mastery_manager=None, profile_manager=None, activity_manager=None):
        self._session_factory = get_session_factory(db_path=db_path)
        self.mastery = mastery_manager or MasteryManager(db_path)
        self.profile = profile_manager or ProfileManager(db_path)
        self.activity = activity_manager or ActivityManager(db_path)

    @staticmethod
    def _level(score: float) -> str:
        return "urgent" if score >= .8 else "high" if score >= .6 else "medium" if score >= .4 else "low"

    def _duration(self, available_minutes: int | None = None) -> int:
        depth = self.profile.get_or_create().preferred_depth
        minutes = {"quick": 8, "standard": 15, "detailed": 25}[depth]
        return min(minutes, available_minutes) if available_minutes and available_minutes >= 5 else minutes

    def _decision(self, mastery, evidence, available_minutes=None):
        now = datetime.now(timezone.utc)
        overdue = bool(mastery.next_revision_at and _aware(mastery.next_revision_at) < now)
        recent = [e for e in evidence if (now - _aware(e.occurred_at)).days <= 14]
        recall_failure = any(e.evidence_type == "recall_failure" for e in recent)
        incorrect = sum(e.evidence_type in {"quiz_incorrect", "recall_failure"} for e in recent)
        mains = [e for e in evidence if e.evidence_type == "mains_answer_score"]
        preference = self.profile.get_or_create().preferred_content_type
        if recall_failure: action = "practise_recall"
        elif mastery.forgetting_risk >= .65 or overdue: action = "revise_topic"
        elif mains and sum((e.score or 0) for e in mains) / len(mains) < .5: action = "practise_mains_answer"
        elif mastery.mastery_score < .5 and incorrect >= 2: action = "take_quiz" if preference == "quiz" else "review_explanation"
        elif mastery.total_attempts == 0: action = "take_quiz"
        else: action = "take_quiz" if mastery.mastery_score < .7 else None
        failure_signal = min(1, incorrect / 3)
        inactivity = min(1, (now - _aware(mastery.last_attempt_at or mastery.created_at)).days / 30)
        score = min(1, max(0, .45 * mastery.forgetting_risk + .3 * (1 - mastery.mastery_score) + .15 * int(overdue) + .07 * failure_signal + .03 * inactivity))
        if not action or score < .25: return None
        reasons = [f"Mastery is {round(mastery.mastery_score * 100)}%", f"Forgetting risk is {mastery.risk_level}"]
        if overdue: reasons.append("Revision is overdue")
        if recall_failure: reasons.append("A recent recall attempt was unsuccessful")
        if incorrect >= 2: reasons.append(f"{incorrect} recent incorrect attempts")
        titles = {"revise_topic": "Revise", "take_quiz": "Take a diagnostic quiz on", "review_explanation": "Review", "practise_recall": "Practise recall for", "practise_mains_answer": "Practise a Mains answer on"}
        return action, f"{titles[action]} {mastery.topic}", score, reasons, self._duration(available_minutes)

    def generate_actions(self, user_id="user_001", available_minutes=None):
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            existing = list(session.scalars(select(MentorRecommendation).where(MentorRecommendation.user_id == user_id)))
            mastery_rows = self.mastery.list_topic_mastery(user_id=user_id)
            for action in existing:
                source = next((m for m in mastery_rows if m.id == action.source_mastery_id), None)
                if action.status in {"pending", "accepted"} and (action.valid_until < now.replace(tzinfo=None) or not source or abs(action.mastery_score_snapshot - source.mastery_score) >= .1): action.status = "expired"
                elif action.status in {"pending", "accepted"} and available_minutes and available_minutes >= 5:
                    action.estimated_minutes = min(action.estimated_minutes, available_minutes)
            session.commit()
            created = []
            for mastery in mastery_rows:
                evidence = list(session.scalars(select(LearningEvidence).where(LearningEvidence.user_id == user_id, LearningEvidence.subject == mastery.subject, LearningEvidence.topic == mastery.topic)))
                decision = self._decision(mastery, evidence, available_minutes)
                if not decision: continue
                action_type, title, score, reasons, minutes = decision
                duplicate = session.scalar(select(MentorRecommendation).where(
                    MentorRecommendation.user_id == user_id, MentorRecommendation.subject == mastery.subject,
                    MentorRecommendation.topic == mastery.topic, MentorRecommendation.action_type == action_type,
                    MentorRecommendation.status.in_(["pending", "accepted"])))
                cooldown = session.scalar(select(MentorRecommendation).where(
                    MentorRecommendation.user_id == user_id, MentorRecommendation.subject == mastery.subject,
                    MentorRecommendation.topic == mastery.topic, MentorRecommendation.action_type == action_type,
                    MentorRecommendation.status == "skipped").order_by(MentorRecommendation.skipped_at.desc()))
                if duplicate or cooldown and cooldown.skipped_at and now - _aware(cooldown.skipped_at) < timedelta(days=2): continue
                row = MentorRecommendation(id=str(uuid.uuid4()), user_id=user_id, subject=mastery.subject, topic=mastery.topic,
                    action_type=action_type, title=title, reason=reasons, priority_score=score, priority_level=self._level(score),
                    estimated_minutes=minutes, status="pending", source_mastery_id=mastery.id,
                    mastery_score_snapshot=mastery.mastery_score, valid_until=now + timedelta(days=7))
                session.add(row); created.append(row)
            session.commit()
        return [row for row in self.list_actions(user_id=user_id) if row.status in {"pending", "accepted"}][:3]

    def list_actions(self, user_id="user_001", status: str | None = None):
        with self._session_factory() as session:
            query = select(MentorRecommendation).where(MentorRecommendation.user_id == user_id)
            if status: query = query.where(MentorRecommendation.status == status)
            return list(session.scalars(query.order_by(MentorRecommendation.priority_score.desc())))

    def get_next_action(self, user_id="user_001", available_minutes=None):
        rows = self.generate_actions(user_id, available_minutes)
        if available_minutes is not None: rows = [r for r in rows if r.estimated_minutes <= available_minutes]
        return {"action": rows[0] if rows else None, "alternatives": rows[1:3]}

    def update_action_status(self, action_id, status):
        if status not in STATUSES: raise ValueError("Invalid recommendation status")
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            row = session.get(MentorRecommendation, action_id)
            if not row: return None
            if row.status == status: return row
            row.status = status
            if status == "accepted": row.accepted_at = now
            if status == "completed": row.completed_at = now
            if status == "skipped": row.skipped_at = now
            session.commit(); session.refresh(row)
        event_type = "recommendation_accepted" if status == "accepted" else "recommendation_skipped" if status == "skipped" else "revision_completed" if status == "completed" and row.action_type == "revise_topic" else None
        if event_type:
            event = self.activity.record_event(event_type, now, user_id=row.user_id, subject=row.subject, topic=row.topic,
                metadata_json={"recommendation_id": row.id, "source": "mentor_plan"})
            if event_type == "revision_completed": self.mastery.process_activity_event(event)
        return row

    def complete_action(self, action_id): return self.update_action_status(action_id, "completed")
    def regenerate_actions(self, user_id="user_001", available_minutes=None): return self.generate_actions(user_id, available_minutes)
