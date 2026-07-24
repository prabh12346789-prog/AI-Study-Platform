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
        from src.core.config import settings
        from datetime import date
        if getattr(settings, "REPORT_DEMO_MODE", False):
            return {
                "demo_mode": True,
                "today": {
                    "study_seconds": 6000,
                    "questions_asked": 4,
                    "subjects_studied": 3,
                    "top_subject": "Polity",
                    "top_topic": "Constitutional Amendments",
                    "subject_breakdown": [
                        {"name": "Polity", "study_seconds": 3600, "event_count": 2},
                        {"name": "Economy", "study_seconds": 1800, "event_count": 1},
                        {"name": "History", "study_seconds": 600, "event_count": 1}
                    ]
                },
                "mentor_brief": {
                    "summary": "[Report Demo Mode] You studied Polity most today. Constitutional Amendments is currently a key focus. Ethics requires attention due to upcoming revision timelines.",
                    "strengths": [
                        {"id": "demo-mast-1", "subject": "Polity", "topic": "Constitutional Amendments", "mastery_score": 0.78, "forgetting_risk": 15, "risk_level": "low", "explanation": ["Strong performance on practice quizzes.", "Regular revisions completed."], "last_revised_at": "2026-07-23T10:00:00Z", "next_revision_at": "2026-07-30T10:00:00Z", "updated_at": "2026-07-24T00:00:00Z"}
                    ],
                    "weaknesses": [
                        {"id": "demo-mast-2", "subject": "Ethics", "topic": "Attitude & Moral Influence", "mastery_score": 0.52, "forgetting_risk": 65, "risk_level": "medium", "explanation": ["Lower scores on recent practice sessions.", "Needs conceptual reinforcement."], "last_revised_at": "2026-07-20T10:00:00Z", "next_revision_at": "2026-07-25T10:00:00Z", "updated_at": "2026-07-24T00:00:00Z"}
                    ],
                    "likely_to_forget": [
                        {"id": "demo-mast-3", "subject": "Environment", "topic": "Climate Change & COP", "mastery_score": 0.60, "forgetting_risk": 82, "risk_level": "high", "explanation": ["High risk of memory decay. Not revised in 5 days."], "last_revised_at": "2026-07-19T10:00:00Z", "next_revision_at": "2026-07-24T10:00:00Z", "updated_at": "2026-07-24T00:00:00Z"}
                    ],
                    "next_best_action": {
                        "id": "demo-act-1", "subject": "Environment", "topic": "Climate Change & COP", "action_type": "revision", "title": "Revise Climate Change COP targets", "reason": ["High forgetting risk detected.", "Syllabus high-yield topic."], "priority_score": 85, "priority_level": "high", "estimated_minutes": 20, "status": "active", "source_mastery_id": "demo-mast-3"
                    }
                },
                "mastery": {
                    "average_mastery": 0.68,
                    "strong_topics": [
                        {"id": "demo-mast-1", "subject": "Polity", "topic": "Constitutional Amendments", "mastery_score": 0.78, "forgetting_risk": 15, "risk_level": "low", "explanation": ["Strong performance on practice quizzes."], "last_revised_at": "2026-07-23T10:00:00Z", "next_revision_at": "2026-07-30T10:00:00Z", "updated_at": "2026-07-24T00:00:00Z"}
                    ],
                    "weak_topics": [
                        {"id": "demo-mast-2", "subject": "Ethics", "topic": "Attitude & Moral Influence", "mastery_score": 0.52, "forgetting_risk": 65, "risk_level": "medium", "explanation": ["Lower scores on recent practice sessions."], "last_revised_at": "2026-07-20T10:00:00Z", "next_revision_at": "2026-07-25T10:00:00Z", "updated_at": "2026-07-24T00:00:00Z"}
                    ],
                    "high_risk_topics": [
                        {"id": "demo-mast-3", "subject": "Environment", "topic": "Climate Change & COP", "mastery_score": 0.60, "forgetting_risk": 82, "risk_level": "high", "explanation": ["High risk of memory decay."], "last_revised_at": "2026-07-19T10:00:00Z", "next_revision_at": "2026-07-24T10:00:00Z", "updated_at": "2026-07-24T00:00:00Z"}
                    ],
                    "subject_breakdown": [
                        {"subject": "Polity", "mastery_score": 0.78},
                        {"subject": "Economy", "mastery_score": 0.70},
                        {"subject": "History", "mastery_score": 0.65},
                        {"subject": "Environment", "mastery_score": 0.60},
                        {"subject": "Ethics", "mastery_score": 0.52}
                    ]
                },
                "recommendations": {
                    "primary": {
                        "id": "demo-act-1", "subject": "Environment", "topic": "Climate Change & COP", "action_type": "revision", "title": "Revise Climate Change COP targets", "reason": ["High forgetting risk detected.", "Syllabus high-yield topic."], "priority_score": 85, "priority_level": "high", "estimated_minutes": 20, "status": "active", "source_mastery_id": "demo-mast-3"
                    },
                    "alternatives": [
                        {"id": "demo-act-2", "subject": "Polity", "topic": "Federal Structure", "action_type": "quiz", "title": "Practice Quiz on Federal Structure", "reason": ["Active recall due."], "priority_score": 70, "priority_level": "medium", "estimated_minutes": 15, "status": "active", "source_mastery_id": "demo-mast-4"}
                    ]
                },
                "recommended_videos": [],
                "profile": {
                    "preferred_language": "english",
                    "preferred_depth": "standard",
                    "preferred_format": "structured",
                    "daily_target_minutes": 120
                },
                "recent_activity": [
                    {"id": "demo-act-evt-1", "user_id": "user_001", "event_type": "study_time_logged", "subject": "Polity", "topic": "Constitutional Amendments", "duration_seconds": 3600, "metadata_json": {}, "occurred_at": "2026-07-24T08:00:00Z", "created_at": "2026-07-24T08:00:00Z"},
                    {"id": "demo-act-evt-2", "user_id": "user_001", "event_type": "quiz_answered", "subject": "History", "topic": "Ancient India", "duration_seconds": 600, "metadata_json": {"score": 4, "total": 5}, "occurred_at": "2026-07-23T15:30:00Z", "created_at": "2026-07-23T15:30:00Z"}
                ]
            }

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
