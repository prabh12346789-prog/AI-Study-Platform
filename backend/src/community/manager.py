import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import func, or_, select

from src.activity.manager import ActivityManager
from src.community.models import CommunityComment, CommunityGroup, CommunityPost, CommunityReport, CommunitySavedPost
from src.memory.storage import get_session_factory

GROUPS = [
    ("Polity and Governance", "Polity and Governance"), ("History and Art & Culture", "History and Art & Culture"),
    ("Geography", "Geography"), ("Economy", "Economy"), ("Environment and Ecology", "Environment and Ecology"),
    ("Science and Technology", "Science and Technology"), ("International Relations", "International Relations"),
    ("Ethics", "Ethics"), ("Current Affairs", "Current Affairs"), ("Mains Answer Writing", "Mains Answer Writing"),
    ("Study Accountability", "Study Accountability"),
]
STATUSES = {"active", "hidden", "removed"}
REASONS = {"spam", "misinformation", "abusive", "unsafe", "personal_information", "irrelevant", "other"}
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d(?:[\s-]?\d){8}(?!\d)")


class CommunityManager:
    def __init__(self, db_path=None, activity=None):
        self._session_factory = get_session_factory(db_path=db_path); self.activity = activity or ActivityManager(db_path); self.seed_groups()

    def seed_groups(self):
        with self._session_factory() as session:
            for name, subject in GROUPS:
                slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                if not session.scalar(select(CommunityGroup).where(CommunityGroup.slug == slug)):
                    session.add(CommunityGroup(id=str(uuid.uuid4()), name=name, slug=slug, description=f"Focused UPSC study discussion for {name}.", subject=subject, active=True))
            session.commit()

    @staticmethod
    def validate_content(value, label, maximum):
        value = value.strip()
        if not value: raise ValueError(f"{label} cannot be empty")
        if len(value) > maximum: raise ValueError(f"{label} must be at most {maximum} characters")
        if EMAIL.search(value) or PHONE.search(value): raise ValueError("Public content cannot include phone numbers or email addresses")
        return value

    @staticmethod
    def validate_url(value):
        if not value: return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc: raise ValueError("source_url must be a valid HTTP or HTTPS URL")
        return value

    def groups(self):
        with self._session_factory() as session: return list(session.scalars(select(CommunityGroup).where(CommunityGroup.active.is_(True)).order_by(CommunityGroup.name)))
    def get_group(self, group_id):
        with self._session_factory() as session: return session.get(CommunityGroup, group_id)

    def create_post(self, data, user_id="user_001"):
        title = self.validate_content(data["title"], "title", 200); content = self.validate_content(data["content"], "content", 5000)
        with self._session_factory() as session:
            group = session.get(CommunityGroup, data["group_id"])
            if not group or not group.active: raise LookupError("Community group not found")
            duplicate = session.scalar(select(CommunityPost).where(CommunityPost.user_id == user_id, CommunityPost.title == title, CommunityPost.content == content, CommunityPost.status == "active"))
            if duplicate: raise ValueError("Repeated spam submission rejected")
            row = CommunityPost(id=str(uuid.uuid4()), user_id=user_id, group_id=group.id, title=title, content=content,
                language=data["language"], source_url=self.validate_url(data.get("source_url")), status="active")
            session.add(row); session.commit(); session.refresh(row)
        self.activity.record_event("community_post_created", datetime.now(timezone.utc), user_id=user_id, subject=group.subject, metadata_json={"post_id": row.id})
        return row

    def get_post(self, post_id, include_inactive=False):
        with self._session_factory() as session:
            row = session.get(CommunityPost, post_id)
            return row if row and (include_inactive or row.status == "active") else None

    def describe_post(self, row, user_id="user_001"):
        with self._session_factory() as session:
            group = session.get(CommunityGroup, row.group_id)
            comments = session.scalar(select(func.count()).select_from(CommunityComment).where(CommunityComment.post_id == row.id, CommunityComment.status == "active")) or 0
            saved = bool(session.scalar(select(CommunitySavedPost).where(CommunitySavedPost.user_id == user_id, CommunitySavedPost.post_id == row.id)))
        return {"id": row.id, "user_id": row.user_id, "group_id": row.group_id, "title": row.title, "content": row.content,
            "language": row.language, "source_url": row.source_url, "status": row.status, "created_at": row.created_at,
            "updated_at": row.updated_at, "display_name": "UPSC Learner", "group_name": group.name if group else "Community",
            "subject": group.subject if group else None, "comment_count": comments, "saved": saved}

    def list_posts(self, *, user_id="user_001", group_id=None, subject=None, language=None, search=None, saved_only=False, newest=True, limit=20, offset=0):
        with self._session_factory() as session:
            query = select(CommunityPost).join(CommunityGroup).where(CommunityPost.status == "active", CommunityGroup.active.is_(True))
            if group_id: query = query.where(CommunityPost.group_id == group_id)
            if subject: query = query.where(CommunityGroup.subject == subject)
            if language: query = query.where(CommunityPost.language == language)
            if search: query = query.where(or_(CommunityPost.title.ilike(f"%{search}%"), CommunityPost.content.ilike(f"%{search}%")))
            if saved_only: query = query.join(CommunitySavedPost).where(CommunitySavedPost.user_id == user_id)
            order = CommunityPost.created_at.desc() if newest else CommunityPost.created_at.asc()
            return list(session.scalars(query.order_by(order).offset(offset).limit(limit)))

    def update_post(self, post_id, data, user_id="user_001"):
        with self._session_factory() as session:
            row = session.get(CommunityPost, post_id)
            if not row: raise LookupError("Community post not found")
            if row.user_id != user_id: raise PermissionError("Only the owner can edit this post")
            if "title" in data: row.title = self.validate_content(data["title"], "title", 200)
            if "content" in data: row.content = self.validate_content(data["content"], "content", 5000)
            if "source_url" in data: row.source_url = self.validate_url(data["source_url"])
            if "language" in data: row.language = data["language"]
            session.commit(); session.refresh(row); return row

    def delete_post(self, post_id, user_id="user_001"):
        with self._session_factory() as session:
            row = session.get(CommunityPost, post_id)
            if not row: return False
            if row.user_id != user_id: raise PermissionError("Only the owner can delete this post")
            row.status = "removed"; session.commit(); return True

    def comments(self, post_id):
        with self._session_factory() as session: return list(session.scalars(select(CommunityComment).where(CommunityComment.post_id == post_id, CommunityComment.status == "active").order_by(CommunityComment.created_at)))
    def create_comment(self, post_id, content, user_id="user_001"):
        content = self.validate_content(content, "comment", 1500)
        if not self.get_post(post_id): raise LookupError("Community post not found")
        with self._session_factory() as session:
            if session.scalar(select(CommunityComment).where(CommunityComment.user_id == user_id, CommunityComment.post_id == post_id, CommunityComment.content == content, CommunityComment.status == "active")): raise ValueError("Repeated spam submission rejected")
            row = CommunityComment(id=str(uuid.uuid4()), user_id=user_id, post_id=post_id, content=content, status="active"); session.add(row); session.commit(); session.refresh(row)
        self.activity.record_event("community_comment_created", datetime.now(timezone.utc), user_id=user_id, metadata_json={"post_id": post_id, "comment_id": row.id}); return row
    def update_comment(self, comment_id, content, user_id="user_001"):
        with self._session_factory() as session:
            row = session.get(CommunityComment, comment_id)
            if not row: raise LookupError("Community comment not found")
            if row.user_id != user_id: raise PermissionError("Only the owner can edit this comment")
            row.content = self.validate_content(content, "comment", 1500); session.commit(); session.refresh(row); return row
    def delete_comment(self, comment_id, user_id="user_001"):
        with self._session_factory() as session:
            row = session.get(CommunityComment, comment_id)
            if not row: return False
            if row.user_id != user_id: raise PermissionError("Only the owner can delete this comment")
            row.status = "removed"; session.commit(); return True

    def save(self, post_id, user_id="user_001"):
        if not self.get_post(post_id): raise LookupError("Community post not found")
        with self._session_factory() as session:
            row = session.scalar(select(CommunitySavedPost).where(CommunitySavedPost.user_id == user_id, CommunitySavedPost.post_id == post_id))
            if not row: row = CommunitySavedPost(id=str(uuid.uuid4()), user_id=user_id, post_id=post_id); session.add(row); session.commit()
        self.activity.record_event("community_post_saved", datetime.now(timezone.utc), user_id=user_id, metadata_json={"post_id": post_id}); return row
    def unsave(self, post_id, user_id="user_001"):
        with self._session_factory() as session:
            row = session.scalar(select(CommunitySavedPost).where(CommunitySavedPost.user_id == user_id, CommunitySavedPost.post_id == post_id))
            if not row: return False
            session.delete(row); session.commit(); return True
    def report(self, data, user_id="user_001"):
        if data["reason"] not in REASONS: raise ValueError("Invalid report reason")
        target = self.get_post(data["target_id"], True) if data["target_type"] == "post" else None
        if data["target_type"] == "comment":
            with self._session_factory() as session: target = session.get(CommunityComment, data["target_id"])
        if not target: raise LookupError("Report target not found")
        if target.user_id == user_id: raise PermissionError("Users cannot report their own content")
        with self._session_factory() as session:
            row = CommunityReport(id=str(uuid.uuid4()), reporter_user_id=user_id, target_type=data["target_type"], target_id=data["target_id"], reason=data["reason"], details=data.get("details"), status="open"); session.add(row); session.commit(); session.refresh(row)
        self.activity.record_event("community_post_reported", datetime.now(timezone.utc), user_id=user_id, metadata_json={"target_type": data["target_type"], "target_id": data["target_id"]}); return row
