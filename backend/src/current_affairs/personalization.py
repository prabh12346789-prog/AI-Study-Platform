import re
from collections import Counter
from datetime import date, datetime, timezone

from src.current_affairs.quiz_service import CurrentAffairsQuizService
from src.current_affairs.service import CurrentAffairsService
from src.current_affairs.source_policy import TIER_ORDER, source_adapter
from src.mastery.manager import MasteryManager
from src.profile.manager import ProfileManager


STOPWORDS = {"the", "a", "an", "of", "for", "to", "and", "in", "on", "india", "new", "update"}


def normalized_title(value: str) -> str:
    words = re.findall(r"[a-z0-9]+", value.casefold())
    return " ".join(word for word in words if word not in STOPWORDS)


def title_similarity(left: str, right: str) -> float:
    a, b = set(normalized_title(left).split()), set(normalized_title(right).split())
    return len(a & b) / len(a | b) if a and b else 0.0


class PersonalizedCurrentAffairsService:
    def __init__(self, db_path=None, current_affairs=None, profiles=None, mastery=None, quizzes=None):
        self.current = current_affairs or CurrentAffairsService(db_path=db_path)
        self.profiles = profiles or ProfileManager(db_path=db_path)
        self.mastery = mastery or MasteryManager(db_path=db_path)
        self.quizzes = quizzes or CurrentAffairsQuizService(db_path=db_path)

    @staticmethod
    def _same_issue(article, issue) -> bool:
        lead = issue["articles"][0]
        if article.source_url == lead.source_url or article.content_hash == lead.content_hash:
            return True
        same_day = article.publication_date == lead.publication_date
        same_topic = article.topic.casefold() == lead.topic.casefold()
        return same_day and (same_topic or title_similarity(article.title, lead.title) >= .5)

    def _groups(self, rows):
        groups = []
        for article, saved, opened in rows:
            issue = next((item for item in groups if self._same_issue(article, item)), None)
            if issue is None:
                issue = {"articles": [], "saved": False, "opened": False}; groups.append(issue)
            issue["articles"].append(article); issue["saved"] |= saved; issue["opened"] |= opened
        for issue in groups:
            issue["articles"].sort(key=lambda row: TIER_ORDER.get((source_adapter(row.source_url) or type("X", (), {"tier": ""})()).tier, 0), reverse=True)
        return groups

    def feed(self, *, user_id="user_001", date_value: date | None = None):
        profile = self.profiles.get_or_create(user_id)
        insights = self.profiles.insights(user_id)
        mode = insights.get("preferred_mode_observed") or "prelims"
        mastery = self.mastery.list_topic_mastery(user_id=user_id)
        weak_topics = {row.topic.casefold(): row for row in mastery if row.mastery_score < .5 or row.risk_level == "high"}
        retention = {row.article_id: row for row in self.quizzes.retention(user_id)}
        rows = self.current.list_articles(user_id=user_id, date_value=date_value)
        groups = self._groups(rows)
        today = date.today()
        results = []
        for issue in groups:
            lead = issue["articles"][0]
            adapter = source_adapter(lead.source_url)
            age = max(0, (today - (lead.publication_date or today)).days)
            score = {"high": 35, "medium": 22, "low": 10}[lead.importance_level]
            reasons = [f"{lead.importance_level.title()} UPSC importance"]
            if adapter and adapter.tier == "primary": score += 18; reasons.append("Primary official source")
            if lead.topic.casefold() in weak_topics: score += 20; reasons.append("Matches a weak or high-risk topic")
            if insights.get("most_studied_subject") == lead.subject: score += 10; reasons.append("Matches recent study activity")
            if issue["saved"]: score += 5; reasons.append("Previously saved")
            if any(retention.get(row.id) and retention[row.id].risk_level == "high" for row in issue["articles"]):
                score += 15; reasons.append("Current Affairs revision is due")
            score += max(0, 12 - age * 2)
            score += 8 if mode == "mains" and lead.relevance_mains else 8 if mode == "prelims" and lead.relevance_prelims else 0
            sources = [{"article_id": row.id, "publisher": row.publisher, "url": row.source_url,
                        "tier": (source_adapter(row.source_url).tier if source_adapter(row.source_url) else "primary")}
                       for row in issue["articles"]]
            results.append({"issue_id": lead.id, "title": lead.title, "summary": lead.summary,
                "subject": lead.subject, "topic": lead.topic, "importance_level": lead.importance_level,
                "publication_date": lead.publication_date, "prelims": lead.relevance_prelims,
                "mains": lead.relevance_mains, "saved": issue["saved"], "opened": issue["opened"],
                "score": round(score, 2), "reasons": reasons, "sources": sources,
                "source_tier": adapter.tier if adapter else "primary"})
        results.sort(key=lambda item: item["score"], reverse=True)
        due = [row for row in retention.values() if row.next_revision_at and row.next_revision_at.replace(tzinfo=row.next_revision_at.tzinfo or timezone.utc) <= datetime.now(timezone.utc)]
        return {"user_id": user_id, "effective_language": profile.preferred_language,
            "effective_depth": profile.preferred_depth, "effective_format": profile.preferred_format,
            "exam_mode": mode, "daily_target_minutes": profile.daily_study_target_minutes,
            "issues": results, "top_stories": results[:5],
            "prelims_facts": [item for item in results if item["prelims"]][:8],
            "mains_analysis": [item for item in results if item["mains"]][:8],
            "editorials": [item for item in results if item["source_tier"] in {"daily_analysis", "mains_editorial"}],
            "monthly_revision": [item for item in results if item["source_tier"] == "monthly_revision"],
            "saved_stories": [item for item in results if item["saved"]],
            "revision_due": len(due),
            "recommended_videos": [
                {"publisher": "Drishti IAS", "url": "https://www.youtube.com/@DrishtiIASvideos", "reason": "Approved UPSC analysis channel"},
                {"publisher": "Vision IAS", "url": "https://www.youtube.com/@VisionIASdelhi", "reason": "Approved UPSC revision channel"},
                {"publisher": "Sansad TV", "url": "https://sansadtv.nic.in/", "reason": "Official parliamentary discussion"},
                {"publisher": "PIB", "url": "https://www.youtube.com/@PIBIndia", "reason": "Primary government updates"},
                {"publisher": "DD News", "url": "https://ddnews.gov.in/", "reason": "Official public broadcaster"},
                {"publisher": "MEA", "url": "https://www.youtube.com/@MEAIndia", "reason": "Official foreign-policy updates"},
            ]}
