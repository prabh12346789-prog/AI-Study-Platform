from fastapi import APIRouter, HTTPException, Response, status

from src.memory.manager import MemoryManager
from src.schemas.conversation import ConversationRename, ConversationResponse, MessageResponse

router = APIRouter()
memory = MemoryManager()


def _conversation_or_404(conversation_id: str):
    conversation = memory.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found")
    return conversation


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation():
    return memory.create_conversation()


@router.get("", response_model=list[ConversationResponse])
def list_conversations():
    return memory.list_conversations()


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: str):
    return _conversation_or_404(conversation_id)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
def get_messages(conversation_id: str):
    _conversation_or_404(conversation_id)
    return [MessageResponse(id=m.id, conversation_id=m.conversation_id, role=m.role,
                            content=m.content, timestamp=m.created_at)
            for m in memory.get_messages(conversation_id)]


@router.patch("/{conversation_id}", response_model=ConversationResponse)
def rename_conversation(conversation_id: str, payload: ConversationRename):
    conversation = memory.rename_conversation(conversation_id, payload.title.strip())
    if conversation is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found")
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str):
    if not memory.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
