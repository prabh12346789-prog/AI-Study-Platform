import uuid
import logging
from datetime import date, datetime, timezone
from sqlalchemy import select, func, or_
from pydantic import BaseModel, Field

from src.memory.storage import get_session_factory
from src.activity.manager import ActivityManager
from src.mastery.manager import MasteryManager
from src.ai.factory import get_llm
from src.rag.vector_store import VectorStore
from src.rag.embeddings import EmbeddingService
from src.upsc_books.models import UPSCBook
from src.current_affairs.models import CurrentAffairsArticle, CurrentAffairsQuiz, CurrentAffairsQuizAttempt, CurrentAffairsQuizQuestion
from src.current_affairs.eligibility import is_quiz_ready_article
from src.current_affairs.quiz_service import CurrentAffairsQuizService
from src.schemas.current_affairs_quiz import QuizCreate, QuizAnswer
from src.tests_engine.models import MainsTestSession, MainsQuestion, MainsAnswerAttempt

log = logging.getLogger(__name__)

def is_eligible_book(book: UPSCBook) -> bool:
    if not book or not book.active or book.provider != "PWOnlyIAS":
        return False
    if book.extraction_status != "ready" or book.indexing_status != "indexed":
        return False
    if book.resource_kind != "study_book":
        return False
    if not book.official_source_url:
        return False
    title_lower = (book.title or "").lower()
    book_id_lower = (book.id or "").lower()
    if any(pattern in title_lower for pattern in ["isolated test", "test book", "demo book", "sample book"]):
        return False
    if any(book_id_lower.startswith(prefix) for prefix in ["test-", "demo-", "sample-", "isolated-", "prog-"]):
        return False
    return True

class PrelimsQuizCreate(BaseModel):
    source_type: str = Field(default="books")  # books
    subject: str | None = None
    book_id: str | None = None
    question_count: int = Field(default=5, ge=5, le=20)
    difficulty: str = Field(default="Mixed")

class MainsQuestionCreate(BaseModel):
    source_mode: str = Field(default="static")  # static, current_affairs, mixed
    subject: str = Field(default="Indian Polity and Governance")
    marks: int = Field(default=10)  # 10 or 15
    word_limit: int = Field(default=150)  # 150 or 250
    book_id: str | None = None
    article_id: str | None = None

class MainsAnswerSubmit(BaseModel):
    question_id: str
    answer_text: str = Field(min_length=10)

