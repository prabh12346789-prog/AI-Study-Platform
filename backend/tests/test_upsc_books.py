import os
import sys
import pytest
import uuid
from fastapi.testclient import TestClient
from src.main import app
from src.pwonlyias.shared import is_valid_pwonlyias_source_url
from src.upsc_books.service import UPSCBooksService, detect_chapters_from_blocks
from src.upsc_books.models import UPSCBook, BookChapter

client = TestClient(app)


def test_isolated_test_book_and_synthetic_ids_excluded():
    svc = UPSCBooksService()
    with svc.sessions() as session:
        existing = session.get(UPSCBook, "test-isolated-001")
        if existing:
            session.delete(existing)
            session.commit()
        session.add(UPSCBook(
            id="test-isolated-001", provider="PWOnlyIAS", title="Isolated Test Book", slug="isolated-test-book",
            normalized_subject="Indian Polity and Governance", official_source_url="https://pwonlyias.com/test",
            canonical_url="https://pwonlyias.com/test-isolated-001"
        ))
        session.commit()

    res = client.get("/upsc-books")
    assert res.status_code == 200
    data = res.json()
    assert not any("Isolated Test Book" in b["title"] for b in data)
    assert not any(b["id"].startswith("test-") for b in data)


def test_import_from_official_source_page_validates_domain():
    svc = UPSCBooksService()
    with pytest.raises(ValueError, match="PWOnlyIAS"):
        svc.import_from_official_source_page("https://evilbooks.com/book-page")


def test_subject_filter_and_zero_result_behavior():
    svc = UPSCBooksService()
    book_id = f"real-book-{uuid.uuid4()}"
    from sqlalchemy import delete
    with svc.sessions() as session:
        # Delete any existing test Ethics or Polity books
        session.execute(delete(UPSCBook).where(
            (UPSCBook.normalized_subject == "Ethics") |
            (UPSCBook.id.like("real-book-%"))
        ))
        session.add(UPSCBook(
            id=book_id, provider="PWOnlyIAS", title="Real Polity Reference Book", slug=f"slug-{book_id}",
            normalized_subject="Indian Polity and Governance", official_source_url="https://pwonlyias.com/books/polity-real",
            canonical_url=f"https://pwonlyias.com/books/polity-real-{book_id}", content_status="ready",
            extraction_status="ready", content_blocks_json=[{"type": "paragraph", "text": "Polity content"}]
        ))
        session.commit()

    # Query matching subject
    res_match = client.get("/upsc-books?subject=Indian%20Polity%20and%20Governance")
    assert res_match.status_code == 200
    books_polity = res_match.json()
    assert any(b["id"] == book_id for b in books_polity)

    # Query zero-result subject
    res_empty = client.get("/upsc-books?subject=Ethics")
    assert res_empty.status_code == 200
    assert res_empty.json() == []


def test_chapter_detection_only_on_explicit_headings():
    uncertain_blocks = [
        {"type": "heading", "level": 2, "text": "Overview"},
        {"type": "paragraph", "text": "Text"}
    ]
    assert detect_chapters_from_blocks(uncertain_blocks) == []

    explicit_blocks = [
        {"type": "heading", "level": 2, "text": "Chapter 1: Constitutional Pillars", "page_start": 1, "page_end": 15}
    ]
    chs = detect_chapters_from_blocks(explicit_blocks)
    assert len(chs) == 1
    assert chs[0]["title"] == "Chapter 1: Constitutional Pillars"


def test_no_local_paths_exposed_in_api():
    res = client.get("/upsc-books")
    assert res.status_code == 200
    txt = str(res.json())
    assert "C:\\" not in txt and "/tmp/" not in txt


