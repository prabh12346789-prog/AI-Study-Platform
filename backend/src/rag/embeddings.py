from typing import Sequence

from sentence_transformers import SentenceTransformer

from src.core.config import settings


class EmbeddingService:

	_model: SentenceTransformer | None = None
	_model_name: str | None = None

	@classmethod
	def load_model(cls):

		model_name = settings.EMBEDDING_MODEL

		if cls._model is None or cls._model_name != model_name:
			cls._model = SentenceTransformer(model_name)
			cls._model_name = model_name

		return cls._model

	@classmethod
	def generate_embeddings(cls, chunks: Sequence[dict]):

		if not chunks:
			return []

		model = cls.load_model()
		texts = [chunk["text"] for chunk in chunks]
		embeddings = model.encode(texts, normalize_embeddings=True)
		return embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings
