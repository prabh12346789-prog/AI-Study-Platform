from pathlib import Path
from typing import Sequence

import logging

from src.core.config import settings


class VectorStore:

	_client = None
	_client_path: str | None = None
	_collection = None
	_collection_name: str | None = None

	def __init__(self):

		if settings.VECTOR_DB.lower() != "chromadb":
			raise ValueError(f"Unsupported vector database: {settings.VECTOR_DB}")

		self.db_path = Path(settings.CHROMA_DB_PATH)
		self.db_path.mkdir(parents=True, exist_ok=True)
		self.collection = self._get_collection()

	@classmethod
	def _get_client(cls):

		db_path = str(Path(settings.CHROMA_DB_PATH))

		if cls._client is None or cls._client_path != db_path:
			logging.getLogger("startup").info("Chroma initialization started: %s", db_path)
			import chromadb
			Path(db_path).mkdir(parents=True, exist_ok=True)
			cls._client = chromadb.PersistentClient(path=db_path)
			cls._client_path = db_path
			logging.getLogger("startup").info("Chroma client initialized")

		return cls._client

	@classmethod
	def _get_collection(cls):

		collection_name = settings.CHROMA_COLLECTION

		if cls._collection is None or cls._collection_name != collection_name:
			client = cls._get_client()
			cls._collection = client.get_or_create_collection(name=collection_name)
			cls._collection_name = collection_name

		return cls._collection

	@classmethod
	def is_initialized(cls) -> bool:
		return cls._client is not None and cls._collection is not None

	def store_vectors(
		self,
		document_id: str,
		original_name: str,
		chunks: Sequence[dict],
		embeddings: Sequence[Sequence[float]],
	):

		if not chunks:
			return []

		if len(chunks) != len(embeddings):
			raise ValueError("Chunks and embeddings must have the same length")

		ids = []
		documents = []
		metadatas = []

		for chunk, embedding in zip(chunks, embeddings):
			chunk_id = int(chunk["chunk_id"])

			ids.append(f"{document_id}_{chunk_id}")
			documents.append(chunk["text"])
			metadata = {
				"chunk_id": chunk_id,
				"document_id": document_id,
				"original_name": original_name,
				"word_count": int(chunk["word_count"]),
				"embedding_model": settings.EMBEDDING_MODEL,
			}

			page_start = chunk.get("page_start")
			page_end = chunk.get("page_end")

			if page_start is not None:
				metadata["page_start"] = int(page_start)

			if page_end is not None:
				metadata["page_end"] = int(page_end)

			metadatas.append(metadata)

		self.collection.add(
			ids=ids,
			embeddings=embeddings,
			documents=documents,
			metadatas=metadatas,
		)

		return ids

	def search(self, query_embedding, n_results: int | None = None, document_id: str | None = None):

		results_limit = n_results or settings.TOP_K_RESULTS
		query_kwargs = {
			"query_embeddings": [query_embedding],
			"n_results": results_limit,
			"include": ["documents", "metadatas", "distances"],
		}

		if document_id:
			query_kwargs["where"] = {"document_id": document_id}

		results = self.collection.query(
			**query_kwargs,
		)

		return results

	def query(self, query_embeddings, n_results: int = 5):

		return self.collection.query(
			query_embeddings=query_embeddings,
			n_results=n_results,
		)
