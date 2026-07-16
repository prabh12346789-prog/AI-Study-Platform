from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PdfDocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    name: str
    uploaded_at: datetime
    status: str
    page_count: int | None = None
    chunk_count: int | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_collection: str | None = None
    indexed: bool
