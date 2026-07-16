import pytest

from src.activity.taxonomy import SubjectTopicClassifier


@pytest.mark.parametrize(("text", "subject", "topic"), [
    ("Explain Article 32 and Fundamental Rights", "Polity and Governance", "Fundamental Rights"),
    ("How do inflation and repo rate affect monetary policy?", "Economy", "Monetary Policy"),
    ("How does the monsoon create cyclones?", "Geography", "Climatology"),
    ("Biodiversity in a national park", "Environment and Ecology", "Biodiversity"),
    ("Explain the Quit India movement", "History and Art & Culture", "Modern Indian History"),
])
def test_upsc_classification(text, subject, topic):
    result = SubjectTopicClassifier().classify(text)
    assert (result["subject"], result["topic"]) == (subject, topic)


def test_low_confidence_fallback_and_manual_override():
    classifier = SubjectTopicClassifier()
    assert classifier.classify("Explain this general idea")["topic"] == "Unclassified"
    result = classifier.classify("inflation", subject="Essay", topic="Development Essay")
    assert result == {
        "subject": "Essay", "topic": "Development Essay",
        "confidence": 1.0, "method": "manual_override",
    }
