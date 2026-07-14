r"""Create an idempotent development-only demo database.

Run from backend: .\.venv\Scripts\python.exe scripts\seed_demo.py
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.activity.manager import ActivityManager
from src.community.manager import CommunityManager
from src.mastery.manager import MasteryManager
from src.mentor.manager import MentorDecisionEngine
from src.profile.manager import ProfileManager
from src.video.manager import VideoRecommendationService


def seed_demo(db_path: str) -> dict:
    activity = ActivityManager(db_path); mastery = MasteryManager(db_path); profile = ProfileManager(db_path, activity)
    videos = VideoRecommendationService(db_path, activity); community = CommunityManager(db_path, activity)
    profile.update({"preferred_language": "english", "preferred_depth": "standard", "preferred_format": "structured", "preferred_content_type": "video", "daily_study_target_minutes": 120})

    if not mastery.list_topic_mastery():
        for _ in range(4): mastery.record_evidence(subject="Polity and Governance", topic="Fundamental Rights", evidence_type="recall_success", source="demo_seed")
        mastery.record_evidence(subject="Polity and Governance", topic="Fundamental Rights", evidence_type="revision_completed", source="demo_seed")
        mastery.record_evidence(subject="Economy", topic="Monetary Policy", evidence_type="quiz_incorrect", source="demo_seed")
        mastery.record_evidence(subject="Economy", topic="Monetary Policy", evidence_type="quiz_incorrect", source="demo_seed")
        mastery.record_evidence(subject="Geography", topic="Climatology", evidence_type="recall_failure", occurred_at=datetime.now(timezone.utc) - timedelta(days=60), source="demo_seed")

    groups = {group.name: group for group in community.groups()}
    existing_titles = {post.title for post in community.list_posts(limit=100)}
    demo_posts = [
        ("Polity and Governance", "Article 32 answer-writing discussion", "How should Article 32 be introduced and evaluated in a concise Mains answer?"),
        ("Study Accountability", "Two-hour revision accountability plan", "Sharing a focused plan: Polity revision, one Economy quiz, and ten minutes of recall."),
    ]
    for group_name, title, content in demo_posts:
        if title not in existing_titles:
            community.create_post({"group_id": groups[group_name].id, "title": title, "content": content, "language": "english"}, user_id="demo_learner")

    engine = MentorDecisionEngine(db_path, mastery, profile, activity, videos)
    actions = engine.generate_actions()
    overview = mastery.get_mastery_overview()
    video_matches = videos.recommend(subject="Polity and Governance", topic="Fundamental Rights", language="english", explicit_request=True)
    result = {
        "database": str(Path(db_path).resolve()),
        "strong_topic": overview["strong_topics"][0].topic if overview["strong_topics"] else None,
        "weak_topic": overview["weak_topics"][0].topic if overview["weak_topics"] else None,
        "high_risk_topic": overview["high_risk_topics"][0].topic if overview["high_risk_topics"] else None,
        "completed_revisions": sum(row.revision_count for row in mastery.list_topic_mastery()),
        "quiz_mistakes": sum(row.incorrect_attempts for row in mastery.list_topic_mastery()),
        "mentor_recommendation": actions[0].title if actions else None,
        "trusted_video": video_matches[0]["video"].title if video_matches else None,
        "community_posts": len([post for post in community.list_posts(limit=100) if post.user_id == "demo_learner"]),
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--db-path", default="data/demo.sqlite3")
    print(json.dumps(seed_demo(parser.parse_args().db_path), indent=2))
