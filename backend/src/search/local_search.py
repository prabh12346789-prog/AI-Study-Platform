import logging
import re
import unicodedata

from sqlalchemy import text

from src.rag.prompt_builder import PromptBuilder
from src.rag.embeddings import EmbeddingProviderError
from src.rag.retriever import Retriever
from src.memory.storage import get_session_factory

log = logging.getLogger(__name__)
STOP_WORDS = {"a", "an", "and", "are", "for", "how", "in", "is", "of", "on", "the", "to", "what", "why", "with"}


class LocalSearch:

    def __init__(self, retriever=None, lexical_search=None):
        self._retriever = retriever
        self._lexical_search = lexical_search or self._search_extracted_books

    @property
    def retriever(self):
        if self._retriever is None:
            self._retriever = Retriever()
        return self._retriever

    @retriever.setter
    def retriever(self, value):
        self._retriever = value

    def search(self, question: str):

        print(f"[local-search] start: question={question!r}", flush=True)
        print("[local-search] before Retriever.retrieve()", flush=True)

        try:
            chunks = self.retriever.retrieve(question)
        except EmbeddingProviderError as error:
            log.warning("Local retrieval unavailable: %s", error)
            chunks = self._lexical_search(question)
            if chunks:
                log.info("Using %d grounded extracted-book chunks as lexical fallback", len(chunks))
            else:
                # Retrieval is an enhancement, not a reason to crash all chat.
                # The shared grounding layer will decide whether trusted web
                # fallback is required when no local chunks are available.
                return {
                    "context": "",
                    "sources": [],
                    "chunks": [],
                    "provider": "local_unavailable",
                    "error": str(error),
                }
        if not chunks:
            chunks = self._lexical_search(question)
            if chunks:
                log.info("Semantic retrieval returned no matches; using %d extracted-book keyword chunks", len(chunks))
        print(f"[local-search] after Retriever.retrieve(): chunks={len(chunks)}", flush=True)

        if not chunks:
            print("[local-search] finished with 0 chunks", flush=True)
            return {
                "context": "",
                "sources": [],
                "chunks": [],
                "provider": "local",
            }

        print(f"[local-search] finished with {len(chunks)} chunks", flush=True)

        return {
            "context": PromptBuilder.build_context(chunks),
            "sources": [
                {
                    "source_type": "current_affairs" if chunk.get("metadata", {}).get("source_type") == "current_affairs" else "pdf",
                    "title": chunk.get("document_name"),
                    "document": chunk.get("document_name"),
                    "document_name": chunk.get("document_name"),
                    "url": chunk.get("metadata", {}).get("source_url"),
                    "publisher": chunk.get("metadata", {}).get("publisher"),
                    "publication_date": chunk.get("metadata", {}).get("publication_date"),
                    "retrieved_at": chunk.get("metadata", {}).get("retrieved_at"),
                    "page_start": chunk.get("metadata", {}).get("page_start"),
                    "page_end": chunk.get("metadata", {}).get("page_end"),
                    "chunk_id": chunk.get("chunk_id"),
                }
                for chunk in chunks
            ],
            "chunks": [{**chunk, "source_type": "pdf"} for chunk in chunks],
            "provider": "local",
        }

    @staticmethod
    def _search_extracted_books(question: str) -> list[dict]:
        """Bounded SQLite keyword fallback over already-extracted study books."""
        terms = [word for word in re.findall(r"[a-z0-9]+", question.casefold()) if len(word) > 2 and word not in STOP_WORDS]
        terms = list(dict.fromkeys(terms))[:6]
        if not terms:
            return []
        clauses = " OR ".join(f"lower(json_extract(j.value, '$.text')) LIKE :term{index}" for index in range(len(terms)))
        query = text(f"""
            SELECT b.id, b.title, b.official_source_url,
                   json_extract(j.value, '$.text') AS block_text,
                   COALESCE(json_extract(j.value, '$.page_start'), json_extract(j.value, '$.page_ref'), 1) AS page_start,
                   COALESCE(json_extract(j.value, '$.page_end'), json_extract(j.value, '$.page_ref'), 1) AS page_end
            FROM upsc_books AS b, json_each(b.content_blocks_json) AS j
            WHERE b.active = 1 AND b.extraction_status = 'ready'
              AND b.resource_kind = 'study_book' AND ({clauses})
            LIMIT 400
        """)
        params = {f"term{index}": f"%{term}%" for index, term in enumerate(terms)}
        phrase = " ".join(terms)
        candidates = []
        try:
            with get_session_factory()() as session:
                rows = session.execute(query, params).all()
        except Exception as error:
            log.warning("Extracted-book lexical fallback unavailable: %s", error)
            return []
        for book_id, title, source_url, raw_text, page_start, page_end in rows:
            block_text = "".join(character for character in str(raw_text or "") if not unicodedata.category(character).startswith("C"))
            block_text = re.sub(r"\s+", " ", block_text).strip()
            if len(block_text) < 45 or len(block_text.split()) < 8:
                continue
            lowered = block_text.casefold()
            matched = sum(term in lowered for term in terms)
            coverage = matched / len(terms)
            if coverage < .6:
                continue
            score = min(.98, .45 + .3 * coverage + (.2 if phrase in lowered else 0))
            candidates.append({
                "chunk_id": f"book-{book_id}-{page_start}",
                "document_id": str(book_id),
                "document_name": str(title),
                "text": block_text[:1600],
                "score": score,
                "metadata": {
                    "source_type": "pdf", "page_start": int(page_start or 1), "page_end": int(page_end or page_start or 1),
                    "source_url": source_url if str(source_url or "").startswith(("http://", "https://")) else None,
                    "retrieval_method": "extracted_book_keyword",
                },
            })
        candidates.sort(key=lambda item: (-item["score"], len(item["text"])))
        return candidates[:5]
