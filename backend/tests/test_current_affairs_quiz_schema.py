from pydantic import ValidationError
import pytest

from src.schemas.current_affairs_quiz import QuizCreate


@pytest.mark.parametrize("payload", [
    {"period_type": "daily", "date_from": "2025-07-04", "date_to": "2025-07-04", "question_count": 5, "difficulty": "standard"},
    {"period_type": "weekly", "date_from": "2025-06-28", "date_to": "2025-07-04", "question_count": 10, "difficulty": "standard"},
])
def test_frontend_quiz_request_matches_schema(payload):
    request = QuizCreate.model_validate(payload)
    assert request.period_type == payload["period_type"]
    assert request.date_from.isoformat() == payload["date_from"]
    assert request.date_to.isoformat() == payload["date_to"]
    assert request.question_count == payload["question_count"]
    assert request.difficulty == "standard"


@pytest.mark.parametrize("field,value", [("period_type", "Daily"), ("difficulty", "normal")])
def test_quiz_request_rejects_unsupported_enum_values(field, value):
    payload = {"period_type": "daily", "date_from": "2025-07-04", "date_to": "2025-07-04", "question_count": 5, "difficulty": "standard"}
    payload[field] = value
    with pytest.raises(ValidationError):
        QuizCreate.model_validate(payload)
