import ipaddress
import io
import re
import logging
from urllib.parse import urlsplit
import pypdf

log = logging.getLogger(__name__)

OFFICIAL_NOTES_HUBS = [
    "https://pwonlyias.com/downloads/",
    "https://pwonlyias.com/upsc-free-study-material/",
    "https://pwonlyias.com/upsc-exam-study-material/",
    "https://pwonlyias.com/udaan/",
    "https://pwonlyias.com/udaan-2-booklets/",
    "https://pwonlyias.com/onlyias-all-books/",
    "https://pwonlyias.com/books/",
    "https://pwonlyias.com/ncert-wallah-books/",
]

CORE_SUBJECT_MAP = {
    "polity": "Indian Polity and Governance",
    "indian polity": "Indian Polity and Governance",
    "polity and governance": "Indian Polity and Governance",
    "history": "History",
    "art and culture": "Art and Culture",
    "geography and disaster management": "Geography and Disaster Management",
    "geography": "Geography",
    "economy": "Indian Economy",
    "indian economy": "Indian Economy",
    "environment": "Environment and Ecology",
    "environment and ecology": "Environment and Ecology",
    "science & tech": "Science and Technology",
    "science and technology": "Science and Technology",
    "ir": "International Relations",
    "international relations": "International Relations",
    "society": "Indian Society and Social Justice",
    "social justice": "Indian Society and Social Justice",
    "internal security": "Internal Security",
    "disaster management": "Disaster Management",
    "ethics": "Ethics",
    "agriculture": "Agriculture",
    "budget": "Budget and Economic Survey",
    "economic survey": "Budget and Economic Survey",
    "essay": "Essay",
    "csat": "CSAT",
}

def is_valid_pwonlyias_source_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    try:
        parts = urlsplit(url)
    except Exception:
        return False

    if parts.scheme not in ("http", "https"):
        return False

    if parts.username or parts.password:
        return False

    hostname = parts.hostname
    if not hostname:
        return False
    hostname = hostname.casefold()

    if hostname == "localhost":
        return False

    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
        return False
    except ValueError:
        pass

    if hostname == "pwonlyias.com" or hostname.endswith(".pwonlyias.com"):
        return True

    return False

def extract_html_blocks(text: str) -> list[dict]:
    blocks = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if line.startswith("# ") or line.startswith("## "):
            blocks.append({"type": "heading", "level": 2, "text": line.lstrip("# ").strip()})
        elif line.startswith("### "):
            blocks.append({"type": "heading", "level": 3, "text": line.lstrip("# ").strip()})
        elif line.startswith("- ") or line.startswith("* "):
            if blocks and blocks[-1].get("type") == "bullet_list":
                blocks[-1]["items"].append(line[2:].strip())
            else:
                blocks.append({"type": "bullet_list", "items": [line[2:].strip()]})
        elif re.match(r"^\d+\.\s", line):
            item_txt = re.sub(r"^\d+\.\s*", "", line)
            if blocks and blocks[-1].get("type") == "numbered_list":
                blocks[-1]["items"].append(item_txt)
            else:
                blocks.append({"type": "numbered_list", "items": [item_txt]})
        elif line.lower().startswith("note:") or line.lower().startswith("key fact:"):
            blocks.append({"type": "important_fact", "text": line})
        else:
            blocks.append({"type": "paragraph", "text": line})
    return blocks

def extract_pdf_blocks(pdf_bytes: bytes, max_size_mb: int = 50) -> tuple[list[dict], int, str]:
    if not pdf_bytes or len(pdf_bytes) > max_size_mb * 1024 * 1024:
        return [], 0, "failed"

    stripped = pdf_bytes.lstrip()
    if not stripped.startswith(b"%PDF"):
        return [], 0, "failed"

    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        page_count = len(reader.pages)
        if page_count == 0:
            return [], 0, "failed"

        all_blocks = []
        has_text = False

        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                has_text = True
                page_blocks = extract_html_blocks(text)
                for b in page_blocks:
                    b["page_start"] = i
                    b["page_end"] = i
                    b["page_ref"] = i
                    all_blocks.append(b)

        if not has_text:
            return [], page_count, "image_only"

        return all_blocks, page_count, "ready"
    except Exception as err:
        log.warning(f"pypdf extraction error: {err}")
        return [], 0, "failed"

def normalize_subject(name: str | None) -> str:
    if not name:
        return "Other"
    clean = name.strip().casefold()
    for key, val in CORE_SUBJECT_MAP.items():
        if key in clean:
            return val
    return name.strip().title() or "Other"
