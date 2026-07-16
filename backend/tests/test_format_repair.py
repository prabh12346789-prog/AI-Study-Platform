import pytest

from src.services.orchestrator.format_repair import repair_mode_format
from src.services.orchestrator.models import ResponseMode


@pytest.mark.parametrize(
    ("mode", "answer", "required"),
    [
        (ResponseMode.LEARN, "**Definition**\nRights protect liberty. They are enforceable.", ["Definition", "Example"]),
        (ResponseMode.REVISION, "Key Facts: Article 14; 44th Amendment, 1978.", ["Key Facts", "Exam Points"]),
        (ResponseMode.PRELIMS, "Articles 12-35 are in Part III. Article 300A concerns property.", ["Core Facts", "Prelims Trap"]),
        (ResponseMode.MAINS, "Introduction: Rights limit state power.\n## Main Body\n### Constitutional Dimension\nArticle 32 enables remedies.\nConclusion: Balance matters.", ["Introduction", "Main Body", "Conclusion"]),
        (ResponseMode.INTERVIEW, "Direct Answer: Rights require balance. Reasons: They protect dignity.", ["Direct Answer", "Different Perspectives"]),
    ],
)
def test_repair_applies_each_mode_structure(mode, answer, required):
    repaired = repair_mode_format(answer, mode)
    for heading in required:
        assert f"## {heading}" in repaired
    assert all(not line or line.startswith("#") or line.startswith("- ") for line in repaired.splitlines())


def test_repair_preserves_facts_and_safe_empty_fallback():
    repaired = repair_mode_format("**Article 21**; 44th Amendment, 1978 [source: PDF]", ResponseMode.PRELIMS)
    assert "**Article 21**" in repaired
    assert "[source: PDF]" in repaired
    assert "- Not specified in the generated response." in repair_mode_format("", ResponseMode.LEARN)


def test_repair_removes_duplicate_required_headings():
    repaired = repair_mode_format("## Key Facts\nA\n**Key Facts**\nB", ResponseMode.REVISION)
    assert repaired.count("## Key Facts") == 1
    assert "- A" in repaired and "- B" in repaired
