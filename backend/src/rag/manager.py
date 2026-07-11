import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import UploadFile
import shutil

from src.rag.chunker import Chunker
from src.rag.embeddings import EmbeddingService
from src.rag.parser import PDFParser
from src.rag.vector_store import VectorStore
from src.core.config import settings


class DocumentManager:

    BASE_DIR = Path("uploads/users")

    @classmethod
    async def create_document(cls, file: UploadFile, user_id: str = "user_001"):

        document_id = str(uuid.uuid4())

        document_dir = cls._build_document_dir(user_id, document_id)
        document_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = cls.save_pdf(document_dir, file)
        parsed = PDFParser.extract_text(pdf_path)
        cls.save_extracted_text(document_dir, parsed["text"])

        cls.save_processing(document_dir, {"chunked": False, "embedded": False, "indexed": False})

        chunks = Chunker.chunk_document(document_dir)
        cls.save_chunks(document_dir, chunks)
        cls.update_processing(document_dir, {"chunked": True})

        embeddings = await asyncio.to_thread(EmbeddingService.generate_embeddings, chunks)

        vector_store = VectorStore()
        await asyncio.to_thread(
            vector_store.store_vectors,
            document_id,
            file.filename,
            chunks,
            embeddings,
        )

        cls.update_processing(document_dir, {"embedded": True, "indexed": True})

        metadata = {
            "document_id": document_id,
            "original_name": file.filename,
            "stored_name": "original.pdf",
            "user_id": user_id,
            "uploaded_at": datetime.utcnow().isoformat(),
            "pages": 0,
            "word_count": 0,
            "chunks": 0,
            "embedding_model": None,
            "vectorized": False,
            "status": "uploaded"
        }

        cls.save_metadata(document_dir, metadata)
        metadata = cls.update_metadata(document_dir, parsed, len(chunks))
        cls.save_metadata(document_dir, metadata)

        return metadata

    @classmethod
    def _build_document_dir(cls, user_id: str, document_id: str) -> Path:

        return cls.BASE_DIR / user_id / "documents" / document_id

    @classmethod
    def save_pdf(cls, document_dir: Path, file: UploadFile) -> Path:

        pdf_path = document_dir / "original.pdf"

        with open(pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return pdf_path

    @staticmethod
    def save_metadata(document_dir: Path, metadata: dict):

        metadata_path = document_dir / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as file:
            json.dump(metadata, file, indent=4)

    @staticmethod
    def load_metadata(document_dir: Path):

        metadata_path = document_dir / "metadata.json"

        with open(metadata_path, "r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def update_metadata(document_dir: Path, parsed: dict, chunks_count: int):

        metadata = DocumentManager.load_metadata(document_dir)

        metadata["pages"] = parsed["pages"]
        metadata["word_count"] = len(parsed["text"].split())
        metadata["chunks"] = chunks_count
        metadata["embedding_model"] = settings.EMBEDDING_MODEL
        metadata["vectorized"] = True
        metadata["status"] = "embedded"
        return metadata

    @staticmethod
    def save_chunks(document_dir: Path, chunks: list):

        chunks_path = document_dir / "chunks.json"
        with open(chunks_path, "w", encoding="utf-8") as file:
            json.dump(chunks, file, indent=4)

    @staticmethod
    def save_processing(document_dir: Path, processing: dict):

        processing_path = document_dir / "processing.json"
        with open(processing_path, "w", encoding="utf-8") as file:
            json.dump(processing, file, indent=4)

    @staticmethod
    def load_processing(document_dir: Path):

        processing_path = document_dir / "processing.json"

        with open(processing_path, "r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def update_processing(document_dir: Path, updates: dict):

        processing = DocumentManager.load_processing(document_dir)
        processing.update(updates)
        DocumentManager.save_processing(document_dir, processing)
        return processing

    @staticmethod
    def save_extracted_text(document_dir: Path, text: str):

        extracted_text_path = document_dir / "extracted.txt"
        extracted_text_path.write_text(text, encoding="utf-8")