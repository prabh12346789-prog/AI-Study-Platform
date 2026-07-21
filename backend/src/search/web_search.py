from __future__ import annotations

import hashlib
import html as html_lib
import json
import logging
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

import requests

from src.core.config import settings
from src.activity.taxonomy import SubjectTopicClassifier
from src.current_affairs.source_policy import DISCOVERY_FEEDS, DISCOVERY_LISTINGS

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
    "mea.gov.in": ("Ministry of External Affairs", "official_government", "official"),
    "sansadtv.nic.in": ("Sansad TV", "official_broadcast", "official"),
    "ddnews.gov.in": ("DD News", "official_broadcast", "official"),
    "forumias.com": ("ForumIAS", "approved_upsc_analysis", "trusted"),
    "insightsonindia.com": ("InsightsIAS", "approved_upsc_analysis", "trusted"),
    "drishtiias.com": ("Drishti IAS", "approved_upsc_analysis", "trusted"),
    "iasscore.in": ("GS SCORE", "approved_upsc_analysis", "trusted"),
    "visionias.in": ("Vision IAS", "approved_upsc_analysis", "trusted"),
    "pwonlyias.com": ("PWOnlyIAS", "approved_upsc_analysis", "trusted"),
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
    PROVIDERS = {
        "bing_rss": "https://www.bing.com/search?format=rss&q={query}",
        "duckduckgo_html": "https://html.duckduckgo.com/html/?q={query}",
    }
    def __init__(self, cache=None): self.cache = cache or WebCache()

    @property
    def provider_name(self): return settings.SEARCH_PROVIDER.strip().casefold()

    def validate_configuration(self, *, direct_urls=False):
        if direct_urls: return
        if not settings.ENABLE_WEB_SEARCH:
            raise RuntimeError("Current Affairs search provider is not configured for live web discovery. ENABLE_WEB_SEARCH is false.")
        if self.provider_name not in self.PROVIDERS:
            raise RuntimeError("Current Affairs search provider is not configured for live web discovery.")
        if not APPROVED_DOMAINS:
            raise RuntimeError("Current Affairs trusted-source allowlist is empty.")
        if settings.MAX_WEB_RESULTS < 1:
            raise RuntimeError("Current Affairs maximum web results must be at least 1.")

    def search(self, question: str, max_results=None):
        self.validate_configuration()
        limit = min(max_results or settings.MAX_WEB_RESULTS, settings.MAX_WEB_RESULTS)
        approved, rejected_domains, rejected_redirects, extraction_attempts, extraction_successes, hits = [], 0, 0, 0, 0, 0
        try: candidates = self._search_web(question, limit)
        except requests.RequestException as error:
            log.warning("Trusted web search failed: %s", type(error).__name__)
            return self._result([], provider=self.provider_name, error="provider_unavailable", zero_result_reason="provider unavailable")
        except (ValueError, ET.ParseError) as error:
            log.warning("Trusted web query failed: %s", type(error).__name__)
            return self._result([], provider=self.provider_name, error="query_failure", zero_result_reason="query failure")
        current = any(word in question.casefold() for word in ("current", "latest", "today", "recent", "2025", "2026"))
        classification = SubjectTopicClassifier().classify(question)
        candidates.sort(key=lambda item: self._candidate_rank(item, question), reverse=True)
        progress = []
        for candidate in candidates:
            policy = TrustedSourcePolicy.classify(candidate["url"])
            if not policy:
                rejected_domains += 1
                progress.append({"url": candidate["url"], "page_type": self.page_type(candidate["url"]),
                    "quality_score": 0.0, "status": "rejected", "rejection_code": "unapproved_domain",
                    "reason": "unapproved domain", "summarization": "not attempted"})
                continue
            publisher, category, trust, domain = policy
            cached = self.cache.get(candidate["url"], current=current)
            if cached:
                quality = self.article_quality(cached)
                if not quality["is_article"]:
                    progress.append({"url": candidate["url"], "page_type": quality["page_type"],
                        "quality_score": quality["quality_score"], "status": "rejected",
                        "rejection_code": self.rejection_code("; ".join(quality["reasons"])),
                        "reason": "; ".join(quality["reasons"]), "summarization": "not attempted"})
                    continue
                chunk = {**cached, "article_quality": quality, "search_rank": self._candidate_rank(candidate, question)}; hits += 1
            else:
                extraction_attempts += 1
                chunk, failure = self._fetch_approved(candidate, publisher, category, trust, domain, question)
                if not chunk:
                    rejected_redirects += failure == "redirect"
                    progress.append({"url": candidate["url"], "page_type": self.page_type(candidate["url"]),
                        "quality_score": 0.0, "status": "rejected", "rejection_code": self.rejection_code(failure),
                        "reason": failure, "summarization": "not attempted"})
                    continue
                extraction_successes += 1
                chunk["subject"], chunk["topic"] = classification["subject"], classification["topic"]
                self.cache.put(chunk)
            approved.append(chunk)
            progress.append({"url": chunk["source_url"], "page_type": chunk["article_quality"]["page_type"],
                "quality_score": chunk["article_quality"]["quality_score"], "status": "candidate",
                "rejection_code": None, "reason": "; ".join(chunk["article_quality"]["reasons"]), "summarization": "pending"})
            if len(approved) >= limit: break
        approved.sort(key=lambda chunk: (chunk["article_quality"]["quality_score"], chunk.get("search_rank", 0)), reverse=True)
        zero_reason = "no search matches" if not candidates else None
        log.info("Trusted web provider=%s query=%r raw=%d rejected_domains=%d rejected_redirects=%d extraction_attempts=%d extraction_successes=%d candidates=%d",
                 self.provider_name, question, len(candidates), rejected_domains, rejected_redirects,
                 extraction_attempts, extraction_successes, len(approved))
        return self._result(approved, provider=self.provider_name, raw_results=len(candidates),
            rejected_domains=rejected_domains, rejected_redirects=rejected_redirects,
            extraction_attempts=extraction_attempts, extraction_successes=extraction_successes,
            cache_hits=hits, zero_result_reason=zero_reason, source_progress=progress)

    def fetch_url(self, url: str, question: str):
        return self.fetch_candidate({"url": url, "title": url, "snippet": "", "discovery_method": "direct_url"}, question)

    def fetch_candidate(self, candidate: dict, question: str):
        url = candidate["url"]
        policy = TrustedSourcePolicy.classify(url)
        if not policy:
            return self._result([], provider="direct_url", raw_results=1, rejected_domains=1)
        publisher, category, trust, domain = policy
        chunk, failure = self._fetch_approved(candidate, publisher, category, trust, domain, question)
        if chunk:
            chunk["discovery_method"] = candidate.get("discovery_method", "direct_url")
            chunk["discovered_title"] = candidate.get("title")
        if chunk and "article_quality" not in chunk: chunk["article_quality"] = self.article_quality(chunk)
        chunks = [chunk] if chunk else []
        return self._result(chunks, provider="direct_url", raw_results=1, rejected_redirects=int(failure == "redirect"),
            extraction_attempts=1, extraction_successes=len(chunks), source_progress=[{
                "url": url, "page_type": self.page_type(url),
                "quality_score": chunk["article_quality"]["quality_score"] if chunk else 0.0,
                "status": "candidate" if chunk else "rejected", "rejection_code": None if chunk else self.rejection_code(failure),
                "reason": failure or "; ".join(chunk["article_quality"]["reasons"]),
                "summarization": "pending" if chunk else "not attempted"}])

    def discover_feeds(self, limit=12):
        candidates, progress = [], []
        for feed in DISCOVERY_FEEDS:
            try:
                response = requests.get(feed["url"], timeout=10, headers={"User-Agent": "UPSC-AI-Mentor/1.0"})
                response.raise_for_status(); root = ET.fromstring(response.text)
                entries = root.findall("./channel/item") + root.findall("{http://www.w3.org/2005/Atom}entry")
                for item in entries[:limit]:
                    atom = "{http://www.w3.org/2005/Atom}"
                    link_node = item.find("link")
                    if link_node is None: link_node = item.find(atom + "link")
                    url = item.findtext("link", "") or (link_node.get("href", "") if link_node is not None else "")
                    title = item.findtext("title", "") or item.findtext(atom + "title", "")
                    published = item.findtext("pubDate", "") or item.findtext(atom + "published", "") or item.findtext(atom + "updated", "")
                    question_page = title.strip().endswith("?") or re.match(r"^(what|how|why|discuss|analyse|examine|evaluate)\b", title.strip(), re.I)
                    if url and not question_page and TrustedSourcePolicy.classify(url) and self.page_type(url) == "article":
                        candidates.append({"url": url, "title": title, "publication_date": published,
                            "source": feed["source"], "source_category": feed["category"], "discovery_method": "rss_atom"})
                progress.append({"url": feed["url"], "status": "discovered", "discovery_method": "rss_atom", "count": len(entries)})
            except (requests.RequestException, ET.ParseError) as error:
                progress.append({"url": feed["url"], "status": "rejected", "rejection_code": "feed_discovery_failure",
                    "reason": type(error).__name__, "discovery_method": "rss_atom"})
        unique = {self._canonical_url(item["url"]): item for item in candidates}
        return {"candidates": list(unique.values())[:limit], "source_progress": progress}

    def discover_listings(self, limit=12):
        candidates, progress = [], []
        for listing in DISCOVERY_LISTINGS:
            try:
                response = requests.get(listing["url"], timeout=10, headers={"User-Agent": "UPSC-AI-Mentor/1.0"})
                response.raise_for_status()
                anchors = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', response.text, re.I | re.S)
                found = 0
                for href, raw_title in anchors:
                    url, title = urljoin(response.url, html_lib.unescape(href)), self._clean(raw_title)
                    if len(title) < 18 or self.page_type(url) != "article" or not TrustedSourcePolicy.classify(url): continue
                    if not re.search(r"(?:prid|id|articleid)=\d+|/20\d{2}/|/current-affairs/|/daily-current-affairs/", url, re.I): continue
                    candidates.append({"url": url, "title": title, "publication_date": None,
                        "source": listing["source"], "source_category": listing["category"], "discovery_method": "source_listing"})
                    found += 1
                progress.append({"url": listing["url"], "status": "discovered", "discovery_method": "source_listing", "count": found})
            except requests.RequestException as error:
                progress.append({"url": listing["url"], "status": "rejected", "rejection_code": "listing_discovery_failure",
                    "reason": type(error).__name__, "discovery_method": "source_listing"})
        unique = {self._canonical_url(item["url"]): item for item in candidates}
        return {"candidates": list(unique.values())[:limit], "source_progress": progress}

    @staticmethod
    def rejection_code(reason):
        value = (reason or "").casefold()
        mappings = (("unapproved domain", "unapproved_domain"), ("redirect", "redirect_to_unapproved_domain"),
            ("homepage", "homepage_index_archive_search_page"), ("index", "homepage_index_archive_search_page"), ("archive", "homepage_index_archive_search_page"),
            ("challenge", "blocked_challenge_response"), ("403", "blocked_challenge_response"), ("429", "blocked_challenge_response"),
            ("fetch", "extraction_http_failure"), ("shorter than", "insufficient_clean_text"),
            ("insufficient extracted", "insufficient_clean_text"), ("title", "missing_article_specific_title"),
            ("paragraph", "insufficient_substantive_paragraphs"), ("boilerplate", "excessive_boilerplate_navigation"),
            ("navigation", "excessive_boilerplate_navigation"), ("publication date", "invalid_implausible_publication_date"))
        return next((code for marker, code in mappings if marker in value), "other_rejection")

    def _result(self, chunks, **diagnostics):
        result = {"context": self._build_context(chunks), "sources": [self._source(chunk) for chunk in chunks],
            "chunks": chunks, "raw_results": 0, "rejected_domains": 0, "rejected_redirects": 0,
            "extraction_attempts": 0, "extraction_successes": 0, "cache_hits": 0, "zero_result_reason": None,
            "source_progress": []}
        result.update(diagnostics); result["rejected_count"] = result["rejected_domains"] + result["rejected_redirects"]
        return result

    def _search_web(self, question, limit):
        response = requests.get(self.PROVIDERS[self.provider_name].format(query=quote_plus(question)), timeout=10,
            headers={"User-Agent": "UPSC-AI-Mentor/1.0"}); response.raise_for_status()
        if self.provider_name == "bing_rss":
            root = ET.fromstring(response.text)
            return [{"title": item.findtext("title", ""), "snippet": item.findtext("description", ""),
                     "url": item.findtext("link", "")} for item in root.findall("./channel/item")][:limit * 4]
        parsed = self._parse_results(response.text)[:limit * 4]
        if response.status_code == 202 and not parsed: raise ValueError("search challenge page")
        return parsed

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
        initial_type = self.page_type(candidate["url"])
        if initial_type != "article": return None, f"{initial_type} URL is not an article"
        try:
            response = requests.get(candidate["url"], timeout=10, headers={"User-Agent": "UPSC-AI-Mentor/1.0"}, allow_redirects=True)
            response.raise_for_status()
        except requests.HTTPError as error:
            status = getattr(error.response, "status_code", None)
            return None, "blocked/challenge response" if status in {401, 403, 429} else "extraction HTTP failure"
        except requests.RequestException: return None, "extraction HTTP failure"
        if not TrustedSourcePolicy.classify(response.url): return None, "redirect"
        raw = re.sub(r"<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>", " ", response.text, flags=re.I|re.S)
        og_title = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:title|twitter:title)["\'][^>]+content=["\']([^"\']+)', raw, re.I)
        title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I|re.S)
        title = self._clean(og_title.group(1)) if og_title else self._clean(title_match.group(1)) if title_match else candidate["title"]
        emphasized = [self._clean(value) for value in re.findall(r"<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>", raw, re.I|re.S)]
        article_titles = [value for value in emphasized if 20 <= len(value) <= 240 and not any(
            term in value.casefold() for term in ("increase font", "skip to", "javascript", "redirect to"))]
        if article_titles: title = max(article_titles, key=len)
        canonical_match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', raw, re.I)
        canonical = html_lib.unescape(canonical_match.group(1)) if canonical_match else response.url
        if not TrustedSourcePolicy.classify(canonical): canonical = response.url
        date_match = re.search(r'<meta[^>]+(?:property|name)=["\'](?:article:published_time|date|last-modified)["\'][^>]+content=["\']([^"\']+)', raw, re.I)
        publication_date = date_match.group(1)[:40] if date_match else None
        if not publication_date:
            visible_date = re.search(r"Date\s*:\s*([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})", self._clean(raw), re.I)
            if visible_date:
                try: publication_date = datetime.strptime(visible_date.group(1), "%b %d, %Y").date().isoformat()
                except ValueError: pass
        if not publication_date:
            posted = re.search(r"Posted On\s*:\s*(\d{1,2}\s+[A-Z]{3}\s+\d{4})", self._clean(raw), re.I)
            if posted:
                try: publication_date = datetime.strptime(posted.group(1).title(), "%d %b %Y").date().isoformat()
                except ValueError: pass
        if not publication_date and candidate.get("publication_date"):
            try: publication_date = parsedate_to_datetime(candidate["publication_date"]).date().isoformat()
            except (TypeError, ValueError, OverflowError):
                try: publication_date = datetime.fromisoformat(str(candidate["publication_date"])[:10]).date().isoformat()
                except ValueError: publication_date = None
        if publication_date:
            try:
                published = datetime.fromisoformat(str(publication_date)[:10]).date()
                if published.year < 2000 or published > datetime.now(timezone.utc).date() + timedelta(days=1): publication_date = None
            except ValueError: publication_date = None
        headings = [self._clean(value) for value in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", raw, re.I|re.S)][:8]
        heading_titles = [value for value in headings if len(value) >= 20 and "press release" not in value.casefold()]
        if heading_titles and ("press release page" in title.casefold() or len(title) > 180): title = heading_titles[0]
        host = (urlparse(response.url).hostname or "").casefold()
        source_pattern = r'<(?:article|main)[^>]*>(.*?)</(?:article|main)>' if any(domain in host for domain in ("forumias.com", "insightsonindia.com", "drishtiias.com", "iasscore.in", "visionias.in")) else r'<div[^>]+(?:id|class)=["\'][^"\']*(?:content|release|article)[^"\']*["\'][^>]*>(.*?)</div>'
        source_match = re.search(source_pattern, raw, re.I | re.S)
        extraction_scope = source_match.group(1) if source_match else raw
        paragraph_html = re.findall(r"<p[^>]*>(.*?)</p>", extraction_scope, re.I|re.S)
        if len(paragraph_html) < 2:
            paragraph_html = re.findall(r"<p[^>]*>(.*?)</p>", raw, re.I|re.S)
            source_match = None
        paragraphs = [self._clean(value) for value in paragraph_html]
        paragraphs = [value for value in paragraphs if len(value) >= 30]
        paragraphs = list(dict.fromkeys(paragraphs))
        terms = {word for word in re.findall(r"[a-z]{4,}", question.casefold()) if word not in {"what", "when", "where", "which", "explain", "discuss"}}
        relevant = [value for value in paragraphs if len(value) >= 30 and (not terms or any(term in value.casefold() for term in terms))]
        text = "\n".join(value for value in headings + (relevant or paragraphs[:12]) if len(value) >= 30)[:12000]
        if len(text) < 100: text = candidate.get("snippet", "")
        if len(text) < 50: return None, "insufficient extracted text"
        quality = self.article_quality({"source_url": canonical, "source_title": title, "text": text,
            "publication_date": publication_date, "metadata": {"headings": headings, "paragraphs": paragraphs,
            "link_text_length": sum(len(value) for value in set(self._clean(value) for paragraph in paragraph_html for value in re.findall(r"<a[^>]*>(.*?)</a>", paragraph, re.I|re.S)))}})
        if not quality["is_article"]: return None, "; ".join(quality["reasons"])
        retrieved = datetime.now(timezone.utc).isoformat()
        return {"text": text, "score": 1.0 if trust == "official" else .9, "source_type": "web",
            "source_url": canonical, "source_title": title, "publisher": publisher, "domain": domain,
            "retrieved_at": retrieved, "publication_date": publication_date, "source_category": category, "trust_level": trust,
            "content_hash": hashlib.sha256(text.encode()).hexdigest(), "subject": None, "topic": None,
            "metadata": {"headings": headings, "paragraphs": paragraphs}, "article_quality": quality,
            "search_rank": self._candidate_rank(candidate, question),
            "extraction_adapter": "source_specific" if source_match else "generic"}, None

    @staticmethod
    def page_type(url):
        parsed = urlparse(url); path = parsed.path.casefold().rstrip("/")
        if not path: return "homepage"
        combined = path + "?" + parsed.query.casefold()
        if any(term in combined for term in ("login", "signin", "sitemap", "search", "/tag/", "/category/", "/author/",
            "quiz", "daily-aptitude", "reasoning-test", "answer-writing", "mains-answer", "practice-question")): return "index"
        index_names = ("/scripts/bs_pressreleasedisplay.aspx", "/allrelease.aspx", "/archive", "/index")
        if any(path.endswith(name) for name in index_names) and not re.search(r"(?:prid|id|articleid)=\d+", parsed.query, re.I): return "index"
        return "article"

    @classmethod
    def article_quality(cls, chunk):
        text = re.sub(r"\s+", " ", chunk.get("text", "")).strip()
        title = re.sub(r"\s+", " ", chunk.get("source_title", "")).strip()
        metadata = chunk.get("metadata") or {}; paragraphs = metadata.get("paragraphs") or [p.strip() for p in chunk.get("text", "").splitlines() if len(p.strip()) >= 30]
        page_type = cls.page_type(chunk.get("source_url", "")); reasons = []; score = 0.0
        generic_title = not title or title.casefold() in {"home", "reserve bank of india", "press information bureau"} or len(title) < 12
        unique_ratio = len(set(paragraphs)) / len(paragraphs) if paragraphs else 0.0
        nav_ratio = float(metadata.get("link_text_length", 0)) / max(len(text), 1)
        if page_type != "article": reasons.append(f"{page_type} URL is not an article")
        if len(text) >= 700: score += .30
        elif len(text) >= 350: score += .20
        else: reasons.append("clean article body is shorter than 350 characters")
        if not generic_title: score += .20
        else: reasons.append("title is missing or generic")
        if len(paragraphs) >= 3: score += .20
        elif len(paragraphs) >= 2: score += .10
        else: reasons.append("fewer than two substantive paragraphs")
        if chunk.get("publication_date"): score += .15
        else: reasons.append("publication date unavailable")
        if unique_ratio >= .70: score += .10
        else: reasons.append("duplicate boilerplate ratio is high")
        if nav_ratio <= .50: score += .05
        else: reasons.append("navigation-to-content ratio is high")
        score = round(min(score, 1.0), 2)
        is_article = page_type == "article" and not generic_title and len(text) >= 350 and len(paragraphs) >= 2 and unique_ratio >= .45 and nav_ratio <= 1.0 and score >= .55
        return {"is_article": is_article, "quality_score": score, "reasons": reasons or ["article quality checks passed"], "page_type": page_type}

    @classmethod
    def _candidate_rank(cls, candidate, question):
        url, title = candidate.get("url", ""), candidate.get("title", "")
        score = 3 if cls.page_type(url) == "article" else -5
        query_terms = {term for term in re.findall(r"[a-z]{4,}|\d{4}", question.casefold()) if term not in {"site", "india"}}
        haystack = f"{title} {url}".casefold(); score += sum(term in haystack for term in query_terms)
        if re.search(r"(?:prid|id|articleid)=\d+", url, re.I): score += 3
        if re.search(r"/20\d{2}/(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])/", url): score += 3
        if candidate.get("publication_date"): score += 2
        if candidate.get("discovery_method") == "rss_atom": score += 3
        return score

    @staticmethod
    def _clean(value): return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<.*?>", " ", value))).strip()
    @staticmethod
    def _source(c):
        return {"source_type": "web", "title": c["source_title"], "document_name": None, "url": c["source_url"],
            "publisher": c["publisher"], "page_start": None, "page_end": None, "retrieved_at": c["retrieved_at"],
            "publication_date": c.get("publication_date"), "source_category": c["source_category"], "trust_level": c["trust_level"]}
    @staticmethod
    def _build_context(chunks): return "\n\n".join(f"[{c['publisher']}: {c['source_title']}]\n{c['text']}\n{c['source_url']}" for c in chunks)
