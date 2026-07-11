import re
from urllib.parse import quote_plus

import requests

from src.core.config import settings


class WebSearch:

    SEARCH_URL = "https://html.duckduckgo.com/html/?q={query}"

    def search(self, question: str):

        print(f"[web-search] start: question={question!r}", flush=True)

        results = self._search_web(question)
        print(f"[web-search] end: results={len(results)}", flush=True)

        return {
            "context": self._build_context(results),
            "sources": [
                {
                    "title": result.get("title"),
                    "url": result.get("url"),
                }
                for result in results
            ],
            "provider": "web",
        }

    def _search_web(self, question: str):

        query = quote_plus(question)
        response = requests.get(
            self.SEARCH_URL.format(query=query),
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        return self._parse_results(response.text)

    def _parse_results(self, html: str):

        results = []
        pattern = re.compile(
            r'<a rel="nofollow" class="result__a" href="(?P<url>[^"]+)">(?P<title>.*?)</a>.*?'
            r'<a class="result__snippet">(?P<snippet>.*?)</a>',
            re.DOTALL,
        )

        for match in pattern.finditer(html):
            title = re.sub(r"<.*?>", "", match.group("title"))
            snippet = re.sub(r"<.*?>", "", match.group("snippet"))
            url = match.group("url")

            results.append(
                {
                    "title": self._clean_text(title),
                    "snippet": self._clean_text(snippet),
                    "url": url,
                }
            )

            if len(results) >= settings.MAX_WEB_RESULTS:
                break

        return results

    @staticmethod
    def _clean_text(text: str):

        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _build_context(results: list[dict]):

        if not results:
            return ""

        blocks = []
        for result in results:
            title = result.get("title") or "Web Source"
            snippet = result.get("snippet") or ""
            url = result.get("url") or ""

            blocks.append(f"{title}\n{snippet}\n{url}".strip())

        return "\n\n".join(blocks).strip()