import re
from pathlib import Path


class Chunker:

	TARGET_WORDS = 800
	OVERLAP_WORDS = 100

	@classmethod
	def chunk_document(cls, document_dir: Path):

		text = cls.read_text(document_dir)
		cleaned_text = cls.clean_text(text)
		paragraphs = cls.split_paragraphs(cleaned_text)
		return cls.build_chunks(paragraphs)

	@staticmethod
	def read_text(document_dir: Path):

		extracted_text_path = document_dir / "extracted.txt"
		return extracted_text_path.read_text(encoding="utf-8")

	@staticmethod
	def clean_text(text: str):

		normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
		return normalized_text.strip()

	@staticmethod
	def split_paragraphs(text: str):

		paragraphs = re.split(r"\n\s*\n+", text)
		cleaned_paragraphs = []

		for paragraph in paragraphs:
			cleaned_paragraph = re.sub(r"\s+", " ", paragraph).strip()
			if cleaned_paragraph:
				cleaned_paragraphs.append(cleaned_paragraph)

		return cleaned_paragraphs

	@classmethod
	def build_chunks(cls, paragraphs):

		chunks = []
		current_parts = []
		current_word_count = 0

		for paragraph in paragraphs:
			paragraph_segments = cls._split_long_paragraph(paragraph)

			for segment in paragraph_segments:
				segment_word_count = len(segment.split())

				if current_parts and current_word_count + segment_word_count > cls.TARGET_WORDS:
					chunk_text = "\n\n".join(current_parts).strip()
					chunks.append(cls._build_chunk(len(chunks), chunk_text))

					overlap_text = cls.add_overlap(chunk_text)
					current_parts = [overlap_text] if overlap_text else []
					current_word_count = len(overlap_text.split()) if overlap_text else 0

				current_parts.append(segment)
				current_word_count += segment_word_count

		if current_parts:
			chunk_text = "\n\n".join(current_parts).strip()
			chunks.append(cls._build_chunk(len(chunks), chunk_text))

		return chunks

	@classmethod
	def add_overlap(cls, chunk_text: str):

		words = chunk_text.split()
		if not words:
			return ""

		overlap_words = words[-cls.OVERLAP_WORDS :]
		return " ".join(overlap_words).strip()

	@classmethod
	def _split_long_paragraph(cls, paragraph: str):

		words = paragraph.split()
		if len(words) <= cls.TARGET_WORDS:
			return [paragraph]

		segments = []
		sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", paragraph) if sentence.strip()]

		if not sentences:
			sentences = [paragraph.strip()]

		for sentence in sentences:
			sentence_words = sentence.split()

			if len(sentence_words) <= cls.TARGET_WORDS:
				segments.append(sentence)
				continue

			for start in range(0, len(sentence_words), cls.TARGET_WORDS):
				segments.append(" ".join(sentence_words[start : start + cls.TARGET_WORDS]))

		return segments

	@staticmethod
	def _build_chunk(chunk_id: int, text: str):

		return {
			"chunk_id": chunk_id,
			"text": text,
			"word_count": len(text.split()),
			"page_start": None,
			"page_end": None,
		}
