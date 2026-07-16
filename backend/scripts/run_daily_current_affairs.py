from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)
load_dotenv(BACKEND / ".env")

from src.core.config import settings
from src.current_affairs.service import CurrentAffairsService

LOCK = BACKEND / "data" / "current_affairs_daily.lock"
LOG_DIR = BACKEND / "logs" / "current_affairs"


def ollama_ready() -> bool:
    try:
        response = requests.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=3)
        response.raise_for_status()
        models = {item.get("name", "").split(":", 1)[0] for item in response.json().get("models", [])}
        return settings.OLLAMA_EMBEDDING_MODEL.split(":", 1)[0] in models
    except (requests.RequestException, ValueError):
        return False


async def run():
    LOG_DIR.mkdir(parents=True, exist_ok=True); LOCK.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return {"status": "skipped", "reason": "overlapping run is already active"}
    try:
        os.write(descriptor, str(os.getpid()).encode()); os.close(descriptor)
        if not ollama_ready():
            return {"status": "failed", "reason": "Ollama or nomic-embed-text is unavailable"}
        service = CurrentAffairsService()
        result = await service.collect_for_date(date.today(), max_results=int(os.getenv("CA_DAILY_MAX_RESULTS", "10")),
            generate_brief=True, language=os.getenv("CA_DAILY_LANGUAGE", "english"))
        result["reindex"] = service.reindex_active(); result["status"] = "complete"
        return result
    finally:
        LOCK.unlink(missing_ok=True)


def main():
    result = asyncio.run(run())
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"collection-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(result, default=str, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, default=str))


if __name__ == "__main__": main()
