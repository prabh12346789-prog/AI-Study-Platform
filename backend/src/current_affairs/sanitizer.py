from __future__ import annotations

import html
import re
from html.parser import HTMLParser


_BLOCK_RE = re.compile(
    r"<(script|style|noscript|form|iframe|svg)\b[^>]*>.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_CODE_MARKERS = (
    "queryselector", "addeventlistener", "domcontentloaded", "function(",
    "aria-expanded", "setattribute(", "mutationobserver", "window.",
)
_NAV_MARKERS = ("subscribe release", "screen reader access")
_REGIONAL_RE = re.compile(r"\bPIB\s+(Delhi|Mumbai|Hyderabad|Chennai|Chandigarh|Kolkata|Bengaluru|Bhubaneswar|Ahmedabad|Guwahati)\b", re.I)
_MONTH_RE = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b", re.I)
_YEAR_RE = re.compile(r"\b20\d{2}\b")


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str):
        self.parts.append(data)


def _strip_markup(value: str) -> str:
    value = _COMMENT_RE.sub(" ", value)
    value = _BLOCK_RE.sub(" ", value)
    parser = _TextExtractor()
    try:
        parser.feed(value)
        parser.close()
        return " ".join(parser.parts)
    except Exception:
        return re.sub(r"<[^>]+>", " ", value)


def contamination_reason(value: str | None) -> str | None:
    text = html.unescape(value or "")
    folded = text.casefold()
    if "<" in text or ">" in text:
        if re.search(r"</?[a-z][^>]*>", text, re.I) or "<a title=" in folded:
            return "html"
    if any(marker in folded for marker in _CODE_MARKERS):
        return "javascript"
    if any(marker in folded for marker in _NAV_MARKERS):
        return "navigation"
    if len(_REGIONAL_RE.findall(text)) >= 3:
        return "regional_directory"
    if folded.count("ministry of ") >= 3:
        return "ministry_directory"
    if len(_MONTH_RE.findall(text)) >= 4 and len(_YEAR_RE.findall(text)) >= 2:
        return "archive_directory"
    return None


def sanitize_current_affairs_text(value: str | None, *, max_length: int = 600) -> str:
    text = html.unescape(value or "")
    text = _strip_markup(text)
    text = re.sub(r"\s+", " ", text).strip(" \t\r\n-|•")
    if contamination_reason(text):
        return ""
    if len(text) > max_length:
        shortened = text[:max_length].rsplit(" ", 1)[0].rstrip(" ,;:-")
        text = shortened + "…"
    return text


def is_safe_quiz_text(value: str | None, *, max_length: int) -> bool:
    text = value or ""
    return bool(text.strip()) and len(text) <= max_length and contamination_reason(text) is None

