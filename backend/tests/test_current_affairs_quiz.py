from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from src.current_affairs.models import CurrentAffairsArticle
from src.current_affairs.quiz_service import CurrentAffairsQuizService
from src.current_affairs.service import CurrentAffairsService
from src.mastery.manager import MasteryManager
from src.mentor.manager import MentorDecisionEngine

def seed(db, count=2, status="active"):
    svc = CurrentAffairsQuizService(str(db)); ids = []
    with svc.sessions() as session:
        for index in range(count):
            row = CurrentAffairsArticle(id=f"a{status}{index}", title=f"Official policy update {index}",
                summary=f"What happened: RBI issued grounded policy update {index} for regulated institutions.",
                source_title=f"Policy update {index}", publisher="Reserve Bank of India",
                source_url=f"https://rbi.org.in/article-{status}-{index}", publication_date=date.today(),
                retrieved_at=datetime.now(timezone.utc), subject="Economy", topic=f"Policy {index}",
                syllabus_tags_json=["GS III"], importance_level="high",
                relevance_prelims="\n".join(f"Grounded fact {index}-{n} from the accepted article" for n in range(1, 8)),
                relevance_mains=f"The accepted article explains policy implications {index}.",
                content_hash=f"hash-{status}-{index}", status=status)
            session.add(row); ids.append(row.id)
        session.commit()
    return svc, ids

def payload(period="daily", count=None):
    return SimpleNamespace(period_type=period, date_from=date.today(), date_to=date.today(),
        question_count=count, difficulty="standard")

def answers(svc, quiz, correct=True):
    return [SimpleNamespace(question_id=q.id, answer=q.correct_answer if correct else "wrong") for q in svc.questions(quiz.id)]

def test_daily_and_weekly_quiz_generation_and_distinct_questions(tmp_path):
    svc, _ = seed(tmp_path/"quiz.sqlite3")
    daily = svc.generate(payload()); weekly = svc.generate(payload("weekly"))
    assert daily.question_count == 5 and weekly.question_count == 10
    assert len({q.question for q in svc.questions(weekly.id)}) == 10

def test_accepted_articles_only_and_insufficient_content(tmp_path):
    svc, active = seed(tmp_path/"accepted.sqlite3", 1); seed(tmp_path/"other.sqlite3", 2, "rejected")
    quiz = svc.generate(payload(count=3)); assert quiz.article_ids_json == active
    with pytest.raises(ValueError, match="Insufficient"): svc.generate(payload(count=20))

def test_scoring_explanations_citations_retention_and_mastery(tmp_path):
    db = tmp_path/"score.sqlite3"; svc, _ = seed(db); quiz = svc.generate(payload())
    result = svc.submit(quiz.id, answers(svc, quiz, True))
    assert result["score"] == result["total"] == 5 and all(item["explanation"] and item["source_url"] for item in result["results"])
    assert all(row.retention_score > .5 for row in svc.retention())
    assert MasteryManager(str(db)).list_topic_mastery()

def test_incorrect_decreases_retention_and_high_risk_overview(tmp_path):
    svc, _ = seed(tmp_path/"risk.sqlite3"); quiz = svc.generate(payload())
    svc.submit(quiz.id, answers(svc, quiz, False)); rows = svc.retention()
    assert all(row.retention_score < .5 for row in rows)
    assert svc.overview()["high_risk_articles"]

def test_duplicate_submission_is_idempotent(tmp_path):
    db = tmp_path/"duplicate.sqlite3"; svc, _ = seed(db); quiz = svc.generate(payload())
    first = svc.submit(quiz.id, answers(svc, quiz)); before = [(r.correct_attempts, r.retention_score) for r in svc.retention()]
    second = svc.submit(quiz.id, answers(svc, quiz, False))
    assert first["id"] == second["id"] and before == [(r.correct_attempts, r.retention_score) for r in svc.retention()]

def test_open_save_and_start_do_not_change_retention(tmp_path):
    db = tmp_path/"reading.sqlite3"; svc, ids = seed(db); ca = CurrentAffairsService(db_path=str(db), llm=object(), indexer=lambda *_: None)
    ca.get_article(ids[0]); ca.save(ids[0]); svc.generate(payload())
    assert svc.retention() == []

def test_revision_updates_date_and_user_isolation(tmp_path):
    svc, ids = seed(tmp_path/"revision.sqlite3"); row = svc.revise(ids[0], user_id="user_001")
    assert row.last_revised_at and row.next_revision_at and svc.retention("other") == []

def test_current_affairs_evidence_drives_mentor_action(tmp_path):
    db = tmp_path/"mentor.sqlite3"; svc, _ = seed(db); quiz = svc.generate(payload())
    svc.submit(quiz.id, answers(svc, quiz, False))
    actions = MentorDecisionEngine(str(db)).generate_actions()
    assert any(row.action_type in {"revise_current_affairs", "take_current_affairs_quiz"} for row in actions)
