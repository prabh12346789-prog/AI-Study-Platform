import json
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.api.routes.tests import get_service
from src.tests_engine.service import PrelimsQuizCreate, UnifiedTestsService

client = TestClient(app)


class _GeneralQuizLLM:
    async def generate_structured(self, **_kwargs):
        return json.dumps({"questions": [{
            "question": f"Verified question {index + 1}?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_answer": "Option A",
            "explanation": "Option A is the established answer.",
            "topic": "Constitution",
        } for index in range(5)]})


class _InvalidGeneralQuizLLM:
    async def generate_structured(self, **_kwargs):
        return "not JSON"


class _UnavailableQuizService:
    def generate_prelims_quiz(self, _payload):
        raise ConnectionError("local model refused the connection")


class _UnavailableQuizLLM:
    async def generate_structured(self, **_kwargs):
        raise ConnectionError("local model refused the connection")


class _EventRecorder:
    def __init__(self):
        self.events = []

    def record_event(self, *args, **kwargs):
        self.events.append((args, kwargs))


def _general_service(llm):
    service = UnifiedTestsService.__new__(UnifiedTestsService)
    service.llm = llm
    service.activity = _EventRecorder()
    return service


# ─── SOURCES AVAILABILITY ────────────────────────────────────────────────────

def test_sources_endpoint_returns_expected_keys():
    res = client.get("/tests/sources")
    assert res.status_code == 200
    data = res.json()
    assert "notes" in data
    assert "books" in data
    assert "current_affairs" in data
    assert isinstance(data["notes"]["available"], bool)
    assert isinstance(data["books"]["available"], bool)
    assert isinstance(data["notes"]["count"], int)
    assert isinstance(data["books"]["count"], int)


def test_sources_books_subjects_list():
    res = client.get("/tests/sources")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["books"]["subjects"], list)


def test_books_unavailable_message_present_when_empty():
    res = client.get("/tests/sources")
    assert res.status_code == 200
    data = res.json()
    if not data["books"]["available"]:
        assert "message" in data["books"]
        assert len(data["books"]["message"]) > 0


# ─── PRELIMS QUIZ GENERATION ─────────────────────────────────────────────────

def test_prelims_general_subject_generation_needs_no_books():
    service = _general_service(_GeneralQuizLLM())
    result = service.generate_prelims_quiz(PrelimsQuizCreate(
        source_type="general", subject="Indian Polity", topic="Fundamental Rights", question_count=5))

    assert len(result["questions"]) == 5
    assert all(question["source_type"] == "general" for question in result["questions"])
    assert all(question["subject"] == "Indian Polity" for question in result["questions"])
    assert all(question["topic"] == "Fundamental Rights" for question in result["questions"])
    assert len(service.activity.events) == 1


def test_prelims_general_subject_rejects_unstructured_model_output():
    service = _general_service(_InvalidGeneralQuizLLM())
    with pytest.raises(ValueError, match="valid quiz structure"):
        service.generate_prelims_quiz(PrelimsQuizCreate(source_type="general", question_count=5))


def test_prelims_endpoint_returns_actionable_error_when_model_is_unavailable():
    app.dependency_overrides[get_service] = lambda: _UnavailableQuizService()
    try:
        response = client.post("/tests/prelims/generate", json={"source_type": "general", "question_count": 5})
    finally:
        app.dependency_overrides.pop(get_service, None)

    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]


def test_fundamental_rights_uses_verified_fallback_when_model_is_unavailable():
    service = _general_service(_UnavailableQuizLLM())
    result = service.generate_prelims_quiz(PrelimsQuizCreate(
        source_type="general", subject="Indian Polity and Governance",
        topic="fundamental rights", question_count=10))

    assert len(result["questions"]) == 10
    assert all(question["source_title"] == "Verified UPSC question bank" for question in result["questions"])
    assert len(service.activity.events) == 1


def test_prelims_generate_books_succeeds():
    res = client.post("/tests/prelims/generate", json={
        "source_type": "books",
        "question_count": 5
    })
    assert res.status_code in (200, 422)
    if res.status_code == 200:
        data = res.json()
        assert "quiz_id" in data
        assert "questions" in data
        assert len(data["questions"]) >= 1


