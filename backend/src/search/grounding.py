from __future__ import annotations

from dataclasses import dataclass

from src.core.config import settings


@dataclass(frozen=True)
class GroundingDecision:
    status: str
    confidence: float
    reason: list[str]
    use_web_fallback: bool

    def as_dict(self):
        return {"status": self.status, "confidence": self.confidence, "reason": self.reason,
                "use_web_fallback": self.use_web_fallback}


class GroundingDecisionService:
    @staticmethod
    def requires_factual_information(question: str) -> bool:
        text = " ".join(question.casefold().split())
        if not text or any(marker in text for marker in ("hello", "hi there", "rewrite", "paraphrase", "improve this sentence")):
            return False
        return any(marker in text for marker in (
            "what", "why", "how", "when", "who", "explain", "discuss", "evaluate", "analyse",
            "article", "act", "constitution", "history", "background", "policy", "economy", "geography",
        ))

    def decide(self, *, chunks: list[dict], question: str, requested_operation: str) -> GroundingDecision:
        threshold = (settings.ROADMAP_MIN_GROUNDING_CONFIDENCE if requested_operation == "roadmap"
                     else settings.CHAT_MIN_GROUNDING_CONFIDENCE)
        useful = [chunk for chunk in chunks if chunk.get("text", "").strip() and float(chunk.get("score", 0)) >= threshold]
        if not chunks:
            status, confidence, reasons = "no_context", 0.0, ["No retrieved context was available"]
        elif not useful:
            best = max((float(chunk.get("score", 0)) for chunk in chunks), default=0.0)
            status, confidence, reasons = "insufficient", round(best, 3), ["Retrieved context was below the relevance threshold"]
        else:
            confidence = round(min(1.0, sum(float(chunk.get("score", 0)) for chunk in useful) / len(useful)), 3)
            status, reasons = "sufficient", [f"{len(useful)} relevant source chunk(s) met the configured threshold"]
        return GroundingDecision(status, confidence, reasons,
            status != "sufficient" and settings.ENABLE_WEB_SEARCH and self.requires_factual_information(question))
