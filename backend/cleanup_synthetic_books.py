"""
cleanup_synthetic_books.py  — one-time script to remove confirmed test
fixtures from the PRODUCTION database.

Run from: backend/
  python cleanup_synthetic_books.py

Removes ONLY records whose titles or IDs match confirmed test fixtures.
Does NOT remove genuine imported PWOnlyIAS books.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text
from src.memory.storage import get_engine

# ── Confirmed synthetic titles (exact matches) ─────────────────────────────
SYNTHETIC_EXACT_TITLES = {
    "Prahaar Book 1 Updated",
    "Prahaar Book 1", "Prahaar Book 2", "Prahaar Book 3",
    "Prahaar Book 4", "Prahaar Book 5", "Prahaar Book 6",
    "Prahaar Book 7", "Prahaar Book 8", "Prahaar Book 9",
    "Prahaar Book 10", "Prahaar Book 11", "Prahaar Book 12",
    "Prahaar Book 13", "Prahaar Book 14", "Prahaar Book 15",
    "Both Relevant Book",
    "Prelims Only Book",
    "Mains Only Book",
    "Isolated Test Book",
    "QA Practice Bank",
    "Batch Book 1",
    "Batch Book 2",
    "Evil Batch Book",
    "Polity Dry Run Book",
    "Polity Real Book",
    "Real Polity Reference Book",
}

# ── Confirmed synthetic ID prefixes ───────────────────────────────────────
SYNTHETIC_ID_PREFIXES = ("test-", "demo-", "sample-", "isolated-", "prog-")

# ── Genuine books to PROTECT (never delete) ───────────────────────────────
PROTECTED_TITLE_KEYWORDS = (
    "Art and Culture Prahaar",
    "Environment and Ecology Prahaar",
    "Ethics, Integrity and Aptitude Prahaar",
    "Geography and Disaster Management Prahaar",
    "Governance Prahaar",
    "Indian Economy Prahaar",
    "Indian Polity and Constitution Prahaar",
    "Indian Society Prahaar",
    "Internal Security Prahaar",
    "International Relations Prahaar",
    "Modern India Prahaar",
    "Post Independence India Prahaar",
    "Science and Technology Prahaar",
    "Social Justice Prahaar",
    "World History Prahaar",
)


def main() -> None:
    engine = get_engine()
    removed: list[tuple[str, str]] = []

    with engine.connect() as conn:
        all_books = conn.execute(text("SELECT id, title FROM upsc_books")).fetchall()

        ids_to_remove: list[str] = []
        for bid, title in all_books:
            # Never delete genuine books
            if any(kw in (title or "") for kw in PROTECTED_TITLE_KEYWORDS):
                continue

            # Remove confirmed synthetic titles
            if title in SYNTHETIC_EXACT_TITLES:
                ids_to_remove.append(bid)
                removed.append((bid, title))
                continue

            # Remove confirmed synthetic ID prefixes
            if any(str(bid).startswith(pfx) for pfx in SYNTHETIC_ID_PREFIXES):
                ids_to_remove.append(bid)
                removed.append((bid, title))
                continue

        if not ids_to_remove:
            print("No synthetic books found — production DB is already clean.")
            return

        print(f"\nRemoving {len(ids_to_remove)} synthetic book(s):\n")
        for bid, title in removed:
            print(f"  DELETE  id={bid!r:45s}  title={title!r}")

        for bid in ids_to_remove:
            conn.execute(text("DELETE FROM book_chapters WHERE book_id = :b"), {"b": bid})
            conn.execute(text("DELETE FROM saved_books WHERE book_id = :b"), {"b": bid})
            conn.execute(text("DELETE FROM book_reading_progress WHERE book_id = :b"), {"b": bid})
            conn.execute(text("DELETE FROM upsc_books WHERE id = :b"), {"b": bid})

        # Also remove vector chunks for synthetic books from Chroma
        try:
            from src.rag.vector_store import VectorStore
            vs = VectorStore()
            for bid, _ in removed:
                try:
                    vs.collection.delete(where={"book_id": bid})
                except Exception:
                    try:
                        vs.collection.delete(where={"document_id": bid})
                    except Exception:
                        pass
            print(f"\nChroma vector chunks removed for {len(removed)} books.")
        except Exception as e:
            print(f"\n[warn] Could not remove Chroma chunks: {e}")

        conn.commit()

    # Final count
    with engine.connect() as conn:
        remaining = conn.execute(text("SELECT COUNT(*) FROM upsc_books")).scalar()
        print(f"\nProduction DB after cleanup: {remaining} book(s) remaining.")

        titles_remaining = conn.execute(
            text("SELECT title FROM upsc_books ORDER BY title")
        ).fetchall()
        print("Remaining books:")
        for (t,) in titles_remaining:
            print(f"  {t!r}")


if __name__ == "__main__":
    main()
