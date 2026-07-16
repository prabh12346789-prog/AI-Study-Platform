import re
from pathlib import Path

from pypdf import PdfReader


_INVALID_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class PDFParser:

    @staticmethod
    def extract_text(pdf_path: Path):
        with pdf_path.open("rb") as pdf_file:
            reader = PdfReader(pdf_file)
            if reader.is_encrypted and reader.decrypt("") == 0:
                raise ValueError("Encrypted PDF requires a usable password.")

            page_texts = []
            for page in reader.pages:
                try:
                    text = page.extract_text() or ""
                except Exception:
                    # A damaged page must not discard text recovered from other pages.
                    text = ""
                page_texts.append(_INVALID_CONTROL_CHARACTERS.sub("", text))

            if not page_texts or not any(text.strip() for text in page_texts):
                raise ValueError("PDF contains no extractable text. Image-only scanned PDFs require OCR.")

            metadata = {
                str(key).lstrip("/"): str(value)
                for key, value in (reader.metadata or {}).items()
                if value is not None
            }

        # Retain the existing extracted-text layout: every page ends in a newline.
        full_text = "".join(f"{text}\n" for text in page_texts)

        return {
            "text": full_text,
            "pages": len(page_texts),
            "page_texts": page_texts,
            "page_numbers": list(range(1, len(page_texts) + 1)),
            "metadata": metadata,
        }
