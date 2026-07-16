class PromptBuilder:

    @staticmethod
    def build_prompt(question: str, search_result: dict):
        provider = search_result.get("provider", "local")
        context_text = search_result.get("context", "")

        if context_text:
            source_label = "Uploaded Documents" if provider == "local" else "Trusted Web Sources"
            return (
                f"Source: {source_label}\n\n"
                "Retrieved Context\n\n"
                f"{context_text}"
            )

        return ""

    @staticmethod
    def build_context(chunks: list[dict]):

        if not chunks:
            return ""

        grouped_chunks = {}
        document_order = []

        for chunk in chunks:
            document_name = chunk.get("document_name") or "Unknown Document"

            if document_name not in grouped_chunks:
                grouped_chunks[document_name] = []
                document_order.append(document_name)

            grouped_chunks[document_name].append(chunk.get("text", ""))

        blocks = []
        for document_name in document_order:
            document_chunks = grouped_chunks[document_name]
            blocks.append(f"===== {document_name} =====")
            blocks.extend(chunk_text for chunk_text in document_chunks if chunk_text)

        return "\n\n".join(blocks).strip()
