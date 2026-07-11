from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.schemas.chat import ChatRequest, ChatResponse
from src.services.orchestrator.service import AIOrchestrator

router = APIRouter()

orchestrator = AIOrchestrator()


def _format_sse_data(token: str) -> str:
    lines = token.splitlines() or [""]
    return "\n".join(f"data: {line}" for line in lines) + "\n\n"


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    print(f"[chat] request received: question={request.question!r}, mode={request.mode!r}", flush=True)
    print("[chat] before AIOrchestrator.process()", flush=True)
    response = await orchestrator.process(
        question=request.question,
        mode=request.mode,
    )
    print("[chat] after AIOrchestrator.process()", flush=True)
    return response


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    print(f"[chat] stream request received: question={request.question!r}, mode={request.mode!r}", flush=True)

    async def event_stream():
        async for token in orchestrator.process_stream(
            question=request.question,
            mode=request.mode,
        ):
            yield _format_sse_data(token)

        yield "event: done\ndata: END\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")