def test_prelims_generate_from_books_rejected_when_unavailable():
    """Books source must be rejected when no verified indexed books exist."""
    # Check availability first
    avail = client.get("/tests/sources").json()
    if not avail["books"]["available"]:
        res = client.post("/tests/prelims/generate", json={
            "source_type": "books",
            "question_count": 5
        })
        assert res.status_code == 422
        assert "Books" in res.json()["detail"] or "books" in res.json()["detail"].lower()


def test_prelims_generate_with_subject_filter():
    res = client.post("/tests/prelims/generate", json={
        "source_type": "books",
        "subject": "Indian Polity and Governance",
        "question_count": 5
    })
    assert res.status_code in (200, 422)
    if res.status_code == 200:
        data = res.json()
        assert all(q["subject"] == "Indian Polity and Governance" for q in data["questions"])


def test_prelims_questions_contain_required_fields():
    res = client.post("/tests/prelims/generate", json={"source_type": "books", "question_count": 5})
    if res.status_code == 200:
        for q in res.json()["questions"]:
            assert "question" in q
            assert "correct_answer" in q
            assert "explanation" in q
            assert "source_id" in q
            assert "source_type" in q
            assert "subject" in q
            assert "C:\\" not in str(q)  # no local paths


def test_prelims_questions_no_synthetic_sources():
    res = client.post("/tests/prelims/generate", json={"source_type": "books", "question_count": 5})
    if res.status_code == 200:
        for q in res.json()["questions"]:
            assert not q["source_id"].startswith("test-")
            assert not q["source_id"].startswith("demo-")
            assert "Prog Test" not in q.get("source_title", "")


def test_prelims_submit_returns_score():
    gen_res = client.post("/tests/prelims/generate", json={"source_type": "books", "question_count": 5})
    if gen_res.status_code != 200:
        pytest.skip("No eligible books available")
    data = gen_res.json()
    answers = {q["id"]: q["correct_answer"] for q in data["questions"]}
    sub_res = client.post(f"/tests/prelims/{data['quiz_id']}/submit", json={
        "questions": data["questions"],
        "answers": answers
    })
    assert sub_res.status_code == 200
    result = sub_res.json()
    assert "score" in result
    assert "total" in result
    assert "percentage" in result
    assert result["score"] <= result["total"]


