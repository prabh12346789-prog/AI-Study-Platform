import re
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select

from src.activity.manager import ActivityManager
from src.current_affairs.models import (CurrentAffairsArticle, CurrentAffairsQuiz, CurrentAffairsQuizAttempt,
    CurrentAffairsQuizQuestion, CurrentAffairsRetention, SavedCurrentAffairs)
from src.current_affairs.eligibility import is_quiz_ready_article
from src.current_affairs.sanitizer import is_safe_quiz_text, sanitize_current_affairs_text
from src.mastery.manager import MasteryManager
from src.memory.storage import get_session_factory

class CurrentAffairsQuizService:
    def __init__(self, db_path=None, activity=None, mastery=None):
        self.sessions = get_session_factory(db_path); self.activity = activity or ActivityManager(db_path)
        self.mastery = mastery or MasteryManager(db_path)

    @staticmethod
    def _norm(value): return " ".join(str(value).casefold().split())

    def _articles(self, start, end):
        with self.sessions() as session:
            rows = list(session.scalars(select(CurrentAffairsArticle).where(
                CurrentAffairsArticle.publication_date >= start, CurrentAffairsArticle.publication_date <= end)
                .order_by(CurrentAffairsArticle.indexed_at.desc().nullslast(),
                    CurrentAffairsArticle.publication_date.desc(), CurrentAffairsArticle.subject)))
        return [article for article in rows if is_quiz_ready_article(article)]

    @staticmethod
    def _clean_article(article):
        title = sanitize_current_affairs_text(article.title, max_length=180)
        summary = sanitize_current_affairs_text(article.summary, max_length=280)
        summary = re.sub(r"^What happened:\s*", "", summary, flags=re.I).strip()
        return (article, title, summary) if title and summary else None

    @staticmethod
    def question_is_valid(question: CurrentAffairsQuizQuestion) -> bool:
        options = question.options_json or []
        return (
            is_safe_quiz_text(question.question, max_length=500)
            and is_safe_quiz_text(question.explanation, max_length=700)
            and len(options) == 4
            and len({option.casefold().strip() for option in options}) == 4
            and all(is_safe_quiz_text(option, max_length=180) for option in options)
            and question.correct_answer in options
        )

    def quiz_is_valid(self, quiz_id: str) -> bool:
        questions = self.questions(quiz_id)
        return bool(questions) and all(self.question_is_valid(question) for question in questions)

    def generate(self, payload, user_id="user_001"):
        today = date.today(); end = payload.date_to or today
        start = payload.date_from or (end - timedelta(days=6) if payload.period_type == "weekly" else end)
        if start > end: raise ValueError("date_from must not be after date_to")
        count = payload.question_count or (10 if payload.period_type == "weekly" else 5)
        articles = self._articles(start, end)
        
        clean_articles = [clean for article in articles if (clean := self._clean_article(article))]
        titles = list(dict.fromkeys(title for _, title, _ in clean_articles))
        if len(titles) < 4:
            raise ValueError("Insufficient clean official Current Affairs content for a four-option quiz")
        questions, seen = [], set()
        for article, title, summary in clean_articles:
            if len(questions) >= count: break
            options = [title, *[candidate for candidate in titles if candidate != title][:3]]
            answer = title
            text = f'Which official article is described by this summary: "{summary}"?'
            key = self._norm(text)
            if key in seen: continue
            candidate = CurrentAffairsQuizQuestion(id=str(uuid.uuid4()), quiz_id="", question_type="mcq",
                question=text, options_json=options, correct_answer=answer,
                explanation=f"Grounded in the official {article.publisher} article published on {article.publication_date.isoformat()}: {summary}",
                article_id=article.id, source_url=article.source_url, subject=article.subject,
                topic=article.topic, difficulty=payload.difficulty)
            if not self.question_is_valid(candidate):
                continue
            seen.add(key); questions.append(candidate)
        if not questions:
            raise ValueError("No clean Current Affairs questions could be generated")
        count = len(questions)
        quiz = CurrentAffairsQuiz(id=str(uuid.uuid4()), user_id=user_id, title=f"{payload.period_type.title()} Current Affairs Quiz",
            period_type=payload.period_type, date_from=start, date_to=end, question_count=count, difficulty=payload.difficulty,
            status="ready", article_ids_json=list(dict.fromkeys(q.article_id for q in questions)))
        for question in questions: question.quiz_id = quiz.id
        with self.sessions() as session: session.add(quiz); session.add_all(questions); session.commit(); session.refresh(quiz)
        self.activity.record_event("current_affairs_quiz_started", datetime.now(timezone.utc), user_id=user_id,
            metadata_json={"quiz_id": quiz.id, "period_type": quiz.period_type, "total": count})
        return quiz

    def get(self, quiz_id, user_id="user_001"):
        with self.sessions() as session:
            return session.scalar(select(CurrentAffairsQuiz).where(CurrentAffairsQuiz.id == quiz_id, CurrentAffairsQuiz.user_id == user_id))

    def questions(self, quiz_id):
        with self.sessions() as session: return list(session.scalars(select(CurrentAffairsQuizQuestion).where(CurrentAffairsQuizQuestion.quiz_id == quiz_id)))

    def list(self, user_id="user_001"):
        with self.sessions() as session: return list(session.scalars(select(CurrentAffairsQuiz).where(CurrentAffairsQuiz.user_id == user_id).order_by(CurrentAffairsQuiz.created_at.desc())))

    def active_quiz(self, user_id="user_001"):
        with self.sessions() as session:
            rows = list(session.scalars(select(CurrentAffairsQuiz).where(
                CurrentAffairsQuiz.user_id == user_id, CurrentAffairsQuiz.status == "ready")
                .order_by(CurrentAffairsQuiz.created_at.desc())))
            completed_ids = set(session.scalars(select(CurrentAffairsQuizAttempt.quiz_id).where(
                CurrentAffairsQuizAttempt.user_id == user_id)))
        return next((row for row in rows if row.id not in completed_ids and self.quiz_is_valid(row.id)), None)

    def abandon(self, quiz_id, user_id="user_001", reason="contaminated_source_text"):
        with self.sessions() as session:
            quiz = session.scalar(select(CurrentAffairsQuiz).where(
                CurrentAffairsQuiz.id == quiz_id, CurrentAffairsQuiz.user_id == user_id))
            if not quiz:
                raise ValueError("Current Affairs quiz not found")
            if quiz.status == "abandoned":
                return quiz
            attempt = session.scalar(select(CurrentAffairsQuizAttempt).where(
                CurrentAffairsQuizAttempt.quiz_id == quiz_id,
                CurrentAffairsQuizAttempt.user_id == user_id))
            if attempt or quiz.status == "completed":
                raise ValueError("Completed Current Affairs quizzes cannot be abandoned")
            quiz.status = "abandoned"
            quiz.invalid_reason = reason
            session.commit(); session.refresh(quiz)
            return quiz

    def submit(self, quiz_id, answers, user_id="user_001"):
        if quiz_id.startswith("demo-"):
            submitted = {}
            for item in answers:
                if hasattr(item, "question_id"):
                    submitted[item.question_id] = item.answer
                else:
                    submitted[item.get("question_id")] = item.get("answer")
            results = []
            for question in self.questions(quiz_id):
                answer = submitted.get(question.id, "")
                correct = self._norm(answer) == self._norm(question.correct_answer)
                results.append({"question_id": question.id, "correct": correct, "submitted_answer": answer,
                    "correct_answer": question.correct_answer, "explanation": question.explanation,
                    "article_id": question.article_id, "source_url": question.source_url, "topic": question.topic})
            score, total = sum(item["correct"] for item in results), len(results)
            percentage = round(score / total * 100, 1) if total > 0 else 0.0
            return {
                "id": f"demo-ca-attempt-{uuid.uuid4().hex[:8]}",
                "quiz_id": quiz_id,
                "score": score,
                "total": total,
                "percentage": percentage,
                "results": results,
                "weak_article_ids": [],
                "weak_topics": [],
                "completed_at": datetime.now(timezone.utc)
            }

        quiz = self.get(quiz_id, user_id)
        if not quiz: raise ValueError("Current Affairs quiz not found")
        with self.sessions() as session:
            existing = session.scalar(select(CurrentAffairsQuizAttempt).where(CurrentAffairsQuizAttempt.quiz_id == quiz_id, CurrentAffairsQuizAttempt.user_id == user_id))
            if existing: return self._attempt_result(existing)
        questions = self.questions(quiz_id)
        if not questions or not all(self.question_is_valid(question) for question in questions):
            raise ValueError("This quiz contains invalid extracted source text. Please generate a new quiz.")
        answer_ids = [item.question_id for item in answers]
        if len(answer_ids) != len(set(answer_ids)):
            raise ValueError("Duplicate question IDs are not allowed")
        if set(answer_ids) - {question.id for question in questions}:
            raise ValueError("Submitted question IDs do not belong to this quiz")
        submitted = {item.question_id: item.answer for item in answers}; results = []; weak_articles = set(); weak_topics = set()
        for question in questions:
            answer = submitted.get(question.id)
            correct = answer is not None and self._norm(answer) == self._norm(question.correct_answer)
            status = "correct" if correct else "unanswered" if answer is None else "incorrect"
            results.append({"question_id": question.id, "correct": correct, "status": status,
                "selected_answer": answer, "submitted_answer": answer,
                "correct_answer": question.correct_answer, "explanation": question.explanation,
                "article_id": question.article_id, "source_url": question.source_url, "topic": question.topic})
            if not correct: weak_articles.add(question.article_id); weak_topics.add(question.topic)
        score, total = sum(item["correct"] for item in results), len(results); now = datetime.now(timezone.utc)
        attempt = CurrentAffairsQuizAttempt(id=str(uuid.uuid4()), user_id=user_id, quiz_id=quiz_id, score=score, total=total,
            percentage=round(score / total * 100, 1), submitted_answers_json=results,
            weak_article_ids_json=sorted(weak_articles), weak_topics_json=sorted(weak_topics), completed_at=now)
        with self.sessions() as session:
            session.add(attempt)
            stored_quiz = session.get(CurrentAffairsQuiz, quiz_id)
            stored_quiz.status = "completed"
            session.commit(); session.refresh(attempt)
        event = self.activity.record_event("current_affairs_quiz_completed", now, user_id=user_id,
            metadata_json={"quiz_id": quiz_id, "score": score, "total": total, "percentage": attempt.percentage})
        for item in results:
            question = next(q for q in self.questions(quiz_id) if q.id == item["question_id"])
            self.mastery.record_evidence(user_id=user_id, subject=question.subject, topic=question.topic,
                evidence_type="quiz_correct" if item["correct"] else "quiz_incorrect", score=1 if item["correct"] else 0,
                confidence=1, source="current_affairs_quiz", metadata_json={"quiz_id": quiz_id, "article_id": question.article_id},
                source_activity_event_id=f"{event.id}:{question.id}")
            self._update_retention(question, item["correct"], user_id, now)
        return self._attempt_result(attempt)

    @staticmethod
    def _attempt_result(row):
        results = row.submitted_answers_json
        answered = sum(item.get("status") != "unanswered" and item.get("submitted_answer") not in (None, "") for item in results)
        return {"id": row.id, "quiz_id": row.quiz_id, "score": row.score, "total": row.total,
            "total_questions": row.total, "answered_count": answered, "unanswered_count": row.total - answered,
            "correct_count": row.score, "incorrect_count": row.total - row.score,
            "percentage": row.percentage, "results": results,
            "weak_article_ids": row.weak_article_ids_json, "weak_topics": row.weak_topics_json, "completed_at": row.completed_at}

    def _update_retention(self, question, correct, user_id, now):
        with self.sessions() as session:
            row = session.scalar(select(CurrentAffairsRetention).where(CurrentAffairsRetention.user_id == user_id,
                CurrentAffairsRetention.article_id == question.article_id))
            if not row: row = CurrentAffairsRetention(id=str(uuid.uuid4()), user_id=user_id, article_id=question.article_id,
                subject=question.subject, topic=question.topic, retention_score=.5, correct_attempts=0,
                incorrect_attempts=0, recall_failures=0, risk_level="medium"); session.add(row)
            row.retention_score = max(0, min(1, row.retention_score + (.08 if correct else -.12)))
            row.correct_attempts += int(correct); row.incorrect_attempts += int(not correct); row.recall_failures += int(not correct)
            row.last_attempt_at = now; self._schedule(row, now); session.commit()

    @staticmethod
    def _schedule(row, basis):
        row.risk_level = "high" if row.retention_score < .4 else "medium" if row.retention_score < .7 else "low"
        row.next_revision_at = basis + timedelta(days=2 if row.risk_level == "high" else 7 if row.risk_level == "medium" else 14)

    def retention(self, user_id="user_001"):
        with self.sessions() as session: return list(session.scalars(select(CurrentAffairsRetention).where(CurrentAffairsRetention.user_id == user_id).order_by(CurrentAffairsRetention.retention_score)))

    def overview(self, user_id="user_001"):
        rows = self.retention(user_id); now = datetime.now(timezone.utc); subjects = defaultdict(list)
        for row in rows: subjects[row.subject].append(row.retention_score)
        with self.sessions() as session:
            saved = list(session.scalars(select(SavedCurrentAffairs).where(SavedCurrentAffairs.user_id == user_id)))
        tested = {row.article_id for row in rows}
        attempts = self.attempts(None, user_id)
        return {"average_retention": sum(r.retention_score for r in rows)/len(rows) if rows else .5,
            "high_risk_articles": [r for r in rows if r.risk_level == "high"],
            "due_for_revision": [r for r in rows if r.next_revision_at and r.next_revision_at.replace(tzinfo=timezone.utc) <= now],
            "weak_subjects": [{"subject": k, "score": sum(v)/len(v)} for k,v in subjects.items() if sum(v)/len(v) < .6],
            "weekly_trend": [{"date": a.completed_at.date(), "percentage": a.percentage} for a in attempts[:7]],
            "saved_but_unrevised_article_ids": [s.article_id for s in saved if s.article_id not in tested]}

    def revise(self, article_id, user_id="user_001"):
        with self.sessions() as session:
            article = session.get(CurrentAffairsArticle, article_id)
            if not article or article.status != "active": raise ValueError("Accepted Current Affairs article not found")
            row = session.scalar(select(CurrentAffairsRetention).where(CurrentAffairsRetention.user_id == user_id, CurrentAffairsRetention.article_id == article_id))
            if not row: row = CurrentAffairsRetention(id=str(uuid.uuid4()), user_id=user_id, article_id=article.id,
                subject=article.subject, topic=article.topic, retention_score=.5, correct_attempts=0,
                incorrect_attempts=0, recall_failures=0, risk_level="medium"); session.add(row)
            now = datetime.now(timezone.utc); row.last_revised_at = now; row.retention_score = min(1, row.retention_score + .04); self._schedule(row, now); session.commit(); session.refresh(row)
        self.activity.record_event("current_affairs_revision_completed", now, user_id=user_id, subject=row.subject, topic=row.topic, metadata_json={"article_id": article_id})
        return row

    def attempts(self, quiz_id=None, user_id="user_001"):
        with self.sessions() as session:
            query = select(CurrentAffairsQuizAttempt).where(CurrentAffairsQuizAttempt.user_id == user_id)
            if quiz_id: query = query.where(CurrentAffairsQuizAttempt.quiz_id == quiz_id)
            return list(session.scalars(query.order_by(CurrentAffairsQuizAttempt.completed_at.desc())))
