from fastapi import APIRouter, Response, status

from src.profile.manager import ProfileManager
from src.schemas.profile import ProfileInsights, ProfilePatch, ProfileReplace, ProfileResponse

router = APIRouter()
manager = ProfileManager()


@router.get("", response_model=ProfileResponse)
def get_profile():
    return manager.get_or_create()


@router.put("", response_model=ProfileResponse)
def replace_profile(payload: ProfileReplace):
    return manager.update(payload.model_dump(), replace=True)


@router.patch("", response_model=ProfileResponse)
def patch_profile(payload: ProfilePatch):
    return manager.update(payload.model_dump(exclude_none=True))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile():
    manager.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/onboarding", response_model=ProfileResponse)
def complete_onboarding(payload: ProfileReplace):
    values = payload.model_dump()
    values["onboarding_completed"] = True
    return manager.update(values)


@router.get("/insights", response_model=ProfileInsights)
def profile_insights():
    return manager.insights()
