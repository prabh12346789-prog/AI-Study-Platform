import re
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select

from src.activity.manager import ActivityManager
from src.current_affairs.models import (CurrentAffairsArticle, CurrentAffairsQuiz, CurrentAffairsQuizAttempt,
    CurrentAffairsQuizQuestion, CurrentAffairsRetention, SavedCurrentAffairs)
from src.mastery.manager import MasteryManager
from src.memory.storage import get_session_factory

class CurrentAffairsQuizService:
    _demo_quizzes = {}

    def __init__(self, db_path=None, activity=None, mastery=None):
        self.sessions = get_session_factory(db_path); self.activity = activity or ActivityManager(db_path)
        self.mastery = mastery or MasteryManager(db_path)

    @staticmethod
    def _norm(value): return " ".join(str(value).casefold().split())

    def _articles(self, start, end):
        with self.sessions() as session:
            return list(session.scalars(select(CurrentAffairsArticle).where(CurrentAffairsArticle.status == "active",
                CurrentAffairsArticle.extraction_status.notin_(["image_only", "unavailable", "failed"]),
                CurrentAffairsArticle.publication_date >= start, CurrentAffairsArticle.publication_date <= end)
                .order_by(CurrentAffairsArticle.importance_level.desc(), CurrentAffairsArticle.publication_date.desc())))

    @staticmethod
    def _facts(article):
        facts = [line.strip(" -•") for line in article.relevance_prelims.splitlines() if len(line.strip()) >= 12]
        core = re.sub(r"^(What happened:\s*)", "", article.summary.splitlines()[0], flags=re.I).strip()
        return list(dict.fromkeys([core, *facts, article.relevance_mains.strip()]))

    def generate(self, payload, user_id="user_001"):
        from src.core.config import settings
        is_demo = getattr(settings, "REPORT_DEMO_MODE", False)
        today = date.today(); end = payload.date_to or today
        start = payload.date_from or (end - timedelta(days=6) if payload.period_type == "weekly" else end)
        if start > end: raise ValueError("date_from must not be after date_to")
        count = payload.question_count or (10 if payload.period_type == "weekly" else 5)
        articles = self._articles(start, end); pool = [(article, fact) for article in articles for fact in self._facts(article) if fact]
        
        if is_demo and (not pool or len(pool) < count):
            # Create in-memory demo quiz
            quiz = CurrentAffairsQuiz(
                id=f"demo-ca-quiz-{uuid.uuid4().hex[:8]}",
                user_id=user_id,
                title=f"[Demo Data] {payload.period_type.title()} Current Affairs Quiz",
                period_type=payload.period_type,
                date_from=start,
                date_to=end,
                question_count=count,
                difficulty=payload.difficulty,
                status="ready",
                article_ids_json=["dmy-art-001"],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            mock_questions = []
            for i in range(count):
                q = CurrentAffairsQuizQuestion(
                    id=f"demo-ca-q-{i}",
                    quiz_id=quiz.id,
                    question_type="mcq",
                    question=f"[Demo Data] Regarding the recent India-France Bilateral Trade Agreement (2026), what is the target year to double the trade volume?",
                    options_json=["A) 2030", "B) 2028", "C) 2035", "D) 2040"],
                    correct_answer="A) 2030",
                    explanation="[Demo Data] The agreement aims to double the bilateral trade volume between India and France by 2030.",
                    article_id="dmy-art-001",
                    source_url="https://pib.gov.in/dummy-1",
                    subject="International Relations",
                    topic="Bilateral Relations",
                    difficulty=payload.difficulty
                )
                mock_questions.append(q)
            self._demo_quizzes[quiz.id] = (quiz, mock_questions)
            return quiz

        if len(pool) < count: raise ValueError("Insufficient accepted Current Affairs content for the requested quiz")
        questions, seen = [], set(); types = ["mcq", "true_false", "statement_based", "short_recall"]
        titles = [article.title for article in articles]
        for article, fact in pool:
            if len(questions) >= count: break
            kind = types[len(questions) % len(types)]
            if kind == "mcq" and len(titles) >= 2:
                text = f"Which accepted article is associated with this grounded fact: {fact}"
                options = list(dict.fromkeys([article.title, *[title for title in titles if title != article.title]]))[:4]
                answer = article.title
            elif kind == "true_false": text, options, answer = f"True or false: {fact}", ["True", "False"], "True"
            elif kind == "statement_based": text, options, answer = f"Identify the accepted source statement for {article.topic}.", [fact], fact
            else: text, options, answer = f"Recall the key accepted fact from “{article.title}”.", [], fact
            key = self._norm(text)
            if key in seen: continue
            seen.add(key); questions.append(CurrentAffairsQuizQuestion(id=str(uuid.uuid4()), quiz_id="", question_type=kind,
                question=text, options_json=options, correct_answer=answer,
                explanation=f"AI-generated practice quiz based on the cited PWOnlyIAS source ({article.publisher}): {fact}", article_id=article.id, source_url=article.source_url,
                subject=article.subject, topic=article.topic, difficulty=payload.difficulty))
        if len(questions) < count: raise ValueError("Insufficient distinct accepted Current Affairs content for the requested quiz")
        quiz = CurrentAffairsQuiz(id=str(uuid.uuid4()), user_id=user_id, title=f"{payload.period_type.title()} Current Affairs Quiz",
            period_type=payload.period_type, date_from=start, date_to=end, question_count=count, difficulty=payload.difficulty,
            status="ready", article_ids_json=list(dict.fromkeys(q.article_id for q in questions)))
        for question in questions: question.quiz_id = quiz.id
        with self.sessions() as session: session.add(quiz); session.add_all(questions); session.commit(); session.refresh(quiz)
        self.activity.record_event("current_affairs_quiz_started", datetime.now(timezone.utc), user_id=user_id,
            metadata_json={"quiz_id": quiz.id, "period_type": quiz.period_type, "total": count})
        return quiz

    def get(self, quiz_id, user_id="user_001"):
        if quiz_id.startswith("demo-"):
            return self._demo_quizzes.get(quiz_id)[0] if quiz_id in self._demo_quizzes else None
        with self.sessions() as session:
            return session.scalar(select(CurrentAffairsQuiz).where(CurrentAffairsQuiz.id == quiz_id, CurrentAffairsQuiz.user_id == user_id))

    def questions(self, quiz_id):
        if quiz_id.startswith("demo-"):
            return self._demo_quizzes.get(quiz_id)[1] if quiz_id in self._demo_quizzes else []
        with self.sessions() as session: return list(session.scalars(select(CurrentAffairsQuizQuestion).where(CurrentAffairsQuizQuestion.quiz_id == quiz_id)))

    def list(self, user_id="user_001"):
        with self.sessions() as session: return list(session.scalars(select(CurrentAffairsQuiz).where(CurrentAffairsQuiz.user_id == user_id).order_by(CurrentAffairsQuiz.created_at.desc())))

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
        submitted = {item.question_id: item.answer for item in answers}; results = []; weak_articles = set(); weak_topics = set()
        for question in self.questions(quiz_id):
            answer = submitted.get(question.id, ""); correct = self._norm(answer) == self._norm(question.correct_answer)
            results.append({"question_id": question.id, "correct": correct, "submitted_answer": answer,
                "correct_answer": question.correct_answer, "explanation": question.explanation,
                "article_id": question.article_id, "source_url": question.source_url, "topic": question.topic})
            if not correct: weak_articles.add(question.article_id); weak_topics.add(question.topic)
        score, total = sum(item["correct"] for item in results), len(results); now = datetime.now(timezone.utc)
        attempt = CurrentAffairsQuizAttempt(id=str(uuid.uuid4()), user_id=user_id, quiz_id=quiz_id, score=score, total=total,
            percentage=round(score / total * 100, 1), submitted_answers_json=results,
            weak_article_ids_json=sorted(weak_articles), weak_topics_json=sorted(weak_topics), completed_at=now)
        with self.sessions() as session: session.add(attempt); session.commit(); session.refresh(attempt)
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
        return {"id": row.id, "quiz_id": row.quiz_id, "score": row.score, "total": row.total,
            "percentage": row.percentage, "results": row.submitted_answers_json,
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
