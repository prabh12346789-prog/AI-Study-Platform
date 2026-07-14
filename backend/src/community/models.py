from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class CommunityGroup(Base):
    __tablename__ = "community_groups"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True); slug: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(Text); subject: Mapped[str] = mapped_column(String(128), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CommunityPost(Base):
    __tablename__ = "community_posts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True); user_id: Mapped[str] = mapped_column(String(64), index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("community_groups.id"), index=True)
    title: Mapped[str] = mapped_column(String(200)); content: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(16), index=True); source_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CommunityComment(Base):
    __tablename__ = "community_comments"
    id: Mapped[str] = mapped_column(String(64), primary_key=True); user_id: Mapped[str] = mapped_column(String(64), index=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("community_posts.id"), index=True); content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CommunitySavedPost(Base):
    __tablename__ = "community_saved_posts"; __table_args__ = (UniqueConstraint("user_id", "post_id"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True); user_id: Mapped[str] = mapped_column(String(64), index=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("community_posts.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommunityReport(Base):
    __tablename__ = "community_reports"
    id: Mapped[str] = mapped_column(String(64), primary_key=True); reporter_user_id: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str] = mapped_column(String(16)); target_id: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(String(32)); details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
