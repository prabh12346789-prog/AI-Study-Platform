import asyncio
import json
import uuid
from datetime import datetime, timezone
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

        metadata = {
            "document_id": document_id,
            "original_name": file.filename or "document.pdf",
            "stored_name": "original.pdf",
            "user_id": user_id,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "pages": None,
            "word_count": None,
            "chunks": None,
            "embedding_provider": settings.EMBEDDING_PROVIDER,
            "embedding_model": settings.OLLAMA_EMBEDDING_MODEL,
            "embedding_collection": settings.CHROMA_COLLECTION,
            "vectorized": False,
            "status": "processing",
        }
        cls.save_metadata(document_dir, metadata)
        cls.save_processing(document_dir, {"chunked": False, "embedded": False, "indexed": False})

        try:
            pdf_path = cls.save_pdf(document_dir, file)
            parsed = PDFParser.extract_text(pdf_path)
            cls.save_extracted_text(document_dir, parsed["text"])

            chunks = Chunker.chunk_document(document_dir)
        # The current chunker works on the concatenated extraction.  Retain
        # page provenance for single-page chunks, and provide a conservative
        # document range when a chunk spans the extraction.
            for chunk in chunks:
                chunk["page_start"] = 1
                chunk["page_end"] = parsed["pages"]
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

            metadata = cls.update_metadata(document_dir, parsed, len(chunks))
            cls.save_metadata(document_dir, metadata)
        except Exception:
            metadata = cls.load_metadata(document_dir)
            metadata.update({"status": "failed", "vectorized": False})
            cls.save_metadata(document_dir, metadata)
            raise

        return metadata

    @classmethod
    def list_documents(cls, user_id: str = "user_001") -> list[dict]:
        documents_root = cls.BASE_DIR / user_id / "documents"
        if not documents_root.exists():
            return []
        documents: list[dict] = []
        for document_dir in documents_root.iterdir():
            if not document_dir.is_dir():
                continue
            metadata_path = document_dir / "metadata.json"
            processing_path = document_dir / "processing.json"
            try:
                metadata = cls.load_metadata(document_dir) if metadata_path.exists() else {}
                processing = cls.load_processing(document_dir) if processing_path.exists() else {}
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            document_id = str(metadata.get("document_id") or document_dir.name)
            uploaded_at = metadata.get("uploaded_at")
            if not uploaded_at:
                uploaded_at = datetime.fromtimestamp(document_dir.stat().st_mtime, timezone.utc).isoformat()
            embedding_model = metadata.get("embedding_model")
            embedding_provider = metadata.get("embedding_provider")
            embedding_collection = metadata.get("embedding_collection")
            model_is_active = embedding_model == settings.OLLAMA_EMBEDDING_MODEL
            collection_is_active = embedding_collection in {None, settings.CHROMA_COLLECTION} and model_is_active
            indexed = bool(processing.get("indexed") or metadata.get("vectorized")) and collection_is_active
            legacy = bool(metadata.get("vectorized")) and embedding_model is not None and not model_is_active
            status = "indexed" if indexed else "legacy" if legacy else str(metadata.get("status") or ("processing" if processing else "failed"))
            documents.append({
                "document_id": document_id,
                "name": str(metadata.get("original_name") or "original.pdf"),
                "uploaded_at": uploaded_at,
                "status": status,
                "page_count": metadata.get("pages"),
                "chunk_count": metadata.get("chunks"),
                "embedding_provider": embedding_provider or (settings.EMBEDDING_PROVIDER if model_is_active else None),
                "embedding_model": embedding_model,
                "embedding_collection": embedding_collection or (settings.CHROMA_COLLECTION if model_is_active else None),
                "indexed": indexed,
            })
        return sorted(documents, key=lambda item: item["uploaded_at"], reverse=True)

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
        metadata["embedding_provider"] = settings.EMBEDDING_PROVIDER
        metadata["embedding_model"] = settings.OLLAMA_EMBEDDING_MODEL
        metadata["embedding_collection"] = settings.CHROMA_COLLECTION
        metadata["vectorized"] = True
        metadata["status"] = "indexed"
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
