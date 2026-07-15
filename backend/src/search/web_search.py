from __future__ import annotations

import hashlib
import html as html_lib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse

import requests

from src.core.config import settings
from src.activity.taxonomy import SubjectTopicClassifier

log = logging.getLogger(__name__)

APPROVED_DOMAINS = {
    "gov.in": ("Government of India", "official_government", "official"),
    "nic.in": ("Government of India", "official_government", "official"),
    "indiacode.nic.in": ("India Code", "legislative", "official"),
    "parliamentofindia.nic.in": ("Parliament of India", "legislative", "official"),
    "sci.gov.in": ("Supreme Court of India", "judicial", "official"),
    "rbi.org.in": ("Reserve Bank of India", "official_institution", "official"),
    "sebi.gov.in": ("SEBI", "official_institution", "official"),
    "niti.gov.in": ("NITI Aayog", "official_institution", "official"),
    "pib.gov.in": ("Press Information Bureau", "official_government", "official"),
    "un.org": ("United Nations", "international_institution", "trusted"),
    "worldbank.org": ("World Bank", "international_institution", "trusted"),
    "imf.org": ("International Monetary Fund", "international_institution", "trusted"),
    "britannica.com": ("Encyclopaedia Britannica", "approved_reference", "trusted"),
}


class TrustedSourcePolicy:
    @staticmethod
    def classify(url: str):
        host = (urlparse(url).hostname or "").casefold().removeprefix("www.")
        for domain, values in sorted(APPROVED_DOMAINS.items(), key=lambda item: len(item[0]), reverse=True):
            if host == domain or host.endswith("." + domain): return (*values, host)
        return None


class WebCache:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or Path(settings.WEB_CACHE_DIR)
        if settings.WEB_CACHE_ENABLED: self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _key(url): return hashlib.sha256(url.encode()).hexdigest()
    def get(self, url: str, *, current: bool):
        path = self.base_dir / f"{self._key(url)}.json"
        if not settings.WEB_CACHE_ENABLED or not path.exists(): return None
        data = json.loads(path.read_text(encoding="utf-8")); retrieved = datetime.fromisoformat(data["retrieved_at"])
        age = timedelta(hours=settings.WEB_CURRENT_CACHE_HOURS) if current else timedelta(days=settings.WEB_STABLE_CACHE_DAYS)
        return data if datetime.now(timezone.utc) - retrieved <= age else None
    def put(self, chunk: dict):
        if not settings.WEB_CACHE_ENABLED: return
        path = self.base_dir / f"{self._key(chunk['source_url'])}.json"
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        if existing and existing.get("content_hash") == chunk.get("content_hash"): return
        path.write_text(json.dumps(chunk, ensure_ascii=False, indent=2), encoding="utf-8")


