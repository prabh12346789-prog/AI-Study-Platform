import logging

from src.core.config import settings
from src.search.base import BaseSearchProvider
from src.search.grounding import GroundingDecisionService
from src.search.local_search import LocalSearch
from src.search.web_search import WebSearch
from src.rag.prompt_builder import PromptBuilder

log = logging.getLogger(__name__)


class SearchProvider(BaseSearchProvider):
    def __init__(self, local_search=None, web_search=None, grounding=None):
        self.local_search = local_search or LocalSearch(); self.web_search = web_search or WebSearch()
        self.grounding = grounding or GroundingDecisionService()

    def search(self, question: str, requested_operation: str = "chat"):
        local = self.local_search.search(question)
        local_chunks = local.get("chunks", [])
        decision = self.grounding.decide(chunks=local_chunks, question=question, requested_operation=requested_operation)
        threshold = (settings.ROADMAP_MIN_GROUNDING_CONFIDENCE if requested_operation == "roadmap"
                     else settings.CHAT_MIN_GROUNDING_CONFIDENCE)
        useful_local = [c for c in local_chunks if float(c.get("score", 0)) >= threshold]
        log.info("Grounding local_count=%d operation=%s status=%s confidence=%.3f web_fallback=%s",
                 len(local_chunks), requested_operation, decision.status, decision.confidence, decision.use_web_fallback)
        if decision.status == "sufficient" or settings.SEARCH_PROVIDER.lower() == "local_only":
            useful_ids = {str(c.get("chunk_id")) for c in useful_local}
            sources = [s for s in local.get("sources", []) if str(s.get("chunk_id")) in useful_ids]
            return {**local, "context": PromptBuilder.build_context(useful_local), "sources": sources, "chunks": useful_local,
                    "grounding": decision.as_dict(), "grounding_enforced": True, "web_fallback_used": False}
        if not decision.use_web_fallback:
            return {**local, "grounding": decision.as_dict(), "grounding_enforced": True, "web_fallback_used": False}
        web = self.web_search.search(question)
        web_decision = self.grounding.decide(chunks=web.get("chunks", []), question=question,
                                             requested_operation=requested_operation)
        if web_decision.status != "sufficient":
            return {**local, "context": "", "sources": [], "chunks": [], "grounding": web_decision.as_dict(),
                    "grounding_enforced": True, "web_fallback_used": True, "web_error": web.get("error")}
        combined_chunks = useful_local + web.get("chunks", [])
        sources = local.get("sources", []) if useful_local else []
        sources += web.get("sources", [])
        context_parts = [local.get("context", "") if useful_local else "", web.get("context", "")]
        log.info("Grounding approved_web=%d rejected_web=%d cache_hits=%d final_sources=%d",
                 len(web.get("sources", [])), web.get("rejected_count", 0), web.get("cache_hits", 0), len(sources))
        return {"context": "\n\n".join(part for part in context_parts if part), "sources": sources,
                "chunks": combined_chunks, "provider": "local+trusted_web" if useful_local else "trusted_web",
                "grounding": web_decision.as_dict(), "grounding_enforced": True, "web_fallback_used": True}
