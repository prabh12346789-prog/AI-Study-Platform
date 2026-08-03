from __future__ import annotations

import argparse
import asyncio
import json
import sys

from src.current_affairs.ingestion_service import OfficialCurrentAffairsIngestionService


def main():
    parser = argparse.ArgumentParser(description="Official Current Affairs Ingestion CLI")
    parser.add_argument(
        "--source",
        choices=["pib", "rbi", "mea"],
        help="Specify source adapter (pib, rbi, or mea). Default: all sources.",
    )
    args = parser.parse_args()

    sources = [args.source] if args.source else None
    svc = OfficialCurrentAffairsIngestionService()

    print(f"Starting official Current Affairs collection for sources: {sources or ['pib', 'rbi', 'mea']}...")
    result = asyncio.run(svc.run_ingestion(sources=sources, trigger_type="cli"))

    summary = {
        "status": result.get("status"),
        "fetched": result.get("fetched", 0),
        "accepted": result.get("accepted", 0),
        "rejected": result.get("rejected", 0),
        "duplicates": result.get("duplicates", 0),
        "summarized": result.get("summarized", 0),
        "indexed": result.get("indexed", 0),
        "failed": result.get("failed", 0),
        "source_results": result.get("source_results", {}),
    }

    print("\n--- INGESTION SUMMARY ---")
    print(json.dumps(summary, indent=2))

    if result.get("errors"):
        print("\nErrors:", result.get("errors"))

    sys.exit(0 if result.get("status") in ("completed", "completed_with_errors") else 1)


if __name__ == "__main__":
    main()
