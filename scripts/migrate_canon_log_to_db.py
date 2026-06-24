#!/usr/bin/env python3
"""Migrate plot/canon-log.md → SQLite canon_facts table — Issue #280.

For each book found in the content root (projects/ and series/*/):
  1. Parse the "## Established Facts" section from canon-log.md
  2. INSERT rows into the per-series/book SQLite DB
  3. Leave canon-log.md untouched (read-only archive)

Usage:
  python scripts/migrate_canon_log_to_db.py           # dry-run (safe)
  python scripts/migrate_canon_log_to_db.py --execute # write to DB

The script is idempotent — re-running only inserts rows not already present
(UNIQUE constraint ON CONFLICT IGNORE).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from the project root without PYTHONPATH tricks
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.db.canon_facts import import_from_parsed_facts  # noqa: E402
from tools.db.connection import get_book_num, get_db_slug_for_book, open_canon_db  # noqa: E402
from tools.shared.config import load_config  # noqa: E402
from tools.shared.paths import find_projects  # noqa: E402
from tools.state.review_brief import _parse_canon_log_facts  # noqa: E402

DRY_RUN = "--execute" not in sys.argv


def log(msg: str) -> None:
    prefix = "[DRY-RUN] " if DRY_RUN else "[EXEC]    "
    print(f"{prefix}{msg}")


def migrate_book(book_root: Path) -> int:
    """Parse canon-log.md for book_root and import into DB. Returns row count."""
    canon_path = book_root / "plot" / "canon-log.md"
    if not canon_path.is_file():
        print(f"  SKIP: no canon-log.md in {book_root.name}")
        return 0

    text = canon_path.read_text(encoding="utf-8")
    facts = _parse_canon_log_facts(text)
    if not facts:
        print(f"  SKIP: no Established Facts found in {book_root.name}/plot/canon-log.md")
        return 0

    book_num = get_book_num(book_root)
    db_slug = get_db_slug_for_book(book_root)

    log(f"{book_root.name} → {db_slug}.db  ({len(facts)} facts, book_num={book_num})")

    if DRY_RUN:
        return len(facts)

    conn = open_canon_db(db_slug)
    try:
        inserted = import_from_parsed_facts(
            conn, book_num=book_num, chapter_num=0, parsed_facts=facts
        )
    finally:
        conn.close()

    log(f"  inserted {inserted} new rows (duplicates silently skipped)")
    return inserted


def main() -> None:
    if DRY_RUN:
        print("=" * 60)
        print("DRY-RUN MODE — no DB writes")
        print("Run with --execute to apply")
        print("=" * 60)
    else:
        print("=" * 60)
        print("EXECUTING MIGRATION")
        print("=" * 60)

    config = load_config()
    books = find_projects(config)
    print(f"\nFound {len(books)} book(s):\n")

    total = 0
    for book_root in books:
        total += migrate_book(book_root)

    print(f"\n{'=' * 60}")
    if DRY_RUN:
        print(f"Dry-run complete. Would process ~{total} facts.")
        print("Rerun with --execute to write to DB.")
    else:
        print(f"Migration complete. {total} rows inserted.")
        print("\ncanon-log.md files are preserved as read-only archives.")


if __name__ == "__main__":
    main()
