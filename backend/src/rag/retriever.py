from src.core.config import settings
from src.rag.embeddings import EmbeddingService
from src.rag.vector_store import VectorStore


class Retriever:

    def __init__(self):

        self.vector_store = VectorStore()

    def retrieve(self, question: str):

        question_embedding = EmbeddingService.generate_embedding(question)
        search_results = self.vector_store.search(question_embedding, n_results=settings.TOP_K_RESULTS)

        return self._format_results(search_results)

    @staticmethod
    def _format_results(search_results: dict):

        formatted_results = []
        ids = search_results.get("ids", [[]])
        documents = search_results.get("documents", [[]])
        metadatas = search_results.get("metadatas", [[]])
        distances = search_results.get("distances", [[]])

        if not ids or not ids[0]:
            return formatted_results

        for index, item_id in enumerate(ids[0]):
            metadata = metadatas[0][index] if metadatas and metadatas[0] else {}
            document_text = documents[0][index] if documents and documents[0] else ""
            distance = distances[0][index] if distances and distances[0] else None

            score = 0.0
            if distance is not None:
                score = round(1.0 / (1.0 + float(distance)), 4)

            if score < settings.SIMILARITY_THRESHOLD:
                continue

            formatted_results.append(
                {
                    "document_id": metadata.get("document_id"),
                    "document_name": metadata.get("original_name"),
                    "chunk_id": metadata.get("chunk_id", item_id),
                    "text": document_text,
                    "score": score,
                    "metadata": {
                        "page_start": metadata.get("page_start"),
                        "page_end": metadata.get("page_end"),
                        "source_type": metadata.get("source_type", "pdf"),
                        "article_id": metadata.get("article_id"),
                        "publisher": metadata.get("publisher"),
                        "source_url": metadata.get("source_url"),
                        "publication_date": metadata.get("publication_date"),
                        "subject": metadata.get("subject"),
                        "topic": metadata.get("topic"),
                        "retrieved_at": metadata.get("retrieved_at"),
                        "content_hash": metadata.get("content_hash"),
                    },
                }
            )

        return formatted_results
