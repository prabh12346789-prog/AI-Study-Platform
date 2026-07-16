from sqlalchemy import select

from src.activity.manager import ActivityManager
from src.mastery.manager import MasteryManager
from src.memory.storage import get_session_factory
from src.mentor.manager import MentorDecisionEngine
from src.profile.manager import ProfileManager
from src.video.manager import VideoRecommendationService
from src.video.models import VideoResource


def setup(tmp_path):
    path = str(tmp_path / "videos.sqlite3")
    activity = ActivityManager(path); mastery = MasteryManager(path); profile = ProfileManager(path, activity)
    videos = VideoRecommendationService(path, activity)
    return path, videos, activity, mastery, profile


def add_video(path, **overrides):
    values = dict(id="custom", title="Custom lesson", description="Curated lesson", subject="Economy", topic="Monetary Policy",
        language="hindi", source_name="Trusted source", source_url="https://example.edu/video", thumbnail_url="",
        duration_seconds=500, difficulty="standard", verified=True, active=True)
    values.update(overrides)
    with get_session_factory(path)() as session: session.add(VideoResource(**values)); session.commit()


def test_verified_active_only_and_no_match(tmp_path):
    path, service, *_ = setup(tmp_path)
    add_video(path, id="unverified", verified=False); add_video(path, id="inactive", active=False)
    rows = service.recommend(subject="Economy", topic="Monetary Policy", explicit_request=True)
    assert rows and all(item["video"].verified and item["video"].active for item in rows)
    assert not service.recommend(subject="Ethics", topic="Integrity")


def test_exact_topic_language_duration_and_maximum_three(tmp_path):
    path, service, *_ = setup(tmp_path)
    add_video(path, id="preferred", language="hindi")
    add_video(path, id="subject", topic="Fiscal Policy", language="hindi")
    add_video(path, id="long", duration_seconds=4000)
    rows = service.recommend(subject="Economy", topic="Monetary Policy", language="hindi", max_duration_seconds=1800, explicit_request=True)
    assert len(rows) <= 3
    assert rows[0]["video"].id == "preferred"
    assert all(item["video"].duration_seconds <= 1800 for item in rows)
    assert any("Exact topic match" in item["reasons"] for item in rows)


def test_explicit_request_preference_watch_cooldown_and_no_mastery_change(tmp_path):
    _, service, activity, mastery, _ = setup(tmp_path)
    assert service.recommend(explicit_request=True)
    preferred = service.recommend(subject="Economy", topic="Monetary Policy", language="english", preferred_content_type="video")
    assert preferred
    mastery.record_evidence(subject="Economy", topic="Monetary Policy", evidence_type="quiz_incorrect")
    before = mastery.list_topic_mastery(subject="Economy", topic="Monetary Policy")[0].mastery_score
    video = preferred[0]["video"]
    assert service.open_video(video.id)
    after = mastery.list_topic_mastery(subject="Economy", topic="Monetary Policy")[0].mastery_score
    assert before == after
    event = activity.list_events(event_type="video_opened")[0]
    assert event.metadata_json["video_id"] == video.id
    service.dismiss_video(video.id)
    assert video.id not in {item["video"].id for item in service.recommend(subject="Economy", topic="Monetary Policy")}


def test_watch_video_action_requires_trusted_exact_match(tmp_path):
    path, videos, activity, mastery, profile = setup(tmp_path)
    profile.update({"preferred_content_type": "video", "preferred_language": "english"})
    mastery.record_evidence(subject="Economy", topic="Monetary Policy", evidence_type="quiz_incorrect")
    mastery.record_evidence(subject="Economy", topic="Monetary Policy", evidence_type="quiz_incorrect")
    engine = MentorDecisionEngine(path, mastery, profile, activity, videos)
    assert any(action.action_type == "watch_video" for action in engine.generate_actions())
    mastery.record_evidence(subject="Ethics", topic="Integrity", evidence_type="quiz_incorrect")
    mastery.record_evidence(subject="Ethics", topic="Integrity", evidence_type="quiz_incorrect")
    assert all(not (action.topic == "Integrity" and action.action_type == "watch_video") for action in engine.generate_actions())
