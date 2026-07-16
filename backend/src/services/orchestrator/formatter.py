def format_response(response: str, provider: str, sources: list[dict] | None = None):
    return {
        "status": "success",
        "answer": response,
        "provider": provider,
        "sources": sources or []
    }