def test_book_manual_import_and_streaming(tmp_path):
    import subprocess
    import json
    from pathlib import Path
    from src.memory.storage import get_session_factory
    from src.upsc_books.models import UPSCBook
    from sqlalchemy import delete

    # Cleanup any existing test books
    sessions = get_session_factory()
    with sessions() as session:
        session.execute(delete(UPSCBook).where(
            (UPSCBook.canonical_url.in_([
                "https://pwonlyias.com/dry-run-book-url",
                "https://pwonlyias.com/real-book-url"
            ])) |
            (UPSCBook.official_source_url.in_([
                "https://pwonlyias.com/dry-run-book-url",
                "https://pwonlyias.com/real-book-url"
            ]))
        ))
        session.commit()
    
    # 1. Create a dummy PDF with correct signature
    pdf_file = tmp_path / "dummy_book.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\n%EOF\nHello dummy book content with enough size to be processed.")

    # 2. Test dry-run book import
    cmd_dry = [
        sys.executable, "-m", "src.scripts.import_pwonlyias_pdf",
        "--type", "book",
        "--title", "Polity Dry Run Book",
        "--subject", "Indian Polity and Governance",
        "--collection", "UDAAN",
        "--source-url", "https://pwonlyias.com/dry-run-book-url",
        "--file", str(pdf_file),
        "--dry-run"
    ]
    res_dry = subprocess.run(cmd_dry, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]))
    assert res_dry.returncode == 0
    data_dry = json.loads(res_dry.stdout)
    assert data_dry["status"] == "dry_run"
    assert data_dry["title"] == "Polity Dry Run Book"
    assert data_dry["subject"] == "Indian Polity and Governance"

    # 3. Test real import book
    cmd_real = [
        sys.executable, "-m", "src.scripts.import_pwonlyias_pdf",
        "--type", "book",
        "--title", "Polity Real Book",
        "--subject", "Indian Polity and Governance",
        "--collection", "UDAAN",
        "--source-url", "https://pwonlyias.com/real-book-url",
        "--file", str(pdf_file)
    ]
    res_real = subprocess.run(cmd_real, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]))
    assert res_real.returncode == 0
    data_real = json.loads(res_real.stdout)
    assert data_real["status"] == "success"
    book_id = data_real["id"]

    # 4. Test duplicate import returns duplicate status and ID
    res_dup = subprocess.run(cmd_real, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]))
    assert res_dup.returncode == 0
    data_dup = json.loads(res_dup.stdout)
    assert data_dup["status"] == "duplicate"
    assert data_dup["id"] == book_id

    # 5. Test local PDF streaming works
    res_stream = client.get(f"/upsc-books/{book_id}/pdf")
    assert res_stream.status_code == 200
    assert res_stream.headers["content-type"] == "application/pdf"
    assert "inline" in res_stream.headers["content-disposition"]

    # 6. Verify learner API exposes no local paths
    res_info = client.get(f"/upsc-books/{book_id}")
    assert res_info.status_code == 200
    info_body = str(res_info.json())
    assert "C:\\" not in info_body and "data/pwonlyias" not in info_body

    # 7. Check notes and books are separated
    res_note = client.get(f"/upsc-notes/{book_id}")
    assert res_note.status_code == 404


def test_book_batch_import(tmp_path):
    import subprocess
    import json
    import csv
    from pathlib import Path
    from src.memory.storage import get_session_factory
    from src.upsc_books.models import UPSCBook
    from sqlalchemy import delete

    # Cleanup any existing batch test books
    sessions = get_session_factory()
    with sessions() as session:
        session.execute(delete(UPSCBook).where(
            (UPSCBook.canonical_url.in_([
                "https://pwonlyias.com/batch-book1",
                "https://pwonlyias.com/batch-book2"
            ])) |
            (UPSCBook.official_source_url.in_([
                "https://pwonlyias.com/batch-book1",
                "https://pwonlyias.com/batch-book2"
            ]))
        ))
        session.commit()

    # 1. Prepare batch files in folder
    folder = tmp_path / "batch_folder"
    folder.mkdir()

    pdf1 = folder / "book1.pdf"
    pdf1.write_bytes(b"%PDF-1.4\n%EOF\nHello Book 1 text content")

    pdf2 = folder / "book2.pdf"
    pdf2.write_bytes(b"%PDF-1.4\n%EOF\nHello Book 2 text content")

    # missing.pdf is in CSV but not in folder
    # unmapped.pdf is in folder but not in CSV
    pdf_unmapped = folder / "unmapped.pdf"
    pdf_unmapped.write_bytes(b"%PDF-1.4\n%EOF\nUnmapped book")

    # 2. Write CSV metadata
    csv_file = tmp_path / "metadata.csv"
    with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "title", "subject", "collection", "source_url", "prelims", "mains"])
        # Successful row 1
        writer.writerow(["book1.pdf", "Batch Book 1", "Indian Polity and Governance", "Prahaar", "https://pwonlyias.com/batch-book1", "true", "true"])
        # Successful row 2
        writer.writerow(["book2.pdf", "Batch Book 2", "Indian Polity and Governance", "Prahaar", "https://pwonlyias.com/batch-book2", "true", "false"])
        # Non-PW URL (rejected)
        writer.writerow(["book2.pdf", "Evil Batch Book", "Indian Polity and Governance", "Prahaar", "https://evilpwonlyias.com/evil", "true", "false"])
        # Missing PDF in folder
        writer.writerow(["missing.pdf", "Missing Book", "Geography", "Prahaar", "https://pwonlyias.com/missing-pdf", "false", "true"])
        # Missing required metadata (missing title/subject/collection/source_url)
        writer.writerow(["book1.pdf", "", "", "", "", "", ""])

    # 3. Test dry-run makes no changes
    cmd_dry = [
        sys.executable, "-m", "src.scripts.batch_import_pwonlyias_pdfs",
        "--folder", str(folder),
        "--metadata", str(csv_file),
        "--dry-run"
    ]
    env = os.environ.copy()
    res_dry = subprocess.run(cmd_dry, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]), env=env)
    assert res_dry.returncode == 0
    data_dry = json.loads(res_dry.stdout)
    # 3 PDFs in folder (book1, book2, unmapped)
    assert data_dry["total_pdfs"] == 3
    # book1 and book2 should succeed
    assert data_dry["successful_imports"] == 2
    # evil url, missing pdf, missing metadata, unmapped pdf
    assert data_dry["validation_failures"] >= 3

    # 4. Actual batch import run
    cmd_real = [
        sys.executable, "-m", "src.scripts.batch_import_pwonlyias_pdfs",
        "--folder", str(folder),
        "--metadata", str(csv_file)
    ]
    res_real = subprocess.run(cmd_real, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]), env=env)
    assert res_real.returncode == 0
    data_real = json.loads(res_real.stdout)
    assert data_real["successful_imports"] == 2

    # Verify books are queryable via API
    res_books = client.get("/upsc-books").json()
    assert any(b["title"] == "Batch Book 1" for b in res_books)
    assert any(b["title"] == "Batch Book 2" for b in res_books)

    # 5. Rerun is idempotent (marks successful imports as duplicate instead of recreating)
    res_rerun = subprocess.run(cmd_real, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]), env=env)
    assert res_rerun.returncode == 0
    data_rerun = json.loads(res_rerun.stdout)
    assert data_rerun["successful_imports"] == 0
    assert data_rerun["duplicates"] == 2


