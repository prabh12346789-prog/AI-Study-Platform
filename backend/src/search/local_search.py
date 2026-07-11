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
                "provider": "local",
            }

        print(f"[local-search] finished with {len(chunks)} chunks", flush=True)

        return {
            "context": PromptBuilder.build_context(chunks),
            "sources": [
                {
                    "document": chunk.get("document_name"),
                    "page_start": chunk.get("metadata", {}).get("page_start"),
                    "page_end": chunk.get("metadata", {}).get("page_end"),
                    "chunk_id": chunk.get("chunk_id"),
                }
                for chunk in chunks
            ],
            "provider": "local",
        }