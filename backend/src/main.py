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
log.info("Settings loaded: provider=%s model=%s", settings.LLM_PROVIDER, settings.OLLAMA_MODEL)
log.info("Model imports and router registration started")
from src.api.router import api_router
log.info("Model imports and router registration finished")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log.info("Application ready in %.2f seconds", time.perf_counter() - STARTED_AT)
    yield


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/")
def root():
    return {"message": f"{settings.APP_NAME} Running"}


@app.get("/health")
def health():
    from src.rag.embeddings import EmbeddingService
    from src.rag.vector_store import VectorStore
    embedding_status = EmbeddingService.health_status()
    return {
        "status": "ok",
        "database": "ready",
        "ollama": "reachable" if embedding_status["ollama_reachable"] else "unreachable",
        "embedding_provider": embedding_status["provider"],
        "embedding_model": embedding_status["model"],
        "embedding_model_available": embedding_status["model_available"],
        "embeddings": "available" if EmbeddingService.is_loaded() else "not_checked",
        "vector_store": "ready" if VectorStore.is_initialized() else "not_initialized",
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
