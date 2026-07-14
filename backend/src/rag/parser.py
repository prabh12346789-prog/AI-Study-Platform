import fitz
from pathlib import Path


class PDFParser:

    @staticmethod
    def extract_text(pdf_path: Path):

        document = fitz.open(pdf_path)

        pages = []
        full_text = ""

        for page in document:
            text = page.get_text()
            pages.append(text)
            full_text += text + "\n"

        document.close()

        return {
            "text": full_text,
            "pages": len(pages),
            "page_texts": pages,
        }
