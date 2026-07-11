from fastapi import APIRouter

from src.api.routes import chat, pdf

api_router = APIRouter()

api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["Chat"],
)

api_router.include_router(
    pdf.router,
    prefix="/pdf",
    tags=["PDF"],
)