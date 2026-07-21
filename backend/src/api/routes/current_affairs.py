from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from src.core.config import settings
from src.current_affairs.service import CurrentAffairsService
from src.current_affairs.quiz_service import CurrentAffairsQuizService
from src.current_affairs.personalization import PersonalizedCurrentAffairsService
from src.schemas.current_affairs import ArticleResponse, CollectRequest, CollectResponse, DailyBriefResponse, DailyGenerateRequest
from src.schemas.current_affairs_quiz import QuizCreate, QuizSubmission

router = APIRouter()


def service(): return CurrentAffairsService()
def quiz_service(): return CurrentAffairsQuizService()
def require_admin(x_internal_key: str | None = Header(default=None, alias="X-Internal-Key", description="Configured INTERNAL_ADMIN_KEY; never expose this in the student frontend.")):
    if not settings.INTERNAL_ADMIN_KEY: raise HTTPException(status_code=503, detail="Internal collection key is not configured")
    if x_internal_key != settings.INTERNAL_ADMIN_KEY: raise HTTPException(status_code=403, detail="Internal access required")


def article_response(row, saved=False, opened=False):
    data = ArticleResponse.model_validate(row).model_dump(); data.update(saved=saved, opened=opened); return data

def quiz_response(row, svc):
    return {"id": row.id, "title": row.title, "period_type": row.period_type, "date_from": row.date_from,
        "date_to": row.date_to, "question_count": row.question_count, "difficulty": row.difficulty,
        "status": row.status, "article_ids_json": row.article_ids_json, "created_at": row.created_at,
        "updated_at": row.updated_at, "questions": [{"id": q.id, "question_type": q.question_type,
        "question": q.question, "options_json": q.options_json, "article_id": q.article_id,
        "source_url": q.source_url, "subject": q.subject, "topic": q.topic, "difficulty": q.difficulty}
        for q in svc.questions(row.id)]}

def retention_response(row):
    return {key: getattr(row, key) for key in ("id", "user_id", "article_id", "subject", "topic", "retention_score",
        "correct_attempts", "incorrect_attempts", "recall_failures", "last_attempt_at", "last_revised_at",
        "next_revision_at", "risk_level", "created_at", "updated_at")}

@router.post("/quizzes")
def create_quiz(payload: QuizCreate):
    svc = quiz_service()
    try: return quiz_response(svc.generate(payload), svc)
    except ValueError as error: raise HTTPException(status_code=422, detail=str(error)) from error

@router.get("/quizzes")
def quizzes():
    svc = quiz_service(); return [quiz_response(row, svc) for row in svc.list()]

@router.get("/quizzes/{quiz_id}")
def quiz(quiz_id: str):
    svc = quiz_service(); row = svc.get(quiz_id)
    if not row: raise HTTPException(status_code=404, detail="Current Affairs quiz not found")
    return quiz_response(row, svc)

@router.post("/quizzes/{quiz_id}/submit")
def submit_quiz(quiz_id: str, payload: QuizSubmission):
    try: return quiz_service().submit(quiz_id, payload.answers)
    except ValueError as error: raise HTTPException(status_code=422, detail=str(error)) from error

@router.get("/quizzes/{quiz_id}/attempts")
def quiz_attempts(quiz_id: str): return [quiz_service()._attempt_result(row) for row in quiz_service().attempts(quiz_id)]

@router.get("/retention")
def retention(): return [retention_response(row) for row in quiz_service().retention()]

@router.get("/retention/overview")
def retention_overview():
    data = quiz_service().overview(); data["high_risk_articles"] = [retention_response(row) for row in data["high_risk_articles"]]
    data["due_for_revision"] = [retention_response(row) for row in data["due_for_revision"]]; return data

@router.post("/retention/{article_id}/revise")
def revise(article_id: str):
    try: return retention_response(quiz_service().revise(article_id))
    except ValueError as error: raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/collect", response_model=CollectResponse, summary="Collect trusted current affairs for a date")
async def collect(payload: CollectRequest, _=Depends(require_admin)):
    return await service().collect_for_date(payload.date, max_results=payload.max_results,
        generate_brief=payload.generate_brief, language=payload.language)


@router.get("/articles", response_model=list[ArticleResponse])
def articles(date: date | None = None, date_from: date | None = None, date_to: date | None = None,
              subject: str | None = None, topic: str | None = None, importance: str | None = None,
              publisher: str | None = None, saved_only: bool = False, search: str | None = None,
              cadence: str | None = None, content_type: str | None = None, week_label: str | None = None,
              month: int | None = None, year: int | None = None):
    return [article_response(*item) for item in service().list_articles(date_value=date, date_from=date_from,
        date_to=date_to, subject=subject, topic=topic, importance=importance, publisher=publisher,
        saved_only=saved_only, search=search, cadence=cadence, content_type=content_type,
        week_label=week_label, month=month, year=year)]


@router.get("/articles/{article_id}", response_model=ArticleResponse)
def article(article_id: str):
    svc = service(); row = svc.get_article(article_id)
    if not row: raise HTTPException(status_code=404, detail="Current-affairs article not found")
    saved = any(item[0].id == article_id for item in svc.list_articles(saved_only=True))
    return article_response(row, saved, True)


@router.get("/{article_id}/content")
@router.get("/articles/{article_id}/content")
def article_content(article_id: str):
    data = service().get_article_content(article_id)
    if not data: raise HTTPException(status_code=404, detail="Current-affairs content not found")
    return data


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


@router.get("/personalized")
def personalized(date: date | None = None):
    return PersonalizedCurrentAffairsService().feed(date_value=date)