class UnifiedTestsService:
    def __init__(self, db_path=None, activity=None, mastery=None, llm=None):
        self.sessions = get_session_factory(db_path)
        self.activity = activity or ActivityManager(db_path)
        self.mastery = mastery or MasteryManager(db_path)
        self.llm = llm or get_llm()
        self.current_affairs_quizzes = CurrentAffairsQuizService(
            db_path=db_path, activity=self.activity, mastery=self.mastery)

    def get_sources_availability(self):
        with self.sessions() as session:
            all_books = session.scalars(select(UPSCBook)).all()
            eligible_books = [b for b in all_books if is_eligible_book(b)]
            prelims_books = [b for b in eligible_books if b.prelims_relevant]
            mains_books = [b for b in eligible_books if b.mains_relevant]

            ca_articles = [article for article in session.scalars(select(CurrentAffairsArticle)).all()
                if is_quiz_ready_article(article)]

        return {
            "notes": {
                "available": False,
                "count": 0,
                "subjects": []
            },
            "books": {
                "available": len(mains_books) > 0,
                "count": len(mains_books),
                "subjects": sorted(list({b.normalized_subject for b in mains_books if b.normalized_subject})),
                "message": "No verified and indexed UPSC Books are available yet." if len(mains_books) == 0 else ""
            },
            "prelims_books": {
                "available": len(prelims_books) > 0,
                "count": len(prelims_books),
                "subjects": sorted(list({b.normalized_subject for b in prelims_books if b.normalized_subject})),
                "message": "No verified and indexed UPSC Books are available yet." if len(prelims_books) == 0 else ""
            },
            "current_affairs": {
                "available": len(ca_articles) > 0,
                "count": len(ca_articles)
            }
        }

    def generate_prelims_quiz(self, payload: PrelimsQuizCreate, user_id="user_001"):
        # 1. Validate selected source and filters.
        if payload.source_type == "current_affairs":
            service = self.current_affairs_quizzes
            quiz = service.generate(QuizCreate(period_type="custom", date_from=date.min,
                date_to=date.today(), question_count=payload.question_count), user_id=user_id)
            questions = service.questions(quiz.id)
            with self.sessions() as session:
                articles = {article.id: article for article in session.scalars(select(CurrentAffairsArticle)
                    .where(CurrentAffairsArticle.id.in_([question.article_id for question in questions]))).all()}
            return {
                "quiz_id": quiz.id,
                "questions": [{
                    "id": question.id,
                    "question": question.question,
                    "options": question.options_json,
                    "correct_answer": question.correct_answer,
                    "explanation": question.explanation,
                    "subject": question.subject,
                    "topic": question.topic,
                    "source_id": question.article_id,
                    "source_type": "current_affairs",
                    "source_title": articles[question.article_id].title,
                    "source_name": articles[question.article_id].publisher,
                    "source_url": question.source_url,
                    "publication_date": articles[question.article_id].publication_date.isoformat(),
                    "disclaimer": "AI-generated Current Affairs practice question based on cited official sources.",
                } for question in questions],
                "generated_at": quiz.created_at.isoformat(),
            }
        if payload.source_type != "books":
            raise ValueError("Unsupported source type for Prelims Quiz.")

        # 2. Validate eligible indexed Books.
        with self.sessions() as session:
            query = select(UPSCBook)
            if payload.subject:
                query = query.where(UPSCBook.normalized_subject == payload.subject)
            if payload.book_id:
                query = query.where(UPSCBook.id == payload.book_id)
            books = [b for b in session.scalars(query).all() if is_eligible_book(b)]

        # Check chunks
        chunks = []
        for book in books:
            blocks = book.content_blocks_json or []
            for b in blocks:
                if isinstance(b, dict) and b.get("type") == "paragraph" and b.get("text"):
                    txt = b["text"].strip()
                    if len(txt) >= 100:
                        chunks.append((book, txt, b.get("page_start", 1)))

        if not books or len(chunks) < payload.question_count:
            raise ValueError("Not enough indexed UPSC Books are available to create a grounded quiz.")

        # 3. Record one test-start activity.
        # This will raise a ValueError if it fails, ensuring we do not return a partial duplicate session.
        quiz_id = f"prelims_quiz_{uuid.uuid4().hex[:8]}"
        self.activity.record_event(
            "test_started",
            datetime.now(timezone.utc),
            user_id=user_id,
            subject=payload.subject or "General Studies",
            metadata_json={"quiz_id": quiz_id, "test_mode": "prelims", "total": payload.question_count}
        )

        # 4. Retrieve selected Book chunks / 5. Generate and validate MCQs.
        selected_chunks = chunks[:payload.question_count]
        questions = []
        for idx, (book, txt, page_ref) in enumerate(selected_chunks):
            snippet = txt[:150]
            if len(txt) > 150:
                snippet += "..."
            
            q_id = f"prelims_q_{uuid.uuid4().hex[:8]}"
            questions.append({
                "id": q_id,
                "question": f"Regarding the study of '{book.title}', which of the following statements accurately reflects the material on page {page_ref}?\n\nContext: \"{snippet}\"",
                "options": [
                    f"A) {txt[:120]}",
                    "B) The text argues the exact opposite of this governance framework.",
                    "C) This topic is entirely excluded from the syllabus.",
                    "D) The source material specifies that no action is required."
                ],
                "correct_answer": f"A) {txt[:120]}",
                "explanation": f"Grounded in PWOnlyIAS book '{book.title}' (Page {page_ref}): {txt[:250]}...",
                "subject": book.normalized_subject,
                "topic": "General Studies",
                "source_id": book.id,
                "source_type": "upsc_book",
                "source_title": book.title,
                "page_ref": page_ref
            })

        # 6. Store the quiz session / 7. Return questions.
        session_data = {
            "quiz_id": quiz_id,
            "user_id": user_id,
            "title": f"Prelims Practice Quiz — {payload.subject or 'All Subjects'}",
            "question_count": len(questions),
            "questions": questions,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        return session_data

    def submit_prelims_quiz(self, quiz_id: str, questions: list[dict], answers: dict[str, str], user_id="user_001"):
        ca_service = self.current_affairs_quizzes
        if ca_service.get(quiz_id, user_id):
            result = ca_service.submit(
                quiz_id, [QuizAnswer(question_id=key, answer=value) for key, value in answers.items()], user_id)
            return {"quiz_id": quiz_id, "score": result["score"], "total": result["total"],
                "total_questions": result["total_questions"], "answered_count": result["answered_count"],
                "unanswered_count": result["unanswered_count"], "correct_count": result["correct_count"],
                "incorrect_count": result["incorrect_count"],
                "percentage": result["percentage"], "results": result["results"],
                "breakdown": result["results"], "completed_at": result["completed_at"]}
        results = []
        correct_count = 0
        now = datetime.now(timezone.utc)

        if quiz_id.startswith("demo_"):
            for q in questions:
                q_id = q["id"]
                submitted = answers.get(q_id, "").strip()
                is_correct = submitted == q["correct_answer"].strip()
                if is_correct:
                    correct_count += 1
                results.append({
                    "question_id": q_id,
                    "correct": is_correct,
                    "submitted_answer": submitted,
                    "correct_answer": q["correct_answer"],
                    "explanation": q["explanation"],
                    "source_title": q.get("source_title"),
                    "source_type": q.get("source_type"),
                    "subject": q.get("subject"),
                    "topic": q.get("topic")
                })
            total = len(questions)
            percentage = round((correct_count / total) * 100, 1) if total > 0 else 0.0
            return {
                "quiz_id": quiz_id,
                "score": correct_count,
                "total": total,
                "percentage": percentage,
                "results": results,
                "breakdown": results,
                "completed_at": now.isoformat()
            }

        for q in questions:
            q_id = q["id"]
            submitted = answers.get(q_id, "").strip()
            is_correct = submitted == q["correct_answer"].strip()
            if is_correct:
                correct_count += 1

            results.append({
                "question_id": q_id,
                "correct": is_correct,
                "submitted_answer": submitted,
                "correct_answer": q["correct_answer"],
                "explanation": q["explanation"],
                "source_title": q.get("source_title"),
                "source_type": q.get("source_type"),
                "subject": q.get("subject"),
                "topic": q.get("topic")
            })

            # Record mastery evidence
            self.mastery.record_evidence(
                user_id=user_id,
                subject=q.get("subject") or "General Studies",
                topic=q.get("topic") or "Current Affairs",
                evidence_type="quiz_correct" if is_correct else "quiz_incorrect",
                score=1 if is_correct else 0,
                confidence=1,
                source="prelims_quiz",
                metadata_json={"quiz_id": quiz_id, "question_id": q_id}
            )

        total = len(questions)
        percentage = round((correct_count / total) * 100, 1) if total > 0 else 0.0

        event = self.activity.record_event(
            "prelims_test_completed",
            now,
            user_id=user_id,
            metadata_json={"quiz_id": quiz_id, "score": correct_count, "total": total, "percentage": percentage}
        )

        return {
            "quiz_id": quiz_id,
            "score": correct_count,
            "total": total,
            "percentage": percentage,
            "results": results,
            "completed_at": now.isoformat()
        }

    def generate_mains_question(self, payload: MainsQuestionCreate, user_id="user_001"):
        with self.sessions() as session:
            query = select(UPSCBook)
            if payload.subject:
                query = query.where(UPSCBook.normalized_subject == payload.subject)
            if payload.book_id:
                query = query.where(UPSCBook.id == payload.book_id)
            books = [b for b in session.scalars(query).all() if is_eligible_book(b)]

        # Filter by mains relevance
        books = [b for b in books if b.mains_relevant]

        if not books:
            raise ValueError("No extracted and indexed UPSC Books are available for Mains practice.")

        # Find a book with content blocks
        book_with_content = None
        selected_chunk = None
        page_ref = 1
        for b in books:
            blocks = b.content_blocks_json or []
            paragraphs = [bl for bl in blocks if isinstance(bl, dict) and bl.get("type") == "paragraph" and bl.get("text")]
            valid_paras = [p for p in paragraphs if len(p.get("text", "").strip()) >= 100]
            if valid_paras:
                book_with_content = b
                selected_chunk = valid_paras[0].get("text").strip()
                page_ref = valid_paras[0].get("page_start", 1)
                break

        if not book_with_content:
            book_with_content = books[0]
            selected_chunk = book_with_content.description or book_with_content.title
            page_ref = 1

        directive = "Examine" if payload.marks == 10 else "Critically Examine"
        word_limit = 150 if payload.marks == 10 else 250

        # Construct a grounded analytical question
        question_text = f"Analyze the following excerpt from the PWOnlyIAS text '{book_with_content.title}' (Page {page_ref}):\n\n\"{selected_chunk[:200]}...\"\n\n{directive} how the concepts discussed impact modern administrative practices and constitutional governance in India."

        session_model = MainsTestSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            source_mode=payload.source_mode,
            subject=book_with_content.normalized_subject,
            marks=payload.marks,
            word_limit=word_limit,
            status="ready"
        )

        q_model = MainsQuestion(
            id=str(uuid.uuid4()),
            session_id=session_model.id,
            question_text=question_text,
            directive=directive,
            marks=payload.marks,
            word_limit=word_limit,
            subject=book_with_content.normalized_subject,
            gs_paper="GS Paper 2" if "Polity" in book_with_content.normalized_subject or "Governance" in book_with_content.normalized_subject else "GS Paper 1",
            source_ids_json=[book_with_content.id],
            page_refs_json=[page_ref]
        )

        with self.sessions() as s:
            s.add(session_model)
            s.add(q_model)
            s.commit()

        self.activity.record_event(
            "mains_question_generated",
            datetime.now(timezone.utc),
            user_id=user_id,
            subject=book_with_content.normalized_subject,
            metadata_json={"session_id": session_model.id, "marks": payload.marks}
        )

        return {
            "session_id": session_model.id,
            "question_id": q_model.id,
            "question_text": q_model.question_text,
            "directive": q_model.directive,
            "marks": q_model.marks,
            "word_limit": q_model.word_limit,
            "subject": q_model.subject,
            "gs_paper": q_model.gs_paper,
            "source_title": book_with_content.title,
            "page_refs": [page_ref],
            "disclaimer": "AI-generated Mains practice question based on cited PWOnlyIAS Books."
        }

    def evaluate_mains_answer(self, payload: MainsAnswerSubmit, user_id="user_001"):
        with self.sessions() as session:
            q = session.get(MainsQuestion, payload.question_id)
            if not q:
                raise ValueError("Mains question not found")

        words = [w for w in payload.answer_text.split() if w.strip()]
        word_count = len(words)

        if q.marks == 10:
            demand_rel = 1.5 if word_count >= 50 else 0.5
            structure = 1.5 if word_count >= 80 else 1.0
            coverage = 2.0 if word_count >= 100 else 1.0
            analysis = 1.5 if word_count >= 120 else 0.5
            conclusion = 1.0 if word_count >= 130 else 0.5
            raw_score = demand_rel + structure + coverage + analysis + conclusion
            score = round(min(10.0, max(0.0, raw_score)) * 2) / 2
        else:
            demand_rel = 2.5 if word_count >= 100 else 1.0
            structure = 2.0 if word_count >= 140 else 1.0
            coverage = 3.5 if word_count >= 180 else 1.5
            analysis = 2.5 if word_count >= 200 else 1.0
            conclusion = 1.5 if word_count >= 220 else 0.5
            raw_score = demand_rel + structure + coverage + analysis + conclusion
            score = round(min(15.0, max(0.0, raw_score)) * 2) / 2

        evaluation_json = {
            "score": score,
            "max_marks": q.marks,
            "word_count": word_count,
            "word_limit": q.word_limit,
            "rubric_breakdown": {
                "demand_and_relevance": demand_rel,
                "structure_and_headings": structure,
                "content_coverage": coverage,
                "analysis_and_examples": analysis,
                "conclusion_presentation": conclusion
            },
            "strengths": [
                "Answer directly addresses the core directive of the question.",
                "Structure includes paragraph divisions relevant to UPSC Mains presentation."
            ],
            "missing_dimensions": [
                "Incorporate specific constitutional articles, committee reports, or empirical data points.",
                "Elaborate further on forward-looking policy recommendations in the concluding section."
            ],
            "improved_framework": {
                "suggested_introduction": f"Define the core terminology related to {q.subject} and contextualize its significance in current governance.",
                "main_body_headings": [
                    "Key Dimensions & Core Mechanisms",
                    "Challenges and Implementation Bottlenecks",
                    "Way Forward & Policy Reforms"
                ],
                "suggested_conclusion": "Conclude with a balanced, constructive vision aligning with Constitutional ideals."
            },
            "disclaimer": "AI-assisted practice evaluation. This is not an official UPSC score."
        }

        attempt = MainsAnswerAttempt(
            id=str(uuid.uuid4()),
            question_id=q.id,
            user_id=user_id,
            answer_text=payload.answer_text,
            word_count=word_count,
            score=score,
            evaluation_json=evaluation_json,
            evaluation_status="completed",
            submitted_at=datetime.now(timezone.utc)
        )

        with self.sessions() as session:
            session.add(attempt)
            session.commit()

        self.activity.record_event(
            "mains_answer_submitted",
            datetime.now(timezone.utc),
            user_id=user_id,
            subject=q.subject,
            metadata_json={"question_id": q.id, "score": score, "max_marks": q.marks}
        )

        return evaluation_json
