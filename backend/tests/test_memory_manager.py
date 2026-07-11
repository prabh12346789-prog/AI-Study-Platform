from src.memory.manager import MemoryManager


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
