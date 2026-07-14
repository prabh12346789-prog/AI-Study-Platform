from fastapi import APIRouter

from src.api.routes import activity, chat, conversations, mastery, mentor, pdf, profile

api_router = APIRouter()

api_router.include_router(mentor.router, prefix="/mentor", tags=["Mentor"])

api_router.include_router(mastery.router, prefix="/mastery", tags=["Mastery"])

api_router.include_router(profile.router, prefix="/profile", tags=["Profile"])

api_router.include_router(activity.router, prefix="/activity", tags=["Activity"])

api_router.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])

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
