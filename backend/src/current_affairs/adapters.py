from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

import httpx

from src.core.config import settings

log = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "UPSC-AI-Mentor-Educational-Aggregator/1.0"


def clean_html_text(raw_html: str) -> str:
    if not raw_html:
        return ""
    # Strip HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", raw_html)
    # Unescape entities
    cleaned = (
        cleaned.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    # Collapse whitespace
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_rss_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    date_str = date_str.strip()
    try:
        dt = parsedate_to_datetime(date_str)
        if dt:
            return dt.astimezone(timezone.utc)
    except Exception:
        pass
    # Try ISO format
    try:
        return datetime.fromisoformat(date_str[:10]).replace(tzinfo=timezone.utc)
    except Exception:
        pass
    # Try common formats like 2026-08-03 or DD-MM-YYYY
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str[:10], fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


class BaseSourceAdapter:
    source_id: str
    source_name: str
    feed_url: str
    allowed_domains: list[str]

    def __init__(self):
        self.timeout = httpx.Timeout(
            settings.CURRENT_AFFAIRS_REQUEST_TIMEOUT_SECONDS,
            connect=5.0,
            read=10.0,
        )
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 UPSC-AI-Mentor-Educational-Aggregator/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.max_bytes = settings.CURRENT_AFFAIRS_MAX_RESPONSE_BYTES

    def is_allowed_domain(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").casefold()
        for domain in self.allowed_domains:
            domain = domain.casefold()
            if host == domain or host.endswith("." + domain):
                return True
        return False

    async def fetch_http(self, url: str) -> str | None:
        retries = 2
        backoff = 1.0
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    headers=self.headers,
                    follow_redirects=True,
                ) as client:
                    response = await client.get(url)
                    response.raise_for_status()

                    # Max size check
                    content_length = response.headers.get("content-length")
                    if content_length and int(content_length) > self.max_bytes:
                        log.warning("Response for %s exceeded max bytes %d", url, self.max_bytes)
                        return None
                    if len(response.content) > self.max_bytes:
                        log.warning("Response payload for %s exceeded max bytes", url)
                        return None

                    # Verify final URL stays within allowed domain
                    if not self.is_allowed_domain(str(response.url)):
                        log.warning("Redirected URL %s outside allowed domain", response.url)
                        return None

                    return response.text
            except Exception as exc:
                if attempt < retries:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    log.warning("Failed to fetch %s (%s): %s", url, type(exc).__name__, exc)
                    return None
        return None

    async def fetch_items(self) -> list[dict]:
        raise NotImplementedError

    def normalize_item(self, raw_item: dict) -> dict | None:
        raise NotImplementedError


class PIBAdapter(BaseSourceAdapter):
    source_id = "pib"
    source_name = "PIB"

    def __init__(self):
        super().__init__()
        self.feed_url = settings.PIB_RSS_URL
        self.listing_url = "https://www.pib.gov.in/AllRelease.aspx?lang=1&reg=3"
        self.allowed_domains = ["pib.gov.in", "www.pib.gov.in"]
        self.headers["User-Agent"] = "Mozilla/5.0"

    async def fetch_items(self) -> list[dict]:
        urls = [
            "https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=6",
            "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
            "https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
            self.feed_url,
            "https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1",
        ]
        xml_data = None
        for u in dict.fromkeys(urls):
            xml_data = await self.fetch_http(u)
            if xml_data:
                break

        items = []
        if xml_data:
            try:
                root = ET.fromstring(xml_data.lstrip("\ufeff"))
                channel_items = root.findall(".//item")
                for item in channel_items:
                    title = clean_html_text(item.findtext("title") or "")
                    link = (item.findtext("link") or "").strip()
                    pub_date_str = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
                    description = clean_html_text(item.findtext("description") or "")
                    category = clean_html_text(item.findtext("category") or "")

                    normalized = self.normalize_item({
                        "title": title,
                        "link": link,
                        "pub_date": pub_date_str,
                        "description": description,
                        "category": category,
                    })
                    if normalized:
                        items.append(normalized)
            except Exception as exc:
                log.error("Failed to parse PIB RSS XML: %s", exc)

        if not items:
            listing = await self.fetch_http(self.listing_url)
            if listing:
                pattern = re.compile(
                    r"<a[^>]+title=(?P<quote>['\"])(?P<title>.*?)(?P=quote)[^>]+"
                    r"href=(?P<hquote>['\"])(?P<href>/PressReleseDetail\.aspx\?PRID=\d+)(?P=hquote)[^>]*>"
                    r".*?</a>\s*<span[^>]*>\s*Posted on:\s*(?P<date>\d{1,2}\s+[A-Za-z]+\s+\d{4})",
                    re.I | re.S,
                )
                for match in pattern.finditer(listing):
                    published = datetime.strptime(match.group("date"), "%d %b %Y").replace(tzinfo=timezone.utc)
                    normalized = self.normalize_item({
                        "title": clean_html_text(match.group("title")),
                        "link": urljoin(self.listing_url, match.group("href")),
                        "pub_date": published.strftime("%a, %d %b %Y %H:%M:%S %z"),
                        "description": clean_html_text(match.group("title")),
                        "category": "Press Release",
                    })
                    if normalized:
                        items.append(normalized)
                    if len(items) >= 50:
                        break

        if not items:
            log.warning("PIB RSS and releases listing returned no usable items")
        return items

    def normalize_item(self, raw_item: dict) -> dict | None:
        title = raw_item.get("title", "").strip()
        link = raw_item.get("link", "").strip()
        pub_date_str = raw_item.get("pub_date", "")

        if not title or not link:
            return None

        if not self.is_allowed_domain(link):
            log.warning("PIB item link domain not allowed: %s", link)
            return None

        pub_dt = parse_rss_date(pub_date_str) or datetime.now(timezone.utc)
        pub_date_iso = pub_dt.date().isoformat()

        description = raw_item.get("description", "").strip() or title
        category = raw_item.get("category", "").strip() or None

        external_id = f"pib:{link}"

        return {
            "external_id": external_id,
            "title": title,
            "published_at": pub_date_iso,
            "source_name": self.source_name,
            "source_url": link,
            "canonical_url": link,
            "feed_description": description,
            "raw_public_text": description,
            "ministry": category,
            "category": category,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }


class RBIAdapter(BaseSourceAdapter):
    source_id = "rbi"
    source_name = "RBI"

    def __init__(self):
        super().__init__()
        self.feed_url = settings.RBI_RSS_URL
        self.allowed_domains = ["rbi.org.in", "www.rbi.org.in"]

    async def fetch_items(self) -> list[dict]:
        xml_urls = [
            "https://rbi.org.in/pressreleases_rss.xml",
            "https://rbi.org.in/Scripts/BS_PressReleaseDisplay.xml",
        ]
        
        html_page = await self.fetch_http(self.feed_url)
        if html_page:
            found = re.findall(r'href=["\']([^"\']+\.xml)["\']', html_page, re.I)
            for path in found:
                full_url = urljoin(self.feed_url, path)
                if self.is_allowed_domain(full_url) and full_url not in xml_urls:
                    xml_urls.insert(0, full_url)

        items = []
        for xml_url in xml_urls:
            xml_data = await self.fetch_http(xml_url)
            if not xml_data:
                continue

            try:
                root = ET.fromstring(xml_data)
                channel_items = root.findall(".//item")
                for item in channel_items:
                    title = clean_html_text(item.findtext("title") or "")
                    link = (item.findtext("link") or "").strip()
                    pub_date_str = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
                    description = clean_html_text(item.findtext("description") or "")

                    normalized = self.normalize_item({
                        "title": title,
                        "link": link,
                        "pub_date": pub_date_str,
                        "description": description,
                    })
                    if normalized:
                        items.append(normalized)
                if items:
                    break
            except Exception as exc:
                log.warning("RBI RSS parse error for %s: %s", xml_url, exc)
                continue

        if not items:
            log.info("RBI source unavailable or no items found")
        return items

    def normalize_item(self, raw_item: dict) -> dict | None:
        title = raw_item.get("title", "").strip()
        link = raw_item.get("link", "").strip()
        pub_date_str = raw_item.get("pub_date", "")

        if not title or not link:
            return None

        if not self.is_allowed_domain(link):
            return None

        pub_dt = parse_rss_date(pub_date_str) or datetime.now(timezone.utc)
        pub_date_iso = pub_dt.date().isoformat()

        description = raw_item.get("description", "").strip() or title
        external_id = f"rbi:{link}"

        return {
            "external_id": external_id,
            "title": title,
            "published_at": pub_date_iso,
            "source_name": self.source_name,
            "source_url": link,
            "canonical_url": link,
            "feed_description": description,
            "raw_public_text": description,
            "ministry": "Reserve Bank of India",
            "category": "Banking & Monetary Policy",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }


class MEAAdapter(BaseSourceAdapter):
    source_id = "mea"
    source_name = "MEA"

    def __init__(self):
        super().__init__()
        self.feed_url = settings.MEA_RSS_URL
        self.fallback_url = settings.MEA_PRESS_RELEASES_URL
        self.allowed_domains = ["mea.gov.in", "www.mea.gov.in"]

    async def fetch_items(self) -> list[dict]:
        rss_info_page = await self.fetch_http(self.feed_url)
        feed_urls = []
        if rss_info_page:
            found = re.findall(r'href=["\']([^"\']+(?:rss|xml)[^"\']*)["\']', rss_info_page, re.I)
            for path in found:
                full_url = urljoin(self.feed_url, path)
                if self.is_allowed_domain(full_url):
                    feed_urls.append(full_url)

        items = []
        for feed_url in feed_urls:
            xml_data = await self.fetch_http(feed_url)
            if not xml_data:
                continue
            try:
                root = ET.fromstring(xml_data)
                channel_items = root.findall(".//item")
                for item in channel_items:
                    title = clean_html_text(item.findtext("title") or "")
                    link = (item.findtext("link") or "").strip()
                    pub_date_str = item.findtext("pubDate") or ""
                    description = clean_html_text(item.findtext("description") or "")

                    normalized = self.normalize_item({
                        "title": title,
                        "link": link,
                        "pub_date": pub_date_str,
                        "description": description,
                    })
                    if normalized:
                        items.append(normalized)
                if items:
                    break
            except Exception as exc:
                log.warning("MEA RSS parse error for %s: %s", feed_url, exc)
                continue

        if not items:
            log.info("MEA source RSS unavailable or returned zero items")
        return items

    def normalize_item(self, raw_item: dict) -> dict | None:
        title = raw_item.get("title", "").strip()
        link = raw_item.get("link", "").strip()
        pub_date_str = raw_item.get("pub_date", "")

        if not title or not link:
            return None

        if not self.is_allowed_domain(link):
            return None

        pub_dt = parse_rss_date(pub_date_str) or datetime.now(timezone.utc)
        pub_date_iso = pub_dt.date().isoformat()

        description = raw_item.get("description", "").strip() or title
        external_id = f"mea:{link}"

        return {
            "external_id": external_id,
            "title": title,
            "published_at": pub_date_iso,
            "source_name": self.source_name,
            "source_url": link,
            "canonical_url": link,
            "feed_description": description,
            "raw_public_text": description,
            "ministry": "Ministry of External Affairs",
            "category": "International Relations",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
