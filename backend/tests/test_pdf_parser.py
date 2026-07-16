from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.errors import PdfReadError
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from src.rag.chunker import Chunker
from src.rag.parser import PDFParser


def _write_text_pdf(path: Path, page_texts: list[str], *, metadata: dict | None = None):
    writer = PdfWriter()
    for text in page_texts:
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
    if metadata:
        writer.add_metadata(metadata)
    with path.open("wb") as output:
        writer.write(output)


def test_extracts_single_page_text_and_metadata(tmp_path):
    pdf_path = tmp_path / "single.pdf"
    _write_text_pdf(pdf_path, ["Fundamental Rights"], metadata={"/Title": "UPSC Notes"})
    parsed = PDFParser.extract_text(pdf_path)
    assert parsed["text"] == "Fundamental Rights\n"
    assert parsed["pages"] == 1
    assert parsed["page_texts"] == ["Fundamental Rights"]
    assert parsed["page_numbers"] == [1]
    assert parsed["metadata"]["Title"] == "UPSC Notes"


def test_multi_page_output_preserves_page_order_and_chunking_contract(tmp_path):
    pdf_path = tmp_path / "multi.pdf"
    _write_text_pdf(pdf_path, ["First page", "Second page"])
    parsed = PDFParser.extract_text(pdf_path)
    document_dir = tmp_path / "document"
    document_dir.mkdir()
    (document_dir / "extracted.txt").write_text(parsed["text"], encoding="utf-8")
    chunks = Chunker.chunk_document(document_dir)
    assert parsed["page_texts"] == ["First page", "Second page"]
    assert parsed["page_numbers"] == [1, 2]
    assert parsed["text"] == "First page\nSecond page\n"
    assert chunks[0]["text"] == "First page Second page"
    assert set(chunks[0]) == {"chunk_id", "text", "word_count", "page_start", "page_end"}


class _Page:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error

    def extract_text(self):
        if self.error:
            raise self.error
        return self.result


class _Reader:
    is_encrypted = False
    metadata = {"/Title": "Unicode Notes"}

    def __init__(self, _file, pages):
        self.pages = pages


def test_none_page_and_partially_readable_pdf_preserve_page_numbers(tmp_path, monkeypatch):
    pdf_path = tmp_path / "partial.pdf"
    pdf_path.write_bytes(b"placeholder")
    pages = [_Page(None), _Page(error=RuntimeError("damaged page")), _Page("Polity")]
    monkeypatch.setattr("src.rag.parser.PdfReader", lambda file: _Reader(file, pages))
    parsed = PDFParser.extract_text(pdf_path)
    assert parsed["page_texts"] == ["", "", "Polity"]
    assert parsed["page_numbers"] == [1, 2, 3]
    assert parsed["text"] == "\n\nPolity\n"


def test_unicode_and_invalid_control_characters_are_handled(tmp_path, monkeypatch):
    pdf_path = tmp_path / "unicode.pdf"
    pdf_path.write_bytes(b"placeholder")
    pages = [_Page("संविधान\x00 और ਪੰਜਾਬੀ\x07\nArticle 21")]
    monkeypatch.setattr("src.rag.parser.PdfReader", lambda file: _Reader(file, pages))
    parsed = PDFParser.extract_text(pdf_path)
    assert parsed["page_texts"] == ["संविधान और ਪੰਜਾਬੀ\nArticle 21"]


@pytest.mark.parametrize("page_texts", [[], [""], [None]])
def test_empty_or_no_text_pdf_has_readable_error(tmp_path, monkeypatch, page_texts):
    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(b"placeholder")
    pages = [_Page(text) for text in page_texts]
    monkeypatch.setattr("src.rag.parser.PdfReader", lambda file: _Reader(file, pages))
    with pytest.raises(ValueError, match="no extractable text"):
        PDFParser.extract_text(pdf_path)


def test_corrupted_pdf_preserves_pypdf_error(tmp_path):
    pdf_path = tmp_path / "corrupted.pdf"
    pdf_path.write_bytes(b"not a PDF")
    with pytest.raises(PdfReadError):
        PDFParser.extract_text(pdf_path)


def test_encrypted_pdf_without_password_has_readable_error(tmp_path):
    pdf_path = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("secret")
    with pdf_path.open("wb") as output:
        writer.write(output)
    with pytest.raises(ValueError, match="usable password"):
        PDFParser.extract_text(pdf_path)
