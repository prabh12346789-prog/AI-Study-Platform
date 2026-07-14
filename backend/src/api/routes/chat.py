import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.schemas.chat import ChatRequest, ChatResponse
from src.services.orchestrator.service import AIOrchestrator, ConversationEvent

router = APIRouter()

orchestrator = AIOrchestrator()


def _format_sse_data(token: str) -> str:
    lines = token.splitlines() or [""]
    return "\n".join(f"data: {line}" for line in lines) + "\n\n"


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    print(f"[chat] request received: question={request.question!r}, mode={request.mode!r}", flush=True)
    print("[chat] before AIOrchestrator.process()", flush=True)
    try:
        response = await orchestrator.process(
            question=request.question, mode=request.mode, conversation_id=request.conversation_id,
            subject=request.subject, topic=request.topic,
            preferred_language=request.preferred_language,
            preferred_depth=request.preferred_depth,
            preferred_format=request.preferred_format,
            language=request.language, depth=request.depth, format=request.format,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    print("[chat] after AIOrchestrator.process()", flush=True)
    return response


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    print(f"[chat] stream request received: question={request.question!r}, mode={request.mode!r}", flush=True)

    async def event_stream():
        try:
            async for token in orchestrator.process_stream(
                question=request.question, mode=request.mode, conversation_id=request.conversation_id,
                subject=request.subject, topic=request.topic,
                preferred_language=request.preferred_language,
                preferred_depth=request.preferred_depth,
                preferred_format=request.preferred_format,
                language=request.language, depth=request.depth, format=request.format,
            ):
                if isinstance(token, ConversationEvent):
                    yield "event: conversation\n" + _format_sse_data(
                        json.dumps({
                            "conversation_id": token.conversation_id,
                            "subject": token.subject,
                            "topic": token.topic,
                            "effective_language": token.effective_language,
                            "effective_depth": token.effective_depth,
                            "effective_format": token.effective_format,
                        }, separators=(",", ":"))
                    )
                else:
                    yield _format_sse_data(token)
        except ValueError as exc:
            yield "event: error\n" + _format_sse_data(json.dumps({"detail": str(exc)}))

        # Closing the SSE response is the completion signal.  Do not append a
        # sentinel token: clients otherwise render it as part of the answer.

    return StreamingResponse(event_stream(), media_type="text/event-stream")
