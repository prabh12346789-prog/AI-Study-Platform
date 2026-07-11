from src.core.config import settings
from src.search.base import BaseSearchProvider
from src.search.local_search import LocalSearch
from src.search.web_search import WebSearch


class SearchProvider(BaseSearchProvider):

    def __init__(self):
        self.local_search = LocalSearch()
        self.web_search = WebSearch()

    def search(self, question: str):

        print(f"[search-provider] search start: question={question!r}", flush=True)

        strategy = settings.SEARCH_PROVIDER.lower()

        if strategy == "local_only":
            print("[search-provider] strategy=local_only -> LocalSearch", flush=True)
            result = self.local_search.search(question)
            print(f"[search-provider] search finished: provider={result.get('provider')!r}, context_present={bool(result.get('context'))}", flush=True)
            return result

        if strategy == "web_only" and settings.ENABLE_WEB_SEARCH:
            print("[search-provider] strategy=web_only -> WebSearch", flush=True)
            web_result = self.web_search.search(question)
            if web_result["context"]:
                print(f"[search-provider] search finished: provider={web_result.get('provider')!r}, context_present=True", flush=True)
                return web_result
            print("[search-provider] web search returned no context", flush=True)
            return {
                "context": "",
                "sources": [],
                "provider": "web",
            }

        print("[search-provider] strategy=local_first -> LocalSearch", flush=True)
        local_result = self.local_search.search(question)

        if local_result["context"]:
            print(f"[search-provider] search finished: provider={local_result.get('provider')!r}, context_present=True", flush=True)
            return local_result

        if settings.ENABLE_WEB_SEARCH:
            print("[search-provider] local search empty -> WebSearch", flush=True)
            web_result = self.web_search.search(question)
            if web_result["context"]:
                print(f"[search-provider] search finished: provider={web_result.get('provider')!r}, context_present=True", flush=True)
                return web_result

        print(f"[search-provider] search finished: provider={local_result.get('provider')!r}, context_present={bool(local_result.get('context'))}", flush=True)
        return local_result