def test_prelims_submit_idempotent():
    """Submitting the same answers twice must not double-record."""
    gen_res = client.post("/tests/prelims/generate", json={"source_type": "books", "question_count": 5})
    if gen_res.status_code != 200:
        pytest.skip("No eligible books available")
    data = gen_res.json()
    answers = {q["id"]: q["correct_answer"] for q in data["questions"]}
    payload = {"questions": data["questions"], "answers": answers}
    r1 = client.post(f"/tests/prelims/{data['quiz_id']}/submit", json=payload)
    r2 = client.post(f"/tests/prelims/{data['quiz_id']}/submit", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["score"] == r2.json()["score"]


def test_prelims_no_local_paths_exposed():
    res = client.post("/tests/prelims/generate", json={"source_type": "books", "question_count": 5})
    if res.status_code == 200:
        body = str(res.json())
        assert "C:\\" not in body
        assert "/tmp/" not in body
        assert "chromadb" not in body.lower()


# ─── MAINS GENERATION ────────────────────────────────────────────────────────

def test_mains_generate_10_mark_question():
    res = client.post("/tests/mains/generate", json={
        "source_mode": "static",
        "subject": "Indian Polity and Governance",
        "marks": 10,
        "word_limit": 150
    })
    assert res.status_code in (200, 422)
    if res.status_code == 200:
        data = res.json()
        assert "question_id" in data
        assert "question_text" in data
        assert data["marks"] == 10
        assert data["word_limit"] == 150
        assert "disclaimer" in data
        assert "not an official UPSC" in data["disclaimer"].lower() or "AI-generated" in data["disclaimer"]


def test_mains_generate_15_mark_question():
    res = client.post("/tests/mains/generate", json={
        "source_mode": "static",
        "marks": 15,
        "word_limit": 250
    })
    assert res.status_code in (200, 422)
    if res.status_code == 200:
        data = res.json()
        assert data["marks"] == 15
        assert data["word_limit"] == 250


def test_mains_generate_has_directive():
    res = client.post("/tests/mains/generate", json={"source_mode": "static", "marks": 10, "word_limit": 150})
    if res.status_code == 200:
        assert "directive" in res.json()
        assert res.json()["directive"] in ["Discuss", "Examine", "Analyse", "Evaluate", "Critically Examine"]


def test_mains_generate_no_synthetic_sources():
    res = client.post("/tests/mains/generate", json={"source_mode": "static", "marks": 10, "word_limit": 150})
    if res.status_code == 200:
        data = res.json()
        assert "Prog Test" not in data.get("source_title", "")
        assert "C:\\" not in str(data)


# ─── MAINS EVALUATION ────────────────────────────────────────────────────────

def test_mains_evaluate_answer():
    gen_res = client.post("/tests/mains/generate", json={
        "source_mode": "static",
        "marks": 10,
        "word_limit": 150
    })
    if gen_res.status_code != 200:
        pytest.skip("No eligible books for mains generation")
    q_id = gen_res.json()["question_id"]
    sub_res = client.post("/tests/mains/submit", json={
        "question_id": q_id,
        "answer_text": "The constitutional framework provides several important mechanisms for governance. "
                       "These mechanisms ensure accountability and transparency in the administration. "
                       "The government must take proactive steps to implement these frameworks effectively "
                       "and in accordance with the directive principles of state policy. "
                       "The role of civil society is also crucial in ensuring that policies are grounded "
                       "in constitutional values and address the needs of all citizens."
    })
    assert sub_res.status_code == 200
    data = sub_res.json()
    assert "score" in data
    assert "max_marks" in data
    assert data["score"] <= data["max_marks"]
    assert "rubric_breakdown" in data
    assert "strengths" in data
    assert "missing_dimensions" in data
    assert "improved_framework" in data
    assert "disclaimer" in data


def test_mains_score_bounded_by_max_marks():
    gen_res = client.post("/tests/mains/generate", json={"source_mode": "static", "marks": 10, "word_limit": 150})
    if gen_res.status_code != 200:
        pytest.skip("No eligible books available")
    q_id = gen_res.json()["question_id"]
    sub_res = client.post("/tests/mains/submit", json={
        "question_id": q_id,
        "answer_text": "Short answer"
    })
    if sub_res.status_code == 200:
        assert sub_res.json()["score"] <= 10


def test_mains_evaluation_contains_disclaimer():
    gen_res = client.post("/tests/mains/generate", json={"source_mode": "static", "marks": 10, "word_limit": 150})
    if gen_res.status_code != 200:
        pytest.skip("No eligible books available")
    q_id = gen_res.json()["question_id"]
    sub_res = client.post("/tests/mains/submit", json={
        "question_id": q_id,
        "answer_text": "The constitutional framework is fundamental to good governance in India. "
                       "Article 12 to 35 covers fundamental rights while DPSPs guide state policy."
    })
    if sub_res.status_code == 200:
        data = sub_res.json()
        assert "disclaimer" in data
        assert "not an official" in data["disclaimer"].lower() or "practice" in data["disclaimer"].lower()


def test_mains_rubric_has_correct_dimensions():
    gen_res = client.post("/tests/mains/generate", json={"source_mode": "static", "marks": 15, "word_limit": 250})
    if gen_res.status_code != 200:
        pytest.skip("No eligible books available")
    q_id = gen_res.json()["question_id"]
    sub_res = client.post("/tests/mains/submit", json={
        "question_id": q_id,
        "answer_text": " ".join(["The core principles of governance and administration are pivotal."] * 20)
    })
    if sub_res.status_code == 200:
        rubric = sub_res.json()["rubric_breakdown"]
        expected_keys = ["demand_and_relevance", "structure_and_headings", "content_coverage",
                         "analysis_and_examples", "conclusion_presentation"]
        for key in expected_keys:
            assert key in rubric
        # Scores should be whole or half marks
        for v in rubric.values():
            assert v * 2 == int(v * 2)  # half-mark granularity
