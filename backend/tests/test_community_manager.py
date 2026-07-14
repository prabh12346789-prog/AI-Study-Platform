from sqlalchemy import select

from src.activity.manager import ActivityManager
from src.community.manager import CommunityManager
from src.community.models import CommunityPost
from src.mastery.manager import MasteryManager
from src.memory.storage import get_session_factory


def setup(tmp_path):
    path = str(tmp_path / "community.sqlite3"); activity = ActivityManager(path)
    return path, CommunityManager(path, activity), activity, MasteryManager(path)


def post(manager, user="user_001", **values):
    group = manager.groups()[0]
    data = {"group_id": group.id, "title": "Article 32 discussion", "content": "How should this constitutional remedy be structured in a Mains answer?", "language": "english", "source_url": "https://legislative.gov.in/constitution-of-india/"}
    data.update(values); return manager.create_post(data, user)


def test_groups_posts_filters_pagination_and_hidden_exclusion(tmp_path):
    path, manager, *_ = setup(tmp_path)
    assert len(manager.groups()) == 11
    first = post(manager); second = post(manager, title="Different question", content="A separate focused learning discussion.")
    assert manager.get_post(first.id).title == "Article 32 discussion"
    assert manager.list_posts(search="Article", limit=1, offset=0)[0].id == first.id
    assert manager.list_posts(group_id=first.group_id, language="english")
    assert len(manager.list_posts(limit=1)) == 1
    with get_session_factory(path)() as session:
        row = session.get(CommunityPost, second.id); row.status = "hidden"; session.commit()
    assert second.id not in {row.id for row in manager.list_posts()}


def test_post_ownership_update_delete_validation_and_spam(tmp_path):
    _, manager, *_ = setup(tmp_path); row = post(manager)
    updated = manager.update_post(row.id, {"title": "Updated Article 32"}); assert updated.title == "Updated Article 32"
    try: manager.update_post(row.id, {"title": "Not mine"}, "user_002"); assert False
    except PermissionError: pass
    for bad in ({"content": ""}, {"content": "Email me at learner@example.com"}, {"content": "Call 9876543210"}, {"source_url": "javascript:alert(1)"}):
        try: post(manager, title=str(bad), **bad); assert False
        except ValueError: pass
    try: manager.create_post({"group_id": row.group_id, "title": updated.title, "content": updated.content, "language": "english"}); assert False
    except ValueError: pass
    assert manager.delete_post(row.id)
    assert manager.get_post(row.id) is None


def test_comments_saves_reports_and_user_isolation(tmp_path):
    _, manager, activity, _ = setup(tmp_path); row = post(manager, user="user_002")
    comment = manager.create_comment(row.id, "A useful constitutional-law response.")
    assert manager.update_comment(comment.id, "Updated useful response.").content.startswith("Updated")
    try: manager.delete_comment(comment.id, "user_002"); assert False
    except PermissionError: pass
    assert manager.delete_comment(comment.id)
    manager.save(row.id); assert manager.list_posts(saved_only=True)[0].id == row.id
    assert manager.list_posts(user_id="user_002", saved_only=True) == []
    assert manager.unsave(row.id)
    report = manager.report({"target_type": "post", "target_id": row.id, "reason": "misinformation", "details": "Needs source review"})
    assert report.status == "open"
    try: manager.report({"target_type": "post", "target_id": row.id, "reason": "spam"}, "user_002"); assert False
    except PermissionError: pass
    assert activity.list_events(event_type="community_comment_created")
    assert activity.list_events(event_type="community_post_saved")
    assert activity.list_events(event_type="community_post_reported")


def test_community_activity_never_changes_mastery(tmp_path):
    _, manager, activity, mastery = setup(tmp_path); row = post(manager)
    manager.create_comment(row.id, "Study-only comment without private details.")
    manager.save(row.id)
    events = [event for kind in ("community_post_created", "community_comment_created", "community_post_saved") for event in activity.list_events(event_type=kind)]
    assert all(mastery.process_activity_event(event) is None for event in events)
    assert mastery.list_topic_mastery() == []
