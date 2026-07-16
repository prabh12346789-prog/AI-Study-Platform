"""Conservative Markdown repair for model responses.

This module deliberately changes presentation, not meaning: it reuses only
the generated text and adds a neutral marker where a required section is absent.
"""

from __future__ import annotations

import re

from src.services.orchestrator.models import ResponseMode


MODE_HEADINGS: dict[ResponseMode, list[str]] = {
    ResponseMode.LEARN: ["Definition", "Explanation", "Example", "Importance", "UPSC Relevance"],
    ResponseMode.REVISION: ["Key Facts", "Important Terms", "Exam Points"],
    ResponseMode.PRELIMS: ["Core Facts", "Constitutional or Legal Provisions", "Important Prelims Facts", "Prelims Trap"],
    ResponseMode.MAINS: ["Introduction", "Main Body", "Challenges", "Way Forward", "Conclusion"],
    ResponseMode.INTERVIEW: ["Direct Answer", "Reasons", "Different Perspectives", "Practical Approach", "Conclusion"],
}

_MISSING = "Not specified in the generated response."


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _sentences(text: str) -> list[str]:
    """Split prose conservatively; decimal values and Article numbers stay intact."""
    text = re.sub(r"^(?:[-*•]\s+)", "", text.strip())
    text = re.sub(r"^\d+[.)]\s*", "", text)
    if not text:
        return []
    pieces = re.split(r"\s*(?:\n+|;\s+|(?<=[.!?])\s+(?=[A-Z#]))", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def _heading(line: str, headings: list[str]) -> str | None:
    candidate = re.sub(r"^#{1,6}\s*", "", line.strip())
    candidate = re.sub(r"^\*{1,3}|\*{1,3}$", "", candidate).strip().rstrip(":")
    candidate_key = _key(candidate)
    for heading in headings:
        if candidate_key == _key(heading):
            return heading
    return None


def _inline_heading(line: str, headings: list[str]) -> tuple[str, str] | None:
    """Recognize labels such as ``**Definition**: text`` without losing text."""
    for heading in headings:
        pattern = rf"^(?:\*{{1,3}}\s*)?{re.escape(heading)}(?:\s*\*{{1,3}})?\s*:\s*(.+)$"
        match = re.match(pattern, line.strip(), flags=re.IGNORECASE)
        if match:
            return heading, match.group(1).strip()
    return None


def _is_subheading(line: str) -> str | None:
    match = re.match(r"^#{1,6}\s+(.+?)\s*$", line.strip())
    return match.group(1) if match else None


def repair_mode_format(answer: str, mode: ResponseMode) -> str:
    """Return the selected mode's required Markdown structure without new facts."""
    headings = MODE_HEADINGS[ResponseMode(mode)]
    sections: dict[str, list[str]] = {heading: [] for heading in headings}
    current: str | None = None
    unassigned: list[str] = []
    mains_subheadings: list[tuple[str, list[str]]] = []
    current_subheading: list[str] | None = None

    for raw_line in (answer or "").replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        inline = _inline_heading(line, headings)
        if inline:
            current, content = inline
            sections[current].extend(_sentences(content))
            current_subheading = None
            continue
        found = _heading(line, headings)
        if found:
            current = found
            current_subheading = None
            continue
        subheading = _is_subheading(line)
        if ResponseMode(mode) is ResponseMode.MAINS and current == "Main Body" and subheading:
            bucket: list[str] = []
            mains_subheadings.append((subheading, bucket))
            current_subheading = bucket
            continue
        points = _sentences(line)
        target = current_subheading if current_subheading is not None else (sections[current] if current else unassigned)
        target.extend(points)

    # Keep all otherwise unlabeled generated material, without duplicating it.
    if unassigned:
        preferred = "Main Body" if ResponseMode(mode) is ResponseMode.MAINS else headings[0]
        sections[preferred].extend(unassigned)

    # A blank model response gets a safe, visibly structured fallback.
    if not any(sections.values()) and not mains_subheadings:
        sections[headings[0]].append(_MISSING)

    output: list[str] = []
    for heading in headings:
        output.append(f"## {heading}")
        if heading == "Main Body" and mains_subheadings:
            if sections[heading]:
                output.extend(f"- {point}" for point in sections[heading])
            for subtitle, points in mains_subheadings:
                output.append(f"### {subtitle}")
                output.extend(f"- {point}" for point in (points or [_MISSING]))
        else:
            output.extend(f"- {point}" for point in (sections[heading] or [_MISSING]))
        output.append("")
    return "\n".join(output).strip()
