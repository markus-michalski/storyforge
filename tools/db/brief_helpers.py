"""Helpers to load canon_log_facts from DB — Issue #280, updated #291.

Usage in brief assemblers (continuity_brief, review_brief):
    from tools.db.brief_helpers import load_canon_facts_for_brief
    facts = load_canon_facts_for_brief(book_root)
    # book_num is auto-derived from README series_number (C1/H1 fix)

Note: The MD fallback was removed in Issue #291. If the DB is empty,
callers receive an empty list. Migrate existing canon-log.md content to
the DB via scripts/migrate_canon_log_to_db.py before relying on this
function. For the chapter-writer path, build_canon_brief() reads both
the DB and the MD archive and merges them.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tools.db.canon_facts import query_facts
from tools.db.connection import get_book_num, get_db_slug_for_book, open_canon_db

_ALL_CHAPTERS = 10**9  # sentinel: "all chapters written so far"


def load_canon_facts_for_brief(
    book_root: Path,
    *,
    book_num: int | None = None,
    chapter_num: int = _ALL_CHAPTERS,
) -> list[dict]:
    """Return canon facts for the brief from the SQLite DB.

    book_num is auto-derived from book_root README series_number when omitted,
    so callers don't need to know it (C1/H1 fix — avoids the book_num=1 default
    bug that silently dropped all facts for series books #2+).

    Returns an empty list if the DB is empty or unreachable. Migrate
    canon-log.md content first (migrate_canon_log_to_db.py) if facts are
    missing. The MD fallback was removed in Issue #291 — dual storage is
    not acceptable; unread Markdown content should be migrated, not silently
    served as a fallback.
    """
    if book_num is None:
        book_num = get_book_num(book_root)

    db_slug = get_db_slug_for_book(book_root)
    try:
        conn = open_canon_db(db_slug)
        try:
            rows = query_facts(conn, book_num=book_num, up_to_chapter=chapter_num)
        finally:
            conn.close()
        return [_db_row_to_legacy_fact(r) for r in rows]
    except (sqlite3.Error, OSError):
        return []


def _db_row_to_legacy_fact(row: dict) -> dict:
    """Map a DB canon_facts row to the legacy MD-parsed fact schema.

    Keeps downstream consumers (review_brief, continuity_brief, skills) working
    without a schema change — they still receive the same keys as before
    (fact, established_in, status, notes, domain).
    """
    return {
        "fact": row["fact"],
        "subject": row.get("subject", ""),
        "established_in": f"Ch {row['chapter_num']}",
        "status": "CHANGED" if row["is_revision"] else "ACTIVE",
        "notes": row.get("old_value") or "",
        "domain": row.get("domain") or "",
    }
