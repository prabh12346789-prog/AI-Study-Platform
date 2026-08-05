import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

STARTED_AT = time.perf_counter()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("startup")
log.info("Settings load started")
from src.core.config import settings
log.info("Settings loaded: provider=%s model=%s", settings.LLM_PROVIDER, settings.OLLAMA_GENERATION_MODEL)
log.info("Model imports and router registration started")
from src.api.router import api_router
log.info("Model imports and router registration finished")


from src.current_affairs.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log.info("Application ready in %.2f seconds", time.perf_counter() - STARTED_AT)
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/")
def root():
    return {"message": f"{settings.APP_NAME} Running"}


@app.get("/health")
def health():
    from src.ai.ollama_status import availability_status
    from src.rag.embeddings import EmbeddingService
    from src.rag.vector_store import VectorStore
    ollama_status = availability_status()
    return {
        "status": "ok",
        "database": "ready",
        "ollama": ollama_status.model_dump(),
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "embedding_model": settings.OLLAMA_EMBEDDING_MODEL,
        "embedding_model_available": ollama_status.embedding_model_available,
        "embeddings": "available" if EmbeddingService.is_loaded() else "not_checked",
        "vector_store": "ready" if VectorStore.is_initialized() else "not_initialized",
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
