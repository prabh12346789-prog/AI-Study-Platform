from datetime import datetime, timezone
from sqlalchemy import inspect

from src.mentor.manager import MentorDecisionEngine


class MentorDashboardService:
    def __init__(self, engine: MentorDecisionEngine):
        self.engine = engine

    @staticmethod
    def _dump(item):
        if item is None: return None
        return {attribute.key: getattr(item, attribute.key) for attribute in inspect(item).mapper.column_attrs} | {
            **({"risk_level": item.risk_level, "explanation": item.explanation_json} if hasattr(item, "risk_level") else {})
        }

    def get_dashboard(self, user_id: str = "user_001") -> dict:
        from datetime import date

        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today = self.engine.activity.summarize(date_from=start, date_to=now)
        mastery = self.engine.mastery.get_mastery_overview(user_id)
        next_actions = self.engine.get_next_action(user_id)
        profile = self.engine.profile.get_or_create(user_id)
        strong = mastery["strong_topics"]
        weak = mastery["weak_topics"]
        risky = mastery["high_risk_topics"]
        primary = next_actions["action"]
        video_matches = self.engine.videos.recommend(user_id=user_id,
            subject=primary.subject if primary else today["top_subject"],
            topic=primary.topic if primary else today["top_topic"],
            language=profile.preferred_language if profile.preferred_language != "auto" else "english",
            preferred_content_type=profile.preferred_content_type)

        sentences = []
        if today["top_subject"]:
            sentences.append(f"You studied {today['top_subject']} most today.")
        if risky:
            sentences.append(f"{risky[0].topic} is currently your highest-risk topic.")
        elif weak:
            sentences.append(f"{weak[0].topic} is the clearest topic needing more evidence.")
        elif strong:
            sentences.append(f"{strong[0].topic} is currently a strength.")
        if primary:
            sentences.append(f"Your next priority is a {primary.estimated_minutes}-minute {primary.action_type.replace('_', ' ')} task.")
        if not sentences:
            sentences.append("There is not enough reliable study evidence yet to create a detailed mentor brief.")

        return {
            "today": {
                "study_seconds": today["total_study_seconds"],
                "questions_asked": today["questions_asked"],
                "subjects_studied": today["subjects_studied"],
                "top_subject": today["top_subject"], "top_topic": today["top_topic"],
                "subject_breakdown": today["subject_breakdown"],
            },
            "mentor_brief": {
                "summary": " ".join(sentences[:3]),
                "strengths": [self._dump(item) for item in strong],
                "weaknesses": [self._dump(item) for item in weak],
                "likely_to_forget": [self._dump(item) for item in risky],
                "next_best_action": self._dump(primary),
            },
            "mastery": {
                "average_mastery": mastery["average_mastery"],
                "strong_topics": [self._dump(item) for item in strong],
                "weak_topics": [self._dump(item) for item in weak],
                "high_risk_topics": [self._dump(item) for item in risky],
                "subject_breakdown": mastery["subject_breakdown"],
            },
            "recommendations": {
                "primary": self._dump(primary),
                "alternatives": [self._dump(item) for item in next_actions["alternatives"]],
            },
            "recommended_videos": [{"video": self._dump(item["video"]), "reasons": item["reasons"]} for item in video_matches],
            "profile": {
                "preferred_language": profile.preferred_language,
                "preferred_depth": profile.preferred_depth,
                "preferred_format": profile.preferred_format,
                "daily_target_minutes": profile.daily_study_target_minutes,
            },
            "recent_activity": [self._dump(item) for item in today["recent_events"]],
        }
