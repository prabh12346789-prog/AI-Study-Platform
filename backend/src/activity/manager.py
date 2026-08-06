import uuid
from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy import inspect, select, text

from src.activity.models import ActivityEvent
from src.memory.storage import get_session_factory


SUPPORTED_EVENT_TYPES = {
    "question_asked", "answer_generated", "pdf_uploaded", "quiz_answered",
    "revision_completed", "video_opened", "recommendation_accepted",
    "recommendation_skipped",
    "study_time_logged",
    "internal_search",
    "visual_roadmap_generated", "visual_roadmap_opened", "visual_roadmap_saved",
    "roadmap_quiz_started", "roadmap_quiz_completed",
    "current_affairs_opened", "current_affairs_saved", "daily_brief_completed",
    "current_affairs_quiz_started", "current_affairs_quiz_completed", "current_affairs_revision_completed",
    "upsc_note_opened", "upsc_note_saved",
    "upsc_book_opened", "upsc_book_saved",
    "test_started", "prelims_test_completed", "current_affairs_test_completed",
    "mains_question_generated", "mains_answer_submitted", "mains_evaluation_completed"
}


class ActivityManager:
    def __init__(self, db_path: str | None = None):
        self._session_factory = get_session_factory(db_path=db_path)
        self._ensure_compatible_schema()

    def _ensure_compatible_schema(self) -> None:
        with self._session_factory() as session:
            columns = {column["name"] for column in inspect(session.bind).get_columns("activity_events")}
            additions = {
                "user_id": "VARCHAR(64) NOT NULL DEFAULT 'user_001'",
                "subject": "VARCHAR(128)",
                "topic": "VARCHAR(255)",
                "duration_seconds": "INTEGER",
            }
            for name, definition in additions.items():
                if name not in columns:
                    session.execute(text(f"ALTER TABLE activity_events ADD COLUMN {name} {definition}"))
            session.commit()

    def record_event(
        self,
        event_type: str,
        occurred_at: datetime,
        *,
        user_id: str = "user_001",
        conversation_id: str | None = None,
        subject: str | None = None,
        topic: str | None = None,
        duration_seconds: int | None = None,
        metadata_json: dict | None = None,
    ) -> ActivityEvent:
        if event_type not in SUPPORTED_EVENT_TYPES:
            raise ValueError(f"Unsupported activity event type: {event_type}")
        if event_type == "study_time_logged" and (duration_seconds is None or duration_seconds <= 0):
            raise ValueError("study_time_logged requires duration_seconds greater than zero")
        if event_type == "internal_search" and not (topic or "").strip():
            raise ValueError("internal_search requires the platform search term in topic")
        event = ActivityEvent(
            id=str(uuid.uuid4()),
            event_type=event_type,
            user_id=user_id,
            conversation_id=conversation_id,
            subject=subject,
            topic=topic,
            duration_seconds=duration_seconds,
            metadata_json=metadata_json,
            consented=True,
            occurred_at=occurred_at,
        )
        with self._session_factory() as session:
            session.add(event)
            session.commit()
            session.refresh(event)
            return event

    def get_event(self, event_id: str) -> ActivityEvent | None:
        with self._session_factory() as session:
            return session.get(ActivityEvent, event_id)

    def list_events(
        self, *, user_id: str | None = None, conversation_id: str | None = None,
        event_type: str | None = None, subject: str | None = None,
        topic: str | None = None, date_from: datetime | None = None,
        date_to: datetime | None = None, limit: int = 100,
    ) -> list[ActivityEvent]:
        with self._session_factory() as session:
            query = select(ActivityEvent)
            filters = {
                ActivityEvent.user_id: user_id,
                ActivityEvent.conversation_id: conversation_id,
                ActivityEvent.event_type: event_type,
                ActivityEvent.subject: subject,
                ActivityEvent.topic: topic,
            }
            for column, value in filters.items():
                if value is not None:
                    query = query.where(column == value)
            if date_from is not None:
                query = query.where(ActivityEvent.occurred_at >= date_from)
            if date_to is not None:
                query = query.where(ActivityEvent.occurred_at <= date_to)
            return list(
                session.execute(
                    query
                    .order_by(ActivityEvent.occurred_at.desc(), ActivityEvent.id)
                    .limit(limit)
                ).scalars().all()
            )

    def delete_event(self, event_id: str) -> bool:
        with self._session_factory() as session:
            event = session.get(ActivityEvent, event_id)
            if event is None:
                return False
            session.delete(event)
            session.commit()
            return True

    def summarize(self, *, date_from: datetime, date_to: datetime) -> dict:
        events = self.list_events(date_from=date_from, date_to=date_to, limit=1_000_000)
        subject_counts: Counter[str] = Counter()
        topic_counts: Counter[str] = Counter()
        subject_seconds: defaultdict[str, int] = defaultdict(int)
        topic_seconds: defaultdict[str, int] = defaultdict(int)
        daily: defaultdict[str, dict[str, int]] = defaultdict(lambda: {"study_seconds": 0, "event_count": 0})
        monthly: defaultdict[str, dict[str, int]] = defaultdict(lambda: {"study_seconds": 0, "event_count": 0, "searches_made": 0, "questions_asked": 0})
        search_counts: Counter[str] = Counter()
        for event in events:
            # Historical rows may contain event names from removed features. Keep
            # them readable, but never let them affect active learning progress.
            if event.event_type not in SUPPORTED_EVENT_TYPES:
                continue
            if event.subject:
                subject_counts[event.subject] += 1
            if event.topic:
                topic_counts[event.topic] += 1
            day = event.occurred_at.date().isoformat()
            month = event.occurred_at.strftime("%Y-%m")
            daily[day]["event_count"] += 1
            monthly[month]["event_count"] += 1
            if event.event_type == "study_time_logged" and event.duration_seconds:
                daily[day]["study_seconds"] += event.duration_seconds
                monthly[month]["study_seconds"] += event.duration_seconds
                if event.subject:
                    subject_seconds[event.subject] += event.duration_seconds
                if event.topic:
                    topic_seconds[event.topic] += event.duration_seconds
            if event.event_type == "internal_search" and event.topic:
                search_counts[event.topic.strip()] += 1
                monthly[month]["searches_made"] += 1
            if event.event_type == "question_asked":
                monthly[month]["questions_asked"] += 1

        def breakdown(counts: Counter[str], seconds: dict[str, int]) -> list[dict]:
            return [
                {"name": name, "study_seconds": seconds.get(name, 0), "event_count": count}
                for name, count in counts.most_common()
            ]

        return {
            "total_study_seconds": sum(
                event.duration_seconds or 0 for event in events if event.event_type == "study_time_logged"
            ),
            "questions_asked": sum(event.event_type == "question_asked" for event in events),
            "answers_generated": sum(event.event_type == "answer_generated" for event in events),
            "pdfs_uploaded": sum(event.event_type == "pdf_uploaded" for event in events),
            "searches_made": sum(event.event_type == "internal_search" for event in events),
            "top_searches": [term for term, _count in search_counts.most_common(10)],
            "first_activity_at": min((event.occurred_at for event in events), default=None),
            "total_learning_days": len(daily),
            "subjects_studied": len(subject_counts),
            "top_subject": subject_counts.most_common(1)[0][0] if subject_counts else None,
            "top_topic": topic_counts.most_common(1)[0][0] if topic_counts else None,
            "subject_breakdown": breakdown(subject_counts, subject_seconds),
            "topic_breakdown": breakdown(topic_counts, topic_seconds),
            "recent_events": events[:10],
            "daily_breakdown": [
                {"date": day, **values} for day, values in sorted(daily.items())
            ],
            "monthly_breakdown": [
                {"month": month, **values} for month, values in sorted(monthly.items())
            ],
        }


# Backward-compatible name for the initial milestone implementation.
ActivityEventStore = ActivityManager
