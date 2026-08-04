from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from src.current_affairs.models import CurrentAffairsArticle, CurrentAffairsQuizQuestion
from src.current_affairs.quiz_service import CurrentAffairsQuizService
from src.current_affairs.service import CurrentAffairsService
from src.mastery.manager import MasteryManager
from src.mentor.manager import MentorDecisionEngine

def seed(db, count=6, status="active"):
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
    svc, _ = seed(tmp_path/"quiz.sqlite3", 10)
    daily = svc.generate(payload()); weekly = svc.generate(payload("weekly"))
    assert daily.question_count == 5 and weekly.question_count == 10
    assert len({q.question for q in svc.questions(weekly.id)}) == 10

def test_accepted_articles_only_and_insufficient_content(tmp_path):
    svc, active = seed(tmp_path/"accepted.sqlite3", 4); seed(tmp_path/"other.sqlite3", 2, "rejected")
    quiz = svc.generate(payload(count=3)); assert set(quiz.article_ids_json).issubset(set(active))
    limited = svc.generate(payload(count=20))
    assert limited.question_count == len(svc.questions(limited.id)) == 4

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

def test_partial_submission_counts_unanswered_against_total(tmp_path):
    svc, _ = seed(tmp_path/"partial.sqlite3"); quiz = svc.generate(payload(count=5)); questions = svc.questions(quiz.id)
    result = svc.submit(quiz.id, [SimpleNamespace(question_id=q.id, answer=q.correct_answer) for q in questions[:3]])
    assert result["score"] == result["answered_count"] == result["correct_count"] == 3
    assert result["total"] == result["total_questions"] == 5
    assert result["unanswered_count"] == 2 and result["incorrect_count"] == 2 and result["percentage"] == 60.0
    assert [item["status"] for item in result["results"]].count("unanswered") == 2
    assert all(item["selected_answer"] is None for item in result["results"] if item["status"] == "unanswered")

def test_unknown_and_duplicate_question_ids_are_rejected(tmp_path):
    svc, _ = seed(tmp_path/"ids.sqlite3"); quiz = svc.generate(payload()); question = svc.questions(quiz.id)[0]
    with pytest.raises(ValueError, match="belong"):
        svc.submit(quiz.id, [SimpleNamespace(question_id="unknown", answer="x")])
    with pytest.raises(ValueError, match="Duplicate"):
        svc.submit(quiz.id, [SimpleNamespace(question_id=question.id, answer="x"), SimpleNamespace(question_id=question.id, answer="y")])

def test_generated_questions_are_clean_four_option_mcqs(tmp_path):
    svc, _ = seed(tmp_path/"clean.sqlite3"); quiz = svc.generate(payload()); questions = svc.questions(quiz.id)
    assert len(questions) == 5
    for question in questions:
        assert svc.question_is_valid(question)
        assert len(question.options_json) == len(set(question.options_json)) == 4
        assert question.correct_answer in question.options_json
        assert all(len(option) <= 180 for option in question.options_json)
        assert question.source_url.startswith("https://rbi.org.in/")

def test_contaminated_unfinished_quiz_is_blocked(tmp_path):
    svc, _ = seed(tmp_path/"contaminated.sqlite3"); quiz = svc.generate(payload())
    with svc.sessions() as session:
        question = session.get(CurrentAffairsQuizQuestion, svc.questions(quiz.id)[0].id)
        question.options_json = ["querySelector(document)", "B", "C", "D"]
        session.commit()
    assert not svc.quiz_is_valid(quiz.id)
    with pytest.raises(ValueError, match="invalid extracted source text"):
        svc.submit(quiz.id, [])

def test_invalid_unfinished_quiz_abandon_is_idempotent_and_not_active(tmp_path):
    svc, _ = seed(tmp_path/"abandon.sqlite3"); quiz = svc.generate(payload())
    first = svc.abandon(quiz.id); second = svc.abandon(quiz.id)
    assert first.status == second.status == "abandoned"
    assert second.invalid_reason == "contaminated_source_text"
    assert svc.active_quiz() is None

def test_completed_quiz_cannot_be_abandoned_and_history_is_preserved(tmp_path):
    svc, _ = seed(tmp_path/"completed.sqlite3"); quiz = svc.generate(payload())
    result = svc.submit(quiz.id, answers(svc, quiz))
    with pytest.raises(ValueError, match="cannot be abandoned"):
        svc.abandon(quiz.id)
    assert svc.get(quiz.id).status == "completed"
    assert svc.attempts(quiz.id)[0].id == result["id"]

def test_contaminated_article_is_excluded_from_new_quiz(tmp_path):
    svc, _ = seed(tmp_path/"exclude.sqlite3", 6)
    contaminated_id = "contaminated-official"
    with svc.sessions() as session:
        session.add(CurrentAffairsArticle(id=contaminated_id, title="Subscribe Release Screen Reader Access PIB Delhi PIB Mumbai PIB Hyderabad",
            summary="querySelector('.menu') addEventListener('click', function() {})", source_title="bad",
            publisher="PIB", source_url="https://pib.gov.in/bad", publication_date=date.today(),
            retrieved_at=datetime.now(timezone.utc), subject="Polity", topic="Governance",
            syllabus_tags_json=["GS II"], importance_level="high", relevance_prelims="bad",
            relevance_mains="bad", content_hash="bad-hash", status="active"))
        session.commit()
    quiz = svc.generate(payload(count=5))
    assert contaminated_id not in quiz.article_ids_json
    assert svc.quiz_is_valid(quiz.id)

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
