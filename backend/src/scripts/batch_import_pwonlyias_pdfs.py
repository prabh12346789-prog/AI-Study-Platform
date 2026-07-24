import argparse
import csv
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
    parser = argparse.ArgumentParser(description="Batch PDF Importer for UPSC Books")
    parser.add_argument("--folder", required=True, help="Folder containing PDF files")
    parser.add_argument("--metadata", required=True, help="Path to CSV metadata file")
    parser.add_argument("--dry-run", action="store_true", help="Dry run only, make no database or file changes")
    parser.add_argument("--include-unmapped", action="store_true", help="Include PDFs in folder that are not mapped in CSV")
    parser.add_argument("--force-reindex", action="store_true", help="Force re-indexing and override duplicate checks")

    args = parser.parse_args()

    folder_path = Path(args.folder)
    metadata_path = Path(args.metadata)

    if not folder_path.is_dir():
        print(json.dumps({"error": f"Folder does not exist or is not a directory: {args.folder}"}))
        sys.exit(1)

    if not metadata_path.is_file():
        print(json.dumps({"error": f"Metadata file does not exist or is not a file: {args.metadata}"}))
        sys.exit(1)

    # Read CSV metadata
    csv_rows = []
    try:
        with open(metadata_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            # Normalize headers
            headers = [h.strip().lower() for h in (reader.fieldnames or [])]
            for row in reader:
                norm_row = {}
                for k, v in row.items():
                    if k:
                        norm_row[k.strip().lower()] = v.strip() if v else ""
                csv_rows.append(norm_row)
    except Exception as e:
        print(json.dumps({"error": f"Could not read metadata CSV file: {e}"}))
        sys.exit(1)

    # Scan PDFs in folder
    all_pdfs = {p.name.lower(): p for p in folder_path.glob("*.pdf")}

    # Stats counters
    stats = {
        "total_pdfs": len(all_pdfs),
        "successful_imports": 0,
        "duplicates": 0,
        "indexed": 0,
        "indexing_skipped": 0,
        "indexing_failures": 0,
        "image_only_pdfs": 0,
        "extraction_failures": 0,
        "validation_failures": 0
    }

    # Match every CSV row to a real PDF in the folder
    mapped_filenames = set()
    rows_to_process = []

    for row in csv_rows:
        filename = row.get("filename")
        if not filename:
            stats["validation_failures"] += 1
            continue

        filename_lower = filename.lower()
        if filename_lower not in all_pdfs:
            stats["validation_failures"] += 1
            continue

        mapped_filenames.add(filename_lower)
        rows_to_process.append((all_pdfs[filename_lower], row))

    # Reject PDFs not present in CSV unless --include-unmapped is used
    if not args.include_unmapped:
        unmapped = set(all_pdfs.keys()) - mapped_filenames
        if unmapped:
            # Report unmapped as validation failures
            stats["validation_failures"] += len(unmapped)

    # Database setup
    sessions = get_session_factory()
    svc = UPSCBooksService()
    backend_root = Path(__file__).resolve().parents[2]

    def parse_bool(val: str) -> bool:
        if not val:
            return False
        v = val.strip().lower()
        if v in ("true", "1", "yes"):
            return True
        return False

    # Process each PDF
    for pdf_path, row in rows_to_process:
        try:
            # Required fields in metadata validation
            title = row.get("title")
            subject = row.get("subject")
            collection = row.get("collection")
            source_url = row.get("source_url")

            if not all([title, subject, collection, source_url]):
                stats["validation_failures"] += 1
                continue

            # Section / classification parsing
            section_val = row.get("section", "").strip().lower()
            resource_kind = "study_book"
            prelims = False
            mains = False

            if section_val:
                if section_val == "prelims":
                    prelims = True
                elif section_val == "mains":
                    mains = True
                elif section_val == "prelims_and_mains":
                    prelims = True
                    mains = True
                elif section_val == "qa_bank":
                    resource_kind = "qa_bank"
                else:
                    stats["validation_failures"] += 1
                    continue
            else:
                prelims = parse_bool(row.get("prelims", ""))
                mains = parse_bool(row.get("mains", ""))

            # Validate source URL as official PWOnlyIAS
            if not is_valid_pwonlyias_source_url(source_url):
                stats["validation_failures"] += 1
                continue

            # Validate PDF signature
            with open(pdf_path, "rb") as f:
                header = f.read(1024).lstrip()
                if not header.startswith(b"%PDF"):
                    stats["validation_failures"] += 1
                    continue

            # Validate PDF size (100MB limit)
            file_size = pdf_path.stat().st_size
            if file_size == 0 or file_size > 100 * 1024 * 1024:
                stats["validation_failures"] += 1
                continue

            # Calculate SHA-256 checksum
            checksum = compute_sha256(pdf_path)

            # Normalized Subject
            norm_subject = normalize_subject(subject)

            # Generate Safe ID based on composite hash to allow different books on same URL
            norm_title_clean = "".join(c for c in title.lower() if c.isalnum())
            hash_str = f"{source_url}_{norm_title_clean}_{resource_kind}"
            url_hash = hashlib.md5(hash_str.encode()).hexdigest()[:12]
            resource_id = f"book-{url_hash}"

            # Check duplicate using priority checks
            existing_id = None
            with sessions() as session:
                # Priority 1: exact PDF SHA-256 checksum + resource_kind (content type)
                q = select(UPSCBook).where(
                    UPSCBook.content_checksum == checksum,
                    UPSCBook.resource_kind == resource_kind
                )
                existing = session.scalars(q).first()

                # Priority 2: existing stable book ID
                if not existing:
                    existing = session.get(UPSCBook, resource_id)

                # Priority 3: normalized title + collection + resource_kind (content type)
                if not existing:
                    col_id = f"col-{hashlib.md5(collection.encode()).hexdigest()[:12]}"
                    q = select(UPSCBook).where(
                        UPSCBook.title.ilike(title),
                        UPSCBook.collection_id == col_id,
                        UPSCBook.resource_kind == resource_kind
                    )
                    existing = session.scalars(q).first()

                if existing:
                    existing_id = existing.id

            if existing_id and not args.force_reindex:
                if not args.dry_run:
                    with sessions() as session:
                        book_obj = session.get(UPSCBook, existing_id)
                        if book_obj:
                            book_obj.prelims_relevant = prelims
                            book_obj.mains_relevant = mains
                            book_obj.resource_kind = resource_kind
                            book_obj.normalized_subject = norm_subject
                            book_obj.title = title
                            col_id = f"col-{hashlib.md5(collection.encode()).hexdigest()[:12]}"
                            col_obj = session.get(BookCollection, col_id)
                            if not col_obj:
                                col_obj = BookCollection(
                                    id=col_id,
                                    provider="PWOnlyIAS",
                                    title=collection,
                                    slug=col_id,
                                    collection_type="books",
                                    official_source_url=source_url
                                )
                                session.add(col_obj)
                            book_obj.collection_id = col_id
                            session.commit()
                stats["duplicates"] += 1
                continue

            # Extract Blocks
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

            blocks, page_count, ext_status = extract_pdf_blocks(pdf_bytes)

            content_status = "ready"
            if ext_status == "failed":
                stats["extraction_failures"] += 1
                content_status = "unavailable"
                blocks = []
            elif ext_status == "image_only":
                content_status = "unavailable"
                blocks = []
                stats["image_only_pdfs"] += 1

            # Storage path
            target_id = existing_id if existing_id else resource_id
            storage_dir = backend_root / "data" / "pwonlyias" / "books" / target_id
            dest_pdf_path = storage_dir / "original.pdf"

            if args.dry_run:
                stats["successful_imports"] += 1
                continue

            # Save file copy
            storage_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf_path, dest_pdf_path)

            # Save to Database
            indexing_status = "indexed"
            with sessions() as session:
                # Collection upsert
                col_id = f"col-{hashlib.md5(collection.encode()).hexdigest()[:12]}"
                col_obj = session.get(BookCollection, col_id)
                if not col_obj:
                    col_obj = BookCollection(
                        id=col_id,
                        provider="PWOnlyIAS",
                        title=collection,
                        slug=col_id,
                        collection_type="books",
                        official_source_url=source_url
                    )
                    session.add(col_obj)

                # Book upsert
                book_obj = session.get(UPSCBook, target_id)
                if not book_obj:
                    book_obj = UPSCBook(id=target_id, slug=target_id)

                book_obj.collection_id = col_id
                book_obj.provider = "PWOnlyIAS"
                book_obj.title = title
                book_obj.normalized_subject = norm_subject
                book_obj.official_source_url = source_url
                book_obj.official_pdf_url = source_url
                book_obj.canonical_url = f"pwonlyias:book:{target_id}"
                book_obj.content_status = content_status
                book_obj.extraction_status = ext_status
                book_obj.content_checksum = checksum
                book_obj.page_count = page_count
                book_obj.content_blocks_json = blocks
                book_obj.prelims_relevant = prelims
                book_obj.mains_relevant = mains
                book_obj.resource_kind = resource_kind

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
                        stats["indexed"] += 1
                    except Exception as index_err:
                        err_msg = str(index_err).lower()
                        if ("ollama embeddings are unavailable" in err_msg
                                or "ollama embedding model" in err_msg
                                or "connection" in err_msg):
                            indexing_status = "indexing_skipped"
                            stats["indexing_skipped"] += 1
                        else:
                            indexing_status = "indexing_failed"
                            stats["indexing_failures"] += 1
                else:
                    # Extraction failed — indexing was never attempted
                    indexing_status = "not_ready"

                book_obj.indexing_status = indexing_status
                session.commit()

            stats["successful_imports"] += 1

        except Exception:
            stats["extraction_failures"] += 1
            continue

    print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    main()
