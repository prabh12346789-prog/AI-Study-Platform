import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory of src to sys.path so we can import src
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core.config import settings
from src.memory.storage import get_session_factory
from src.pwonlyias.shared import is_valid_pwonlyias_source_url, extract_pdf_blocks, normalize_subject
from src.upsc_books.service import UPSCBooksService, detect_chapters_from_blocks
from src.upsc_books.models import UPSCBook, BookChapter, BookCollection
from sqlalchemy import select

def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def main():
    parser = argparse.ArgumentParser(description="Manual PDF Importer for UPSC Books")
    parser.add_argument("--type", required=True, choices=["book"], help="Type of import (book only)")
    parser.add_argument("--title", required=True, help="Title of the resource")
    parser.add_argument("--subject", required=True, help="UPSC Subject")
    parser.add_argument("--collection", required=True, help="Collection / Hub name")
    parser.add_argument("--source-url", required=True, help="Official PWOnlyIAS webpage source URL")
    parser.add_argument("--file", required=True, help="Path to local PDF file")
    parser.add_argument("--topic", default="", help="Optional topic/chapter name")
    parser.add_argument("--language", default="english", help="Language (default: english)")
    parser.add_argument("--prelims", action="store_true", help="Relevant for Prelims")
    parser.add_argument("--mains", action="store_true", help="Relevant for Mains")
    parser.add_argument("--qa-bank", action="store_true", help="Solves practice or practice question bank PDF")
    parser.add_argument("--dry-run", action="store_true", help="Dry run only, make no database or file changes")
    parser.add_argument("--force-reindex", action="store_true", help="Force re-indexing and override duplicate checks")

    args = parser.parse_args()

    # Ambiguity check
    if args.qa_bank and (args.prelims or args.mains):
        print(json.dumps({"error": "Ambiguous classification: --qa-bank cannot be combined with --prelims or --mains"}))
        sys.exit(1)

    # 1. Validation
    # Validate URL
    if not is_valid_pwonlyias_source_url(args.source_url):
        print(json.dumps({"error": f"Invalid source URL: {args.source_url}. Must belong to official PWOnlyIAS domain."}))
        sys.exit(1)

    # Validate Local File
    pdf_path = Path(args.file)
    if not pdf_path.exists():
        print(json.dumps({"error": f"File does not exist: {args.file}"}))
        sys.exit(1)
    if pdf_path.is_dir():
        print(json.dumps({"error": f"Specified path is a directory, not a file: {args.file}"}))
        sys.exit(1)
    
    # Size check (100MB limit)
    file_size = pdf_path.stat().st_size
    if file_size == 0:
        print(json.dumps({"error": "File is empty"}))
        sys.exit(1)
    if file_size > 100 * 1024 * 1024:
        print(json.dumps({"error": "File size exceeds maximum limit of 100MB"}))
        sys.exit(1)

    # Verify %PDF signature
    with open(pdf_path, "rb") as f:
        header = f.read(1024).lstrip()
        if not header.startswith(b"%PDF"):
            print(json.dumps({"error": "Invalid PDF signature (does not start with %PDF)"}))
            sys.exit(1)

    # Calculate checksum
    checksum = compute_sha256(pdf_path)

    # Normalized Subject
    norm_subject = normalize_subject(args.subject)

    # Generate Safe ID based on composite hash to avoid collision on same URL
    norm_title_clean = "".join(c for c in args.title.lower() if c.isalnum())
    r_kind = "study_book"
    if args.qa_bank:
        r_kind = "qa_bank"
    hash_str = f"{args.source_url}_{norm_title_clean}_{r_kind}"
    url_hash = hashlib.md5(hash_str.encode()).hexdigest()[:12]
    resource_id = f"{args.type}-{url_hash}"

    # Database Session Factory
    sessions = get_session_factory()

    # Check for duplicate using priority matching
    existing_id = None
    with sessions() as session:
        # Priority 1: exact PDF SHA-256 checksum + resource_kind (content type)
        q = select(UPSCBook).where(
            UPSCBook.content_checksum == checksum,
            UPSCBook.resource_kind == r_kind
        )
        existing = session.scalars(q).first()

        # Priority 2: existing stable ID
        if not existing:
            existing = session.get(UPSCBook, resource_id)

        # Priority 3: normalized title + collection + resource_kind (content type)
        if not existing:
            col_id = f"col-{hashlib.md5(args.collection.encode()).hexdigest()[:12]}"
            q = select(UPSCBook).where(
                UPSCBook.title.ilike(args.title),
                UPSCBook.collection_id == col_id,
                UPSCBook.resource_kind == r_kind
            )
            existing = session.scalars(q).first()

        if existing:
            existing_id = existing.id

    if existing_id and not args.force_reindex:
        print(json.dumps({
            "status": "duplicate",
            "message": "Resource already exists in database.",
            "id": existing_id
        }, indent=2))
        return

    # Read bytes for extraction
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    # Extract Blocks
    blocks, page_count, ext_status = extract_pdf_blocks(pdf_bytes)

    # Set status fields
    if ext_status == "ready":
        content_status = "ready"
    elif ext_status == "image_only":
        content_status = "unavailable"
        blocks = []
    else:
        content_status = "unavailable"
        blocks = []

    # Local Storage Path Resolution
    # backend/data/pwonlyias/notes/<id>/original.pdf
    # backend/data/pwonlyias/books/<id>/original.pdf
    backend_root = Path(__file__).resolve().parents[2]
    storage_dir = backend_root / "data" / "pwonlyias" / (f"{args.type}s") / resource_id
    dest_pdf_path = storage_dir / "original.pdf"

    if args.dry_run:
        print(json.dumps({
            "status": "dry_run",
            "id": resource_id,
            "title": args.title,
            "subject": norm_subject,
            "pages": page_count,
            "extraction_status": ext_status,
            "content_status": content_status,
            "checksum": checksum,
            "expected_storage_path": str(dest_pdf_path)
        }, indent=2))
        return

    # Write file copies
    storage_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf_path, dest_pdf_path)

    # Save to DB and index
    target_id = existing_id if existing_id else resource_id
    indexing_status = "indexed"
    svc = UPSCBooksService()
    with sessions() as session:
        # Upsert Collection
        col_id = f"col-{hashlib.md5(args.collection.encode()).hexdigest()[:12]}"
        col_obj = session.get(BookCollection, col_id)
        if not col_obj:
            col_obj = BookCollection(
                id=col_id,
                provider="PWOnlyIAS",
                title=args.collection,
                slug=col_id,
                collection_type="books",
                official_source_url=args.source_url
            )
            session.add(col_obj)

        # Upsert Book
        book_obj = session.get(UPSCBook, target_id)
        if not book_obj:
            book_obj = UPSCBook(id=target_id, slug=target_id)
        
        book_obj.collection_id = col_id
        book_obj.provider = "PWOnlyIAS"
        book_obj.title = args.title
        book_obj.normalized_subject = norm_subject
        book_obj.official_source_url = args.source_url
        book_obj.official_pdf_url = args.source_url
        book_obj.canonical_url = f"pwonlyias:book:{target_id}"
        book_obj.content_status = content_status
        book_obj.extraction_status = ext_status
        book_obj.content_checksum = checksum
        book_obj.page_count = page_count
        book_obj.content_blocks_json = blocks

        # Classification logic
        r_kind = "study_book"
        p_rel = args.prelims
        m_rel = args.mains
        if args.qa_bank:
            r_kind = "qa_bank"
            p_rel = False
            m_rel = False
        else:
            pass
        
        book_obj.prelims_relevant = p_rel
        book_obj.mains_relevant = m_rel
        book_obj.resource_kind = r_kind

        session.merge(book_obj)

        # Chapters
        chs = detect_chapters_from_blocks(blocks)
        for c in chs:
            session.merge(BookChapter(
                id=f"ch-{target_id}-{c['chapter_order']}",
                book_id=target_id,
                title=c["title"],
                slug=c["slug"],
                chapter_order=c["chapter_order"],
                page_start=c["page_start"],
                page_end=c["page_end"]
            ))
        
        # Indexing — only attempted when extraction succeeded
        if content_status == "ready":
            try:
                svc._index(book_obj)
                indexing_status = "indexed"
            except Exception as index_err:
                err_msg = str(index_err).lower()
                if ("ollama embeddings are unavailable" in err_msg
                        or "ollama embedding model" in err_msg
                        or "connection" in err_msg):
                    indexing_status = "indexing_skipped"
                else:
                    indexing_status = "indexing_failed"
        else:
            # Extraction failed — indexing was never attempted
            indexing_status = "not_ready"

        book_obj.indexing_status = indexing_status
        session.commit()

    print(json.dumps({
        "status": "success",
        "id": target_id,
        "title": args.title,
        "subject": norm_subject,
        "pages": page_count,
        "extraction_status": ext_status,
        "indexing_status": indexing_status,
        "content_status": content_status
    }, indent=2))

if __name__ == "__main__":
    main()
