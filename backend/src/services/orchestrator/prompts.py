from src.services.orchestrator.models import ResponseMode


ACCURACY_AND_GROUNDING_RULES = """
- Answer accurately and do not invent Articles, Acts, years, institutions, cases, or factual details.
- Answer the exact scope of the current question. Do not replace it with a broader or easier generic topic.
- When retrieved context is present, use only passages relevant to the exact current question.
- If retrieved context conflicts with the current question's scope, ignore the irrelevant passage rather than changing the topic.
- Preserve precise constitutional terms, official names, dates, and source attribution.
"""


MODE_INTENT = {
    ResponseMode.LEARN: "Explain concepts clearly, build understanding, and use examples only where useful.",
    ResponseMode.REVISION: "Support fast recall with key facts and minimal explanation.",
    ResponseMode.PRELIMS: "Prioritize factual precision, Articles, dates, institutions, distinctions, and common traps.",
    ResponseMode.MAINS: "Develop analytical dimensions, arguments, challenges, a practical way forward, and a balanced conclusion.",
    ResponseMode.INTERVIEW: "Give a direct, balanced, natural response with practical reasoning.",
}


DEPTH_INTENT = {
    "quick": "Be direct and selective; target roughly 120–250 words when the question warrants it.",
    "standard": "Cover the core concepts, relevant examples, and exam relevance; target roughly 300–550 words when warranted.",
    "detailed": "Provide broader analysis, dimensions, qualifications, and limitations; target roughly 600–900 words when warranted.",
}


def build_presentation_instructions(mode, format: str, depth: str) -> dict[str, str]:
    mode = ResponseMode(mode)
    base = {
        "bullets": "Presentation contract: write concise Markdown bullet points only, each beginning with '- '. Do not force headings; add a topic-specific heading only if it materially improves clarity.",
        "structured": "Presentation contract: use meaningful topic-specific Markdown headings and subheadings, with organized points or short paragraphs beneath them. At least two topic-specific headings are required when the answer has enough content.",
        "explanation": "Presentation contract: write readable short connected paragraphs. Do not use Markdown headings or bullet markers unless a list is genuinely unavoidable.",
        "mixed": "Presentation contract: the first content must be one short prose overview paragraph with no heading; follow it with key Markdown bullets, then optionally add one short conclusion or UPSC relevance line.",
    }[format]
    combinations = {
        (ResponseMode.LEARN, "bullets"): "Use about 5–8 explanatory bullets and answer the exact question directly; do not require Definition or Explanation headings.",
        (ResponseMode.LEARN, "structured"): "Choose headings that match this particular topic; never default mechanically to Definition / Explanation / Example / Importance.",
        (ResponseMode.LEARN, "explanation"): "Use about 2–4 short connected paragraphs with no bullet list unless the content truly needs one.",
        (ResponseMode.LEARN, "mixed"): "Use one short overview paragraph, about 4–6 key bullets, and one short UPSC relevance line when relevant.",
        (ResponseMode.REVISION, "bullets"): "Use compact recall points only, without introductory prose.",
        (ResponseMode.PRELIMS, "structured"): "Use question-relevant sections such as Core Facts, Important Provisions, and Prelims Traps when applicable.",
        (ResponseMode.MAINS, "structured"): "Use Introduction, a topic-specific Main Body with analytical dimensions, Challenges, Way Forward, and Conclusion when applicable.",
        (ResponseMode.INTERVIEW, "explanation"): "Answer conversationally and directly, give balanced reasoning, and end with a short practical conclusion.",
    }
    return {
        "mode": MODE_INTENT[mode],
        "format": base + " " + combinations.get((mode, format), "Let the selected format control presentation while the mode controls purpose."),
        "depth": DEPTH_INTENT[depth],
    }


def build_exact_question_scope(question: str) -> str:
    normalized = " ".join(question.casefold().split())
    if "historical background" in normalized and "indian constitution" in normalized:
        return (
            "Treat 'historical background' as the constitutional-development chronology: Company-rule regulation, "
            "Crown rule, Charter and Government of India reforms, transfer of power, and the Constituent Assembly. "
            "Focus on the relevant Acts, years, institutional changes, and progression. Do not substitute a definition, "
            "present-day features, Parts, Schedules, or a general account of adoption."
        )
    return "Identify and preserve every limiting phrase in the question; do not broaden the requested scope."
