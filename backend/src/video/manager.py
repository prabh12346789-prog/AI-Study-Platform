from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.activity.manager import ActivityManager
from src.memory.storage import get_session_factory
from src.video.catalog import CATALOG
from src.video.models import VideoResource

LANGUAGES = {"english", "hindi", "punjabi"}
DIFFICULTIES = {"beginner", "standard", "advanced"}


class VideoRecommendationService:
    def __init__(self, db_path: str | None = None, activity_manager=None):
        self._session_factory = get_session_factory(db_path=db_path)
        self.activity = activity_manager or ActivityManager(db_path)
        self.seed_catalog()

    def seed_catalog(self) -> None:
        with self._session_factory() as session:
            for resource in CATALOG:
                if not session.get(VideoResource, resource["id"]):
                    session.add(VideoResource(**resource, verified=True, active=True))
            session.commit()

    def get_video(self, video_id: str) -> VideoResource | None:
        with self._session_factory() as session:
            return session.get(VideoResource, video_id)

    def list_videos(self, *, subject=None, topic=None, language=None, difficulty=None, max_duration_seconds=None):
        if language and language not in LANGUAGES: raise ValueError("Invalid video language")
        if difficulty and difficulty not in DIFFICULTIES: raise ValueError("Invalid video difficulty")
        with self._session_factory() as session:
            query = select(VideoResource).where(VideoResource.active.is_(True), VideoResource.verified.is_(True))
            if subject: query = query.where(VideoResource.subject == subject)
            if topic: query = query.where(VideoResource.topic == topic)
            if language: query = query.where(VideoResource.language == language)
            if difficulty: query = query.where(VideoResource.difficulty == difficulty)
            if max_duration_seconds: query = query.where(VideoResource.duration_seconds <= max_duration_seconds)
            return list(session.scalars(query.order_by(VideoResource.subject, VideoResource.topic)))

    def _dismissed_ids(self, user_id: str) -> set[str]:
        since = datetime.now(timezone.utc) - timedelta(days=2)
        events = self.activity.list_events(user_id=user_id, event_type="recommendation_skipped", date_from=since)
        return {event.metadata_json.get("video_id") for event in events if event.metadata_json and event.metadata_json.get("video_id")}

    def recommend(self, *, user_id="user_001", subject=None, topic=None, language=None, difficulty=None,
                  max_duration_seconds=None, preferred_content_type=None, explicit_request=False,
                  mastery_score=None, forgetting_risk=None, repeated_mistakes=0):
        rows = self.list_videos(difficulty=difficulty, max_duration_seconds=max_duration_seconds)
        dismissed = self._dismissed_ids(user_id)
        rows = [row for row in rows if row.id not in dismissed]
        if not subject and not topic and not explicit_request and preferred_content_type != "video": return []
        def rank(row):
            topic_match = bool(topic and row.topic.casefold() == topic.casefold())
            subject_match = bool(subject and row.subject.casefold() == subject.casefold())
            language_match = bool(language and row.language == language)
            return (4 if topic_match and language_match else 3 if topic_match else 2 if subject_match else 1 if explicit_request else 0,
                    int(preferred_content_type == "video"), int(repeated_mistakes >= 2), -row.duration_seconds)
        ranked = [(rank(row), row) for row in rows]
        ranked = [item for item in ranked if item[0][0] > 0]
        ranked.sort(key=lambda item: item[0], reverse=True)
        result = []
        for score, row in ranked[:3]:
            reasons = ["Verified resource from a curated trusted source"]
            if topic and row.topic.casefold() == topic.casefold(): reasons.append("Exact topic match")
            elif subject and row.subject.casefold() == subject.casefold(): reasons.append("Subject match")
            if language and row.language == language: reasons.append("Matches your preferred language")
            if max_duration_seconds: reasons.append("Fits your available time")
            if repeated_mistakes >= 2: reasons.append("Offers another explanation after repeated difficulty")
            result.append({"video": row, "reasons": reasons})
        return result

    def open_video(self, video_id: str, *, user_id="user_001"):
        row = self.get_video(video_id)
        if not row or not row.active or not row.verified: return None
        self.activity.record_event("video_opened", datetime.now(timezone.utc), user_id=user_id,
            subject=row.subject, topic=row.topic, metadata_json={"video_id": row.id, "language": row.language, "source_name": row.source_name})
        return row

    def dismiss_video(self, video_id: str, *, user_id="user_001"):
        row = self.get_video(video_id)
        if not row: return None
        self.activity.record_event("recommendation_skipped", datetime.now(timezone.utc), user_id=user_id,
            subject=row.subject, topic=row.topic, metadata_json={"video_id": row.id, "source": "video_recommendation"})
        return row
