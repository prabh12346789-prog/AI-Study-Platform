from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

from src.current_affairs.service import CurrentAffairsService


def parse_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD format") from error
    if value != parsed.isoformat(): raise argparse.ArgumentTypeError("date must use YYYY-MM-DD format")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect trusted UPSC current affairs into the local backend.")
    parser.add_argument("--date", required=True, type=parse_date)
    parser.add_argument("--generate-brief", action="store_true")
    parser.add_argument("--language", choices=("english", "hindi", "punjabi"), default="english")
    parser.add_argument("--max-results", type=int, default=10, choices=range(1, 21), metavar="1-20")
    return parser


async def run_collection(args, service=None):
    service = service or CurrentAffairsService()
    return await service.collect_for_date(args.date, max_results=args.max_results,
        generate_brief=args.generate_brief, language=args.language)


def print_summary(result):
    print(f"Date: {result['date'].isoformat()}")
    print(f"Collected: {result['collected']}")
    print(f"Accepted: {result['accepted']}")
    print(f"Rejected: {result['rejected']}")
    print(f"Duplicates: {result['duplicates']}")
    print(f"Daily brief: {result['daily_brief']}")
    if result.get("collection_errors"): print("Collection errors: " + "; ".join(result["collection_errors"]))
    if result.get("brief_error"): print("Brief error: " + result["brief_error"])


def main():
    result = asyncio.run(run_collection(build_parser().parse_args()))
    print_summary(result)


if __name__ == "__main__": main()
