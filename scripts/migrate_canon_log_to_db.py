#!/usr/bin/env python3
"""Migrate plot/canon-log.md (and people-log.md) → SQLite canon_facts table.

Fixes Issue #297: replaces the broken parser from #280 that only handled the
deprecated '## Established Facts' table format.  The real log format uses
'## Chapter NN' section headers with '### Subject: topic' subsections and
'**CHANGED**' markers — parsed via tools.state.loaders.canon_log_extractor.

Handles both fiction books (canon-log.md) and memoir books (people-log.md)
by reading book_category from each book's README.md frontmatter.

Usage:
  python scripts/migrate_canon_log_to_db.py           # dry-run (safe)
  python scripts/migrate_canon_log_to_db.py --execute # write to DB

The script is idempotent — re-running inserts only rows not already present
(UNIQUE constraint ON CONFLICT IGNORE).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.db.canon_facts import insert_fact  # noqa: E402
from tools.db.connection import get_book_num, get_db_slug_for_book, open_canon_db  # noqa: E402
from tools.shared.config import load_config  # noqa: E402
from tools.shared.paths import find_projects  # noqa: E402
from tools.state.loaders.canon_log_extractor import extract_all_facts  # noqa: E402

DRY_RUN = "--execute" not in sys.argv


def _detect_book_category(book_root: Path) -> str:
    """Read book_category from README frontmatter, default to 'fiction'."""
    readme = book_root / "README.md"
    if not readme.is_file():
        return "fiction"
    for line in readme.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("book_category:"):
            value = line.split(":", 1)[1].strip().strip('"').strip("'")
            if value == "memoir":
                return "memoir"
    return "fiction"


def _log(msg: str) -> None:
    prefix = "[DRY-RUN] " if DRY_RUN else "[EXEC]    "
    print(f"{prefix}{msg}")


def migrate_book(book_root: Path) -> int:
    """Extract facts from the MD log and import into DB. Returns fact count."""
    book_category = _detect_book_category(book_root)
    log_name = "people-log.md" if book_category == "memoir" else "canon-log.md"

    result = extract_all_facts(book_root, book_category)

    if result["extraction_method"] == "none":
        warning = result["warnings"][0] if result["warnings"] else "no log"
        print(f"  SKIP: {book_root.name} — {warning}")
        return 0

    current = result["current_facts"]
    changed = result["changed_facts"]
    total = len(current) + len(changed)

    if total == 0:
        print(f"  SKIP: {book_root.name} — {log_name} found but no extractable facts")
        return 0

    for w in result["warnings"]:
        print(f"  WARN: {w}")

    book_num = get_book_num(book_root)
    db_slug = get_db_slug_for_book(book_root)

    _log(
        f"{book_root.name} ({book_category}) → {db_slug}.db  "
        f"({len(current)} facts + {len(changed)} CHANGED, book_num={book_num})"
    )

    if DRY_RUN:
        return total

    conn = open_canon_db(db_slug)
    inserted = 0
    try:
        for f in current:
            insert_fact(
                conn,
                book_num=book_num,
                chapter_num=f["chapter_num"],
                subject=f["subject"],
                fact=f["fact"],
                domain=f.get("domain", ""),
            )
            inserted += 1

        for f in changed:
            insert_fact(
                conn,
                book_num=book_num,
                chapter_num=f["chapter_num"],
                subject=f["subject"],
                fact=f["fact"],
                is_revision=True,
                old_value=f["old_value"] or None,
                revision_impacts=json.dumps(f["revision_impacts"]) if f["revision_impacts"] else None,
            )
            inserted += 1
    finally:
        conn.close()

    _log(f"  inserted up to {inserted} rows (duplicates silently skipped via UNIQUE)")
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
        print(f"Migration complete. Up to {total} rows inserted (duplicates silently skipped).")
        print("\nLog files are preserved as read-only archives.")


if __name__ == "__main__":
    main()