def test_book_three_sections_classification_and_cli(tmp_path):
    import subprocess
    import json
    import csv
    from pathlib import Path
    from src.memory.storage import get_session_factory
    from src.upsc_books.models import UPSCBook
    from sqlalchemy import delete

    sessions = get_session_factory()
    with sessions() as session:
        session.execute(delete(UPSCBook).where(
            (UPSCBook.canonical_url.in_([
                "https://pwonlyias.com/prelims-test-url",
                "https://pwonlyias.com/mains-test-url",
                "https://pwonlyias.com/both-test-url",
                "https://pwonlyias.com/qa-test-url"
            ])) |
            (UPSCBook.official_source_url.in_([
                "https://pwonlyias.com/prelims-test-url",
                "https://pwonlyias.com/mains-test-url",
                "https://pwonlyias.com/both-test-url",
                "https://pwonlyias.com/qa-test-url"
            ]))
        ))
        session.commit()

    pdf1 = tmp_path / "test_import1.pdf"
    pdf1.write_bytes(b"%PDF-1.4\n%EOF\nDummy book text content 1")
    pdf2 = tmp_path / "test_import2.pdf"
    pdf2.write_bytes(b"%PDF-1.4\n%EOF\nDummy book text content 2")
    pdf3 = tmp_path / "test_import3.pdf"
    pdf3.write_bytes(b"%PDF-1.4\n%EOF\nDummy book text content 3")
    pdf4 = tmp_path / "test_import4.pdf"
    pdf4.write_bytes(b"%PDF-1.4\n%EOF\nDummy book text content 4")

    # 1. Test single import --prelims
    cmd1 = [
        sys.executable, "-m", "src.scripts.import_pwonlyias_pdf",
        "--type", "book", "--title", "Prelims Only Book",
        "--subject", "Indian Polity and Governance", "--collection", "UDAAN",
        "--source-url", "https://pwonlyias.com/prelims-test-url",
        "--file", str(pdf1), "--prelims"
    ]
    env = os.environ.copy()
    res1 = subprocess.run(cmd1, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]), env=env)
    assert res1.returncode == 0
    assert json.loads(res1.stdout)["status"] == "success"

    # 2. Test single import --mains
    cmd2 = [
        sys.executable, "-m", "src.scripts.import_pwonlyias_pdf",
        "--type", "book", "--title", "Mains Only Book",
        "--subject", "Indian Polity and Governance", "--collection", "UDAAN",
        "--source-url", "https://pwonlyias.com/mains-test-url",
        "--file", str(pdf2), "--mains"
    ]
    res2 = subprocess.run(cmd2, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]), env=env)
    assert res2.returncode == 0

    # 3. Test single import both
    cmd3 = [
        sys.executable, "-m", "src.scripts.import_pwonlyias_pdf",
        "--type", "book", "--title", "Both Relevant Book",
        "--subject", "Indian Polity and Governance", "--collection", "UDAAN",
        "--source-url", "https://pwonlyias.com/both-test-url",
        "--file", str(pdf3), "--prelims", "--mains"
    ]
    res3 = subprocess.run(cmd3, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]), env=env)
    assert res3.returncode == 0

    # 4. Test single import --qa-bank
    cmd4 = [
        sys.executable, "-m", "src.scripts.import_pwonlyias_pdf",
        "--type", "book", "--title", "QA Practice Bank",
        "--subject", "Indian Polity and Governance", "--collection", "UDAAN",
        "--source-url", "https://pwonlyias.com/qa-test-url",
        "--file", str(pdf4), "--qa-bank"
    ]
    res4 = subprocess.run(cmd4, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]), env=env)
    assert res4.returncode == 0

    # 5. Test ambiguous combination rejected
    cmd_evil = [
        sys.executable, "-m", "src.scripts.import_pwonlyias_pdf",
        "--type", "book", "--title", "Evil Book",
        "--subject", "Geography", "--collection", "UDAAN",
        "--source-url", "https://pwonlyias.com/evil-test-url",
        "--file", str(pdf1), "--prelims", "--qa-bank"
    ]
    res_evil = subprocess.run(cmd_evil, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]), env=env)
    assert res_evil.returncode != 0
    assert "Ambiguous classification" in res_evil.stdout

    # 6. Verify section filtering APIs
    # Prelims
    res_p = client.get("/upsc-books?section=prelims").json()
    assert any(b["title"] == "Prelims Only Book" for b in res_p)
    assert any(b["title"] == "Both Relevant Book" for b in res_p)
    assert not any(b["title"] == "Mains Only Book" for b in res_p)
    assert not any(b["title"] == "QA Practice Bank" for b in res_p)

    # Mains
    res_m = client.get("/upsc-books?section=mains").json()
    assert any(b["title"] == "Mains Only Book" for b in res_m)
    assert any(b["title"] == "Both Relevant Book" for b in res_m)
    assert not any(b["title"] == "Prelims Only Book" for b in res_m)
    assert not any(b["title"] == "QA Practice Bank" for b in res_m)

    # QA Bank
    res_q = client.get("/upsc-books?section=qa_bank").json()
    assert any(b["title"] == "QA Practice Bank" for b in res_q)
    assert not any(b["title"] == "Mains Only Book" for b in res_q)
    assert not any(b["title"] == "Prelims Only Book" for b in res_q)
    assert not any(b["title"] == "Both Relevant Book" for b in res_q)

    # Subject filter combination
    res_subj = client.get("/upsc-books?section=mains&subject=Indian%20Polity%20and%20Governance").json()
    assert any(b["title"] == "Mains Only Book" for b in res_subj)

    # Subject list section aware counts
    subjects_p = client.get("/upsc-books/subjects?section=prelims").json()
    polity_count_p = next(s["book_count"] for s in subjects_p if s["subject"] == "Indian Polity and Governance")
    assert polity_count_p >= 2


