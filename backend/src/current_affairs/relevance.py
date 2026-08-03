from __future__ import annotations

import re
from typing import TypedDict


class ClassificationResult(TypedDict):
    subject: str
    gs_paper: str
    relevance_reason: str
    classification_method: str


REJECT_PATTERNS = [
    (r"\b(greetings|congratulates|wishes|condolences|deeply saddened|happy birthday|warm wishes)\b", "irrelevant_routine_notice"),
    (r"\b(tender|e-procurement|expression of interest|rfp|auction)\b", "irrelevant_tender_notice"),
    (r"\b(walk-in interview|recruitment|vacancy|admit card|examination result)\b", "irrelevant_advertisement"),
    (r"\b(curtain raiser|photo exhibition|cultural event|inaugurated photo)\b", "photo_event_notice"),
]

# Standard UPSC Subjects
SUBJECT_KEYWORDS = [
    (
        "Economy",
        "GS Paper III",
        r"\b(rbi|reserve bank|banking|inflation|monetary policy|repo rate|fiscal|gdp|sebi|forex|economy|economic|gst|revenue|trade|currency|budget|taxation)\b",
        "Pertains to macroeconomic, banking, and monetary policy developments.",
    ),
    (
        "International Relations",
        "GS Paper II",
        r"\b(bilateral|treaty|foreign minister|summit|diplomatic|mou|un|g20|asean|ambassador|foreign visit|mea|external affairs|diaspora|quad|brics)\b",
        "Relates to India's foreign policy, international summits, and bilateral relations.",
    ),
    (
        "Environment and Ecology",
        "GS Paper III",
        r"\b(climate|biodiversity|pollution|conservation|cop|forest|tiger reserve|renewable|emission|environment|ecology|wildlife|solar|green energy|cop28|cop29)\b",
        "Focuses on environmental policy, biodiversity conservation, and climate change.",
    ),
    (
        "Polity and Governance",
        "GS Paper II",
        r"\b(parliament|bill|constitution|constitutional|ministry|cabinet|supreme court|high court|act|commission|eci|cag|governor|ordinance|judiciary|elections|governance|public policy)\b",
        "Covers constitutional provisions, statutory bodies, legislation, and governance reforms.",
    ),
    (
        "Science and Technology",
        "GS Paper III",
        r"\b(space|ai|artificial intelligence|biotechnology|research|isro|satellite|quantum|semiconductor|r&d|patent|technology|cyber|drdo|nanotechnology|nuclear)\b",
        "Covers technological advancements, space missions, defense R&D, and scientific research.",
    ),
    (
        "Agriculture",
        "GS Paper III",
        r"\b(agriculture|agricultural|crop|farmer|farmers|msp|pm-kisan|irrigation|fertilizer|harvest|icar|farming|kharif|rabi)\b",
        "Deals with agricultural policies, schemes, crop management, and farming sector.",
    ),
    (
        "Disaster Management",
        "GS Paper III",
        r"\b(disaster|cyclone|flood|earthquake|ndma|landslide|tsunami|imd|meteorological|rescue|relief operation)\b",
        "Relates to disaster management infrastructure, meteorological warnings, and emergency response.",
    ),
    (
        "Social Justice",
        "GS Paper II",
        r"\b(scheme|pm-yojana|mission|welfare|pension|health insurance|education|tribal|divyangjan|women empowerment|poshan|ayushman)\b",
        "Pertains to government welfare schemes, health, education, and social development.",
    ),
]


def evaluate_relevance(title: str, description: str) -> tuple[bool, str | None]:
    if not title or len(title.strip()) < 5:
        return False, "missing_title"

    text = f"{title} {description}".casefold()
    if len(text.strip()) < 20:
        return False, "insufficient_content"

    # Check rejection patterns
    for pattern, reason in REJECT_PATTERNS:
        if re.search(pattern, text, re.I):
            return False, reason

    # Routine appointment check without major policy significance
    if re.search(r"\b(assumes charge|takes over as|relinquishes charge)\b", text, re.I):
        if not re.search(r"\b(governor|chief justice|election commissioner|cag|upsc chairman|cabinet secretary)\b", text, re.I):
            return False, "irrelevant_routine_appointment"

    return True, None


def classify_subject(title: str, description: str) -> ClassificationResult:
    text = f"{title} {description}".casefold()

    for subject, gs_paper, pattern, reason in SUBJECT_KEYWORDS:
        if re.search(pattern, text, re.I):
            return {
                "subject": subject,
                "gs_paper": gs_paper,
                "relevance_reason": reason,
                "classification_method": "deterministic_keywords",
            }

    return {
        "subject": "Polity and Governance",
        "gs_paper": "GS Paper II",
        "relevance_reason": "Official government release on public policy and administrative developments.",
        "classification_method": "deterministic_keywords",
    }


def generate_extractive_summary(
    title: str,
    description: str,
    subject: str,
    gs_paper: str,
    source_name: str,
    source_url: str,
) -> str:
    clean_title = title.strip().rstrip(".")
    clean_desc = description.strip()

    # Format structured 80-150 word summary
    what = clean_title if clean_title in clean_desc else f"{clean_title}. {clean_desc}"
    if len(what) > 400:
        what = what[:397] + "..."

    summary = (
        f"What happened: {what}\n"
        f"Why it matters: This official update from {source_name} provides key administrative and policy details relevant to governance.\n"
        f"UPSC Relevance: Important for {gs_paper} under {subject}.\n"
        f"Source: {source_name} — {source_url}"
    )
    return summary