class WebSearch:
    SEARCH_URL = "https://html.duckduckgo.com/html/?q={query}"
    def __init__(self, cache=None): self.cache = cache or WebCache()

    def search(self, question: str):
        approved, rejected, hits = [], 0, 0
        try: candidates = self._search_web(question)
        except requests.RequestException as error:
            log.warning("Trusted web search failed: %s", type(error).__name__)
            return {"context": "", "sources": [], "chunks": [], "provider": "web", "error": "trusted_web_unavailable"}
        current = any(word in question.casefold() for word in ("current", "latest", "today", "recent", "2025", "2026"))
        classification = SubjectTopicClassifier().classify(question)
        for candidate in candidates:
            policy = TrustedSourcePolicy.classify(candidate["url"])
            if not policy: rejected += 1; continue
            publisher, category, trust, domain = policy
            cached = self.cache.get(candidate["url"], current=current)
            if cached: chunk = cached; hits += 1
            else:
                chunk = self._fetch_approved(candidate, publisher, category, trust, domain, question)
                if not chunk: rejected += 1; continue
                chunk["subject"], chunk["topic"] = classification["subject"], classification["topic"]
                self.cache.put(chunk)
            approved.append(chunk)
            if len(approved) >= settings.MAX_WEB_RESULTS: break
        log.info("Trusted web fallback approved=%d rejected=%d cache_hits=%d", len(approved), rejected, hits)
        return {"context": self._build_context(approved), "sources": [self._source(chunk) for chunk in approved],
                "chunks": approved, "provider": "web", "cache_hits": hits, "rejected_count": rejected}

    def _search_web(self, question):
        response = requests.get(self.SEARCH_URL.format(query=quote_plus(question)), timeout=10,
            headers={"User-Agent": "UPSC-AI-Mentor/1.0"}); response.raise_for_status()
        return self._parse_results(response.text)

    @staticmethod
    def _canonical_url(raw):
        if raw.startswith("//"): raw = "https:" + raw
        parsed = urlparse(raw); redirected = parse_qs(parsed.query).get("uddg")
        return redirected[0] if redirected else raw

    def _parse_results(self, html):
        pattern = re.compile(r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?(?:class="result__snippet"[^>]*>(?P<snippet>.*?)</a>)', re.S)
        return [{"title": self._clean(m.group("title")), "snippet": self._clean(m.group("snippet")),
                 "url": self._canonical_url(html_lib.unescape(m.group("url")))} for m in pattern.finditer(html)][:settings.MAX_WEB_RESULTS * 4]

    def _fetch_approved(self, candidate, publisher, category, trust, domain, question):
        try:
            response = requests.get(candidate["url"], timeout=10, headers={"User-Agent": "UPSC-AI-Mentor/1.0"}, allow_redirects=True)
            response.raise_for_status()
        except requests.RequestException: return None
        if not TrustedSourcePolicy.classify(response.url): return None
        raw = re.sub(r"<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>", " ", response.text, flags=re.I|re.S)
        title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I|re.S)
        title = self._clean(title_match.group(1)) if title_match else candidate["title"]
        canonical_match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', raw, re.I)
        canonical = html_lib.unescape(canonical_match.group(1)) if canonical_match else response.url
        if not TrustedSourcePolicy.classify(canonical): canonical = response.url
        date_match = re.search(r'<meta[^>]+(?:property|name)=["\'](?:article:published_time|date|last-modified)["\'][^>]+content=["\']([^"\']+)', raw, re.I)
        publication_date = date_match.group(1)[:40] if date_match else None
        headings = [self._clean(value) for value in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", raw, re.I|re.S)][:8]
        paragraphs = [self._clean(value) for value in re.findall(r"<p[^>]*>(.*?)</p>", raw, re.I|re.S)]
        terms = {word for word in re.findall(r"[a-z]{4,}", question.casefold()) if word not in {"what", "when", "where", "which", "explain", "discuss"}}
        relevant = [value for value in paragraphs if len(value) >= 30 and (not terms or any(term in value.casefold() for term in terms))]
        text = "\n".join(value for value in headings + (relevant or paragraphs[:12]) if len(value) >= 30)[:12000]
        if len(text) < 100: text = candidate.get("snippet", "")
        if len(text) < 50: return None
        retrieved = datetime.now(timezone.utc).isoformat()
        return {"text": text, "score": 1.0 if trust == "official" else .9, "source_type": "web",
            "source_url": canonical, "source_title": title, "publisher": publisher, "domain": domain,
            "retrieved_at": retrieved, "publication_date": publication_date, "source_category": category, "trust_level": trust,
            "content_hash": hashlib.sha256(text.encode()).hexdigest(), "subject": None, "topic": None,
            "metadata": {"headings": headings}}

    @staticmethod
    def _clean(value): return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<.*?>", " ", value))).strip()
    @staticmethod
    def _source(c):
        return {"source_type": "web", "title": c["source_title"], "document_name": None, "url": c["source_url"],
            "publisher": c["publisher"], "page_start": None, "page_end": None, "retrieved_at": c["retrieved_at"],
            "publication_date": c.get("publication_date"), "source_category": c["source_category"], "trust_level": c["trust_level"]}
    @staticmethod
    def _build_context(chunks): return "\n\n".join(f"[{c['publisher']}: {c['source_title']}]\n{c['text']}\n{c['source_url']}" for c in chunks)
