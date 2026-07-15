from src.rag.prompt_builder import PromptBuilder
from src.rag.retriever import Retriever


class LocalSearch:

    def __init__(self):
        self.retriever = Retriever()

    def search(self, question: str):

        print(f"[local-search] start: question={question!r}", flush=True)
        print("[local-search] before Retriever.retrieve()", flush=True)

        chunks = self.retriever.retrieve(question)
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
