from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.memory.models import Conversation, ConversationMessage
from src.memory.storage import get_session_factory


@dataclass
class ConversationSummary:
    id: str
    title: str
    created_at: Any
    updated_at: Any


class MemoryManager:
    def __init__(self, db_path: str | None = None):
        self._session_factory = get_session_factory(db_path=db_path)

    def _session(self) -> Session:
        return self._session_factory()

    def create_conversation(self, title: str | None = None) -> Conversation:
        conversation = Conversation(id=str(uuid.uuid4()), title=title or "New Conversation")
        with self._session() as session:
            session.add(conversation)
            session.commit()
            session.refresh(conversation)
            return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._session() as session:
            return session.get(Conversation, conversation_id)

    def conversation_exists(self, conversation_id: str) -> bool:
        return self.get_conversation(conversation_id) is not None

    def get_messages(self, conversation_id: str) -> list[ConversationMessage]:
        with self._session() as session:
            return list(session.execute(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.created_at, ConversationMessage.id)
            ).scalars().all())

    def _touch(self, session: Session, conversation_id: str) -> None:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation '{conversation_id}' not found")
        conversation.updated_at = datetime.now(timezone.utc)

    def add_user_message(self, conversation_id: str, content: str) -> ConversationMessage:
        message = ConversationMessage(conversation_id=conversation_id, role="user", content=content)
        with self._session() as session:
            self._touch(session, conversation_id)
            session.add(message)
            session.commit()
            session.refresh(message)
            return message

    def add_assistant_message(self, conversation_id: str, content: str) -> ConversationMessage:
        message = ConversationMessage(conversation_id=conversation_id, role="assistant", content=content)
        with self._session() as session:
            self._touch(session, conversation_id)
            session.add(message)
            session.commit()
            session.refresh(message)
            return message

    def get_recent_history(self, conversation_id: str, limit: int = 10) -> list[dict[str, str]]:
        with self._session() as session:
            messages = (
                session.execute(
                    select(ConversationMessage)
                    .where(ConversationMessage.conversation_id == conversation_id)
                    .order_by(ConversationMessage.created_at.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return [
                {"role": message.role, "content": message.content}
                for message in sorted(messages, key=lambda item: item.created_at)
            ]

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._session() as session:
            conversation = session.get(Conversation, conversation_id)
            if conversation is not None:
                session.delete(conversation)
                session.commit()
                return True
            return False

    def list_conversations(self) -> list[ConversationSummary]:
        with self._session() as session:
            conversations = session.execute(
                select(Conversation).order_by(Conversation.updated_at.desc())
            ).scalars().all()
            return [
                ConversationSummary(
                    id=conversation.id,
                    title=conversation.title,
                    created_at=conversation.created_at,
                    updated_at=conversation.updated_at,
                )
                for conversation in conversations
            ]

    def rename_conversation(self, conversation_id: str, title: str) -> Conversation | None:
        with self._session() as session:
            conversation = session.get(Conversation, conversation_id)
            if conversation is None:
                return None
            conversation.title = title
            session.commit()
            session.refresh(conversation)
            return conversation
