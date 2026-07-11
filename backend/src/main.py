from fastapi import FastAPI
from fastapi.responses import Response

from src.api.router import api_router
from src.core.config import settings

print("========== CONFIG ==========")
print(f"LLM Provider : {settings.LLM_PROVIDER}")
print(f"OLLAMA_MODEL : {settings.OLLAMA_MODEL}")
print("============================")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)

app.include_router(api_router)


@app.get("/")
def root():
    return {
        "message": f"{settings.APP_NAME} Running 🚀"
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)