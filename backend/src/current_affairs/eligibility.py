from __future__ import annotations

from urllib.parse import urlparse

from src.current_affairs.models import CurrentAffairsArticle
from src.current_affairs.source_policy import source_adapter


def is_quiz_ready_article(article: CurrentAffairsArticle | None) -> bool:
    if article is None or article.is_demo or article.status != "active":
        return False
    if not article.title or not article.publication_date or not article.source_url:
        return False
    # Quiz grounding comes from the accepted article's summary plus its
    # extracted Prelims/Mains relevance fields.  A fixed summary word count
    # incorrectly excludes concise official releases even when those grounded
    # fields are present.
    if not article.summary or not article.relevance_prelims or not article.relevance_mains:
        return False
    if source_adapter(article.source_url) is None:
        return False
    article_id = (article.id or "").casefold()
    if article_id.startswith(("test-", "demo-", "sample-", "dmy-")):
        return False
    return True


def is_official_source_url(url: str) -> bool:
    adapter = source_adapter(url)
    return bool(adapter and urlparse(url).scheme in {"http", "https"})
