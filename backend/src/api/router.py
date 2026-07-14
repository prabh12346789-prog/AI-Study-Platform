import logging
from fastapi import APIRouter

log = logging.getLogger("startup")
log.info("Router registration: importing lightweight route modules")
from src.api.routes import activity, chat, community, conversations, mastery, mentor, pdf, profile, videos
log.info("Router registration: route and model imports completed")

api_router = APIRouter()

api_router.include_router(community.router, prefix="/community", tags=["Community"])

api_router.include_router(videos.router, prefix="/videos", tags=["Videos"])

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
log.info("Router registration completed")
