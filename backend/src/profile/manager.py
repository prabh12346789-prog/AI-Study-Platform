import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.activity.manager import ActivityManager
from src.memory.storage import get_session_factory
from src.profile.models import LearnerProfile


DEFAULTS = {
    "preferred_language": "auto",
    "preferred_depth": "standard",
    "preferred_format": "mixed",
    "daily_study_target_minutes": 120,
    "preferred_content_type": "mixed",
    "onboarding_completed": False,
}


class ProfileManager:
    def __init__(self, db_path: str | None = None, activity_manager: ActivityManager | None = None):
        self._session_factory = get_session_factory(db_path=db_path)
        self.activity_manager = activity_manager or ActivityManager(db_path=db_path)

    def get_or_create(self, user_id: str = "user_001") -> LearnerProfile:
        with self._session_factory() as session:
            profile = session.scalar(select(LearnerProfile).where(LearnerProfile.user_id == user_id))
            if profile is None:
                profile = LearnerProfile(id=str(uuid.uuid4()), user_id=user_id, **DEFAULTS)
                session.add(profile)
                session.commit()
                session.refresh(profile)
            return profile

    def update(self, values: dict, user_id: str = "user_001", *, replace: bool = False) -> LearnerProfile:
        profile = self.get_or_create(user_id)
        with self._session_factory() as session:
            stored = session.get(LearnerProfile, profile.id)
            editable_defaults = {key: value for key, value in DEFAULTS.items() if key != "onboarding_completed"}
            updates = {**editable_defaults, **values} if replace else values
            for field, value in updates.items():
                setattr(stored, field, value)
            session.commit()
            session.refresh(stored)
            return stored

    def delete(self, user_id: str = "user_001") -> bool:
        profile = self.get_or_create(user_id)
        with self._session_factory() as session:
            stored = session.get(LearnerProfile, profile.id)
            session.delete(stored)
            session.commit()
            return True

    def insights(self, user_id: str = "user_001") -> dict:
        now = datetime.now(timezone.utc)
        events = self.activity_manager.list_events(
            user_id=user_id, date_from=now - timedelta(days=7), date_to=now, limit=1_000_000
        )
        subjects = Counter(event.subject for event in events if event.subject)
        topics = Counter(event.topic for event in events if event.topic)
        modes = Counter(
            event.metadata_json.get("mode") for event in events
            if event.event_type == "question_asked" and event.metadata_json and event.metadata_json.get("mode")
        )
        study_events = [event for event in events if event.event_type == "study_time_logged"]
        total = sum(event.duration_seconds or 0 for event in study_events)
        active_days = len({event.occurred_at.date() for event in events})
        return {
            "most_studied_subject": subjects.most_common(1)[0][0] if subjects else None,
            "most_studied_topic": topics.most_common(1)[0][0] if topics else None,
            "total_study_seconds_7d": total,
            "questions_asked_7d": sum(event.event_type == "question_asked" for event in events),
            "active_days_7d": active_days,
            "average_daily_study_seconds": round(total / active_days) if active_days else 0,
            "preferred_mode_observed": modes.most_common(1)[0][0] if modes else None,
        }
