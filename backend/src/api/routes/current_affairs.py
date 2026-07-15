from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from src.core.config import settings
from src.current_affairs.service import CurrentAffairsService
from src.schemas.current_affairs import ArticleResponse, CollectRequest, CollectResponse, DailyBriefResponse, DailyGenerateRequest

router = APIRouter()


def service(): return CurrentAffairsService()
def require_admin(x_internal_key: str | None = Header(default=None, alias="X-Internal-Key", description="Configured INTERNAL_ADMIN_KEY; never expose this in the student frontend.")):
    if not settings.INTERNAL_ADMIN_KEY: raise HTTPException(status_code=503, detail="Internal collection key is not configured")
    if x_internal_key != settings.INTERNAL_ADMIN_KEY: raise HTTPException(status_code=403, detail="Internal access required")


def article_response(row, saved=False, opened=False):
    data = ArticleResponse.model_validate(row).model_dump(); data.update(saved=saved, opened=opened); return data


@router.post("/collect", response_model=CollectResponse, summary="Collect trusted current affairs for a date")
async def collect(payload: CollectRequest, _=Depends(require_admin)):
    return await service().collect_for_date(payload.date, max_results=payload.max_results,
        generate_brief=payload.generate_brief, language=payload.language)


@router.get("/articles", response_model=list[ArticleResponse])
def articles(date: date | None = None, date_from: date | None = None, date_to: date | None = None,
             subject: str | None = None, topic: str | None = None, importance: str | None = None,
             publisher: str | None = None, saved_only: bool = False, search: str | None = None):
    return [article_response(*item) for item in service().list_articles(date_value=date, date_from=date_from,
        date_to=date_to, subject=subject, topic=topic, importance=importance, publisher=publisher,
        saved_only=saved_only, search=search)]


@router.get("/articles/{article_id}", response_model=ArticleResponse)
def article(article_id: str):
    svc = service(); row = svc.get_article(article_id)
    if not row: raise HTTPException(status_code=404, detail="Current-affairs article not found")
    saved = any(item[0].id == article_id for item in svc.list_articles(saved_only=True))
    return article_response(row, saved, True)


@router.get("/daily", response_model=DailyBriefResponse)
def daily(date: date = Query(default_factory=date.today), language: str = "english"):
    row = service().get_daily(date, language)
    if not row: raise HTTPException(status_code=404, detail="Daily brief not available")
    return row


@router.post("/daily/generate", response_model=DailyBriefResponse)
def generate_daily(payload: DailyGenerateRequest, _=Depends(require_admin)):
    try: return service().generate_daily(payload.date, payload.language)
    except ValueError as error: raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/articles/{article_id}/save", status_code=204)
def save(article_id: str):
    if not service().save(article_id): raise HTTPException(status_code=404, detail="Current-affairs article not found")
    return Response(status_code=204)


@router.delete("/articles/{article_id}/save", status_code=204)
def unsave(article_id: str):
    if not service().unsave(article_id): raise HTTPException(status_code=404, detail="Saved article not found")
    return Response(status_code=204)


@router.get("/saved", response_model=list[ArticleResponse])
def saved(): return [article_response(*item) for item in service().list_articles(saved_only=True)]


@router.get("/summary")
def summary(): return service().dashboard_summary()