def test_detailed_duplicate_matching_and_classification(tmp_path):
    import subprocess
    import json
    import csv
    import hashlib
    from pathlib import Path
    from src.memory.storage import get_session_factory
    from src.upsc_books.models import UPSCBook
    from sqlalchemy import select

    # Cleanup any existing Prahaar books
    from sqlalchemy import delete
    sessions = get_session_factory()
    with sessions() as session:
        session.execute(delete(UPSCBook).where(
            UPSCBook.official_source_url == "https://pwonlyias.com/prahaar-for-mains-current-affairs/"
        ))
        session.commit()

    # Setup isolated folder and CSV
    folder = tmp_path / "batch_prahaar"
    folder.mkdir()
    csv_file = tmp_path / "books.csv"

    # Create 15 distinct valid text PDFs sharing the same source URL
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    def _write_pdf_file(path: Path, text: str):
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
        })
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
        with path.open("wb") as output:
            writer.write(output)

    filenames = []
    for i in range(1, 16):
        fname = f"prahaar_{i}.pdf"
        pdf_path = folder / fname
        _write_pdf_file(pdf_path, f"Distinct book content number {i}")
        filenames.append(fname)

    # Write CSV with various classifications and string "false"/"true"
    with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "title", "subject", "collection", "source_url", "prelims", "mains"])
        for idx, fname in enumerate(filenames):
            # Share the same source URL
            url = "https://pwonlyias.com/prahaar-for-mains-current-affairs/"
            subj = "Ethics" if idx % 2 == 0 else "History"
            # Some marked mains=true and prelims=false, some mains=true and prelims=true
            p_val = "false" if idx < 10 else "true"
            m_val = "true"
            writer.writerow([fname, f"Prahaar Book {idx+1}", subj, "Prahaar 2026", url, p_val, m_val])

    # Run batch importer CLI on the 15 files
    cmd = [
        sys.executable, "-m", "src.scripts.batch_import_pwonlyias_pdfs",
        "--folder", str(folder),
        "--metadata", str(csv_file)
    ]
    env = os.environ.copy()
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]), env=env)
    assert res.returncode == 0
    data = json.loads(res.stdout)

    # 15 distinct checksums must create 15 books
    assert data["successful_imports"] == 15
    assert data["duplicates"] == 0
    # Each book must have been indexed OR skipped (if Ollama unavailable), never failed
    assert data["indexing_failures"] == 0
    assert data["extraction_failures"] == 0
    # indexed + indexing_skipped must equal successful_imports
    assert data["indexed"] + data["indexing_skipped"] == 15

    # Rerun same checksum: must be duplicates
    res_rerun = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]), env=env)
    assert res_rerun.returncode == 0
    data_rerun = json.loads(res_rerun.stdout)
    assert data_rerun["successful_imports"] == 0
    assert data_rerun["duplicates"] == 15

    # Check database directly
    sessions = get_session_factory()
    with sessions() as session:
        # Verify 15 unique books imported
        books_db = list(session.scalars(select(UPSCBook).where(UPSCBook.collection_id.like("col-%"))))
        # col-id for collection 'Prahaar 2026'
        col_id = f"col-{hashlib.md5('Prahaar 2026'.encode()).hexdigest()[:12]}"
        prahaar_books = [b for b in books_db if b.collection_id == col_id]
        assert len(prahaar_books) == 15

        # Check boolean values correctly parsed:
        # First 10 had prelims="false" -> should be prelims_relevant = False
        mains_only = [b for b in prahaar_books if b.mains_relevant and not b.prelims_relevant]
        assert len(mains_only) == 10

        both_relevant = [b for b in prahaar_books if b.mains_relevant and b.prelims_relevant]
        assert len(both_relevant) == 5

        # Verify that all books have a terminal indexing status (no "not_ready" since PDFs are valid)
        for b in prahaar_books:
            assert b.indexing_status in ("indexed", "indexing_skipped")

        # Verify no local path is exposed in learner-visible fields
        for b in prahaar_books:
            assert "C:" not in (b.official_pdf_url or "")
            assert "Users" not in (b.official_pdf_url or "")
            assert "AppData" not in (b.official_pdf_url or "")
            # canonical_url is an internal identity URI, not a learner-facing field
            assert b.canonical_url.startswith("pwonlyias:book:")

    # Check force reindex: update classification and reindex
    # We update the CSV to change prelims value for the first book
    with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "title", "subject", "collection", "source_url", "prelims", "mains"])
        writer.writerow([filenames[0], "Prahaar Book 1 Updated", "History", "Prahaar 2026", "https://pwonlyias.com/prahaar-for-mains-current-affairs/", "true", "true"])

    cmd_force = [
        sys.executable, "-m", "src.scripts.batch_import_pwonlyias_pdfs",
        "--folder", str(folder),
        "--metadata", str(csv_file),
        "--force-reindex"
    ]
    res_force = subprocess.run(cmd_force, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]), env=env)
    assert res_force.returncode == 0
    data_force = json.loads(res_force.stdout)
    assert data_force["successful_imports"] == 1
    assert data_force["duplicates"] == 0

    with sessions() as session:
        # Verify book title and classification are updated
        # Since the checksum of prahaar_1.pdf was unchanged, the priority 1 duplicate checker matched the existing book
        prahaar_books_now = list(session.scalars(select(UPSCBook).where(UPSCBook.collection_id == col_id)))
        assert len(prahaar_books_now) == 15
        
        # Check that one of them has title "Prahaar Book 1 Updated"
        updated_book = next(b for b in prahaar_books_now if b.title == "Prahaar Book 1 Updated")
        assert updated_book.prelims_relevant is True
        assert updated_book.mains_relevant is True
