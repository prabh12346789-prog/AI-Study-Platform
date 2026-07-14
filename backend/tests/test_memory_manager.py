from src.memory.manager import MemoryManager
import time


def test_memory_manager_round_trip(tmp_path):
    manager = MemoryManager(db_path=str(tmp_path / "memory.sqlite3"))
    conversation = manager.create_conversation(title="Test")
    assert conversation is not None

    manager.add_user_message(conversation_id=conversation.id, content="Hello")
    manager.add_assistant_message(conversation_id=conversation.id, content="Hi there")

    history = manager.get_recent_history(conversation_id=conversation.id, limit=5)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"

    manager.rename_conversation(conversation_id=conversation.id, title="Updated")
    renamed = manager.list_conversations()
    assert renamed[0].title == "Updated"

    manager.delete_conversation(conversation_id=conversation.id)
    assert manager.list_conversations() == []


def test_conversations_are_isolated_and_sorted_by_updated_at(tmp_path):
    manager = MemoryManager(db_path=str(tmp_path / "memory.sqlite3"))
    first = manager.create_conversation("Fundamental Rights")
    second = manager.create_conversation("Inflation")
    manager.add_user_message(first.id, "What is Article 32?")
    time.sleep(0.01)
    manager.add_user_message(second.id, "What causes inflation?")

    assert [item.content for item in manager.get_messages(first.id)] == ["What is Article 32?"]
    assert [item.content for item in manager.get_messages(second.id)] == ["What causes inflation?"]
    assert [item.id for item in manager.list_conversations()] == [second.id, first.id]


def test_missing_conversation_is_rejected(tmp_path):
    manager = MemoryManager(db_path=str(tmp_path / "memory.sqlite3"))
    try:
        manager.add_user_message("missing", "Hello")
    except ValueError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("Missing conversation should be rejected")
