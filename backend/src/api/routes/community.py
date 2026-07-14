from fastapi import APIRouter, Header, HTTPException, Query, Response, status

from src.community.manager import CommunityManager
from src.schemas.community import CommentCreate, CommentResponse, GroupResponse, PostCreate, PostPatch, PostResponse, ReportCreate, ReportResponse

router = APIRouter(); manager = CommunityManager()
def user_id(value: str | None): return value or "user_001"
def fail(error):
    code = 403 if isinstance(error, PermissionError) else 404 if isinstance(error, LookupError) else 422
    raise HTTPException(status_code=code, detail=str(error)) from error
def post_dump(row, user): return manager.describe_post(row, user)

@router.get("/groups", response_model=list[GroupResponse])
def groups(): return manager.groups()
@router.get("/groups/{group_id}", response_model=GroupResponse)
def group(group_id: str):
    row = manager.get_group(group_id)
    if not row: raise HTTPException(404, "Community group not found")
    return row
@router.get("/posts", response_model=list[PostResponse])
def posts(group_id: str | None = None, subject: str | None = None, language: str | None = None, search: str | None = None,
          saved_only: bool = False, sort: str = "newest", limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), x_user_id: str | None = Header(None)):
    user = user_id(x_user_id); rows = manager.list_posts(user_id=user, group_id=group_id, subject=subject, language=language, search=search, saved_only=saved_only, newest=sort != "oldest", limit=limit, offset=offset)
    return [post_dump(row, user) for row in rows]
@router.post("/posts", response_model=PostResponse, status_code=201)
def create_post(payload: PostCreate, x_user_id: str | None = Header(None)):
    user = user_id(x_user_id)
    try: return post_dump(manager.create_post(payload.model_dump(mode="json"), user), user)
    except (ValueError, LookupError) as error: fail(error)
@router.get("/posts/{post_id}", response_model=PostResponse)
def get_post(post_id: str, x_user_id: str | None = Header(None)):
    row = manager.get_post(post_id)
    if not row: raise HTTPException(404, "Community post not found")
    return post_dump(row, user_id(x_user_id))
@router.patch("/posts/{post_id}", response_model=PostResponse)
def patch_post(post_id: str, payload: PostPatch, x_user_id: str | None = Header(None)):
    user = user_id(x_user_id)
    try: return post_dump(manager.update_post(post_id, payload.model_dump(exclude_unset=True, mode="json"), user), user)
    except (ValueError, LookupError, PermissionError) as error: fail(error)
@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: str, x_user_id: str | None = Header(None)):
    try:
        if not manager.delete_post(post_id, user_id(x_user_id)): raise HTTPException(404, "Community post not found")
        return Response(status_code=204)
    except PermissionError as error: fail(error)
@router.get("/posts/{post_id}/comments", response_model=list[CommentResponse])
def comments(post_id: str): return manager.comments(post_id)
@router.post("/posts/{post_id}/comments", response_model=CommentResponse, status_code=201)
def create_comment(post_id: str, payload: CommentCreate, x_user_id: str | None = Header(None)):
    try: return manager.create_comment(post_id, payload.content, user_id(x_user_id))
    except (ValueError, LookupError) as error: fail(error)
@router.patch("/comments/{comment_id}", response_model=CommentResponse)
def patch_comment(comment_id: str, payload: CommentCreate, x_user_id: str | None = Header(None)):
    try: return manager.update_comment(comment_id, payload.content, user_id(x_user_id))
    except (ValueError, LookupError, PermissionError) as error: fail(error)
@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(comment_id: str, x_user_id: str | None = Header(None)):
    try:
        if not manager.delete_comment(comment_id, user_id(x_user_id)): raise HTTPException(404, "Community comment not found")
        return Response(status_code=204)
    except PermissionError as error: fail(error)
@router.post("/posts/{post_id}/save", status_code=201)
def save(post_id: str, x_user_id: str | None = Header(None)):
    try: manager.save(post_id, user_id(x_user_id)); return {"saved": True}
    except LookupError as error: fail(error)
@router.delete("/posts/{post_id}/save", status_code=204)
def unsave(post_id: str, x_user_id: str | None = Header(None)): manager.unsave(post_id, user_id(x_user_id)); return Response(status_code=204)
@router.get("/saved", response_model=list[PostResponse])
def saved(x_user_id: str | None = Header(None)):
    user = user_id(x_user_id); return [post_dump(row, user) for row in manager.list_posts(user_id=user, saved_only=True)]
@router.post("/reports", response_model=ReportResponse, status_code=201)
def report(payload: ReportCreate, x_user_id: str | None = Header(None)):
    try: return manager.report(payload.model_dump(), user_id(x_user_id))
    except (ValueError, LookupError, PermissionError) as error: fail(error)
