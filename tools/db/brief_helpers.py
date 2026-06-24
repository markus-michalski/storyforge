"""Helpers to load canon_log_facts from DB with Markdown fallback — Issue #280.

Usage in brief assemblers:
    from tools.db.brief_helpers import load_canon_facts_for_brief
    facts = load_canon_facts_for_brief(book_root)
    # book_num is auto-derived from README series_number (C1/H1 fix)
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
    """Return canon facts for the brief, preferring DB over Markdown parse.

    book_num is auto-derived from book_root README series_number when omitted,
    so callers don't need to know it (C1/H1 fix — avoids the book_num=1 default
    bug that silently dropped all facts for series books #2+).

    Strategy:
    1. Resolve book_num from README if not provided.
    2. Open the per-series/book SQLite DB.
    3. If it has rows: return query_facts() result (fast SQL path).
    4. If DB is empty or fails: parse canon-log.md via the legacy parser.
       The parsed facts share the same dict schema so callers don't branch.
    """
    if book_num is None:
        book_num = get_book_num(book_root)

    db_slug = get_db_slug_for_book(book_root)
    try:
        conn = open_canon_db(db_slug)
        try:
            db_facts = query_facts(conn, book_num=book_num, up_to_chapter=chapter_num)
        finally:
            conn.close()
        if db_facts:
            return db_facts
    except (sqlite3.Error, OSError):
        pass

    # Fallback: parse Markdown log (canon-log.md stays as read-only archive)
    return _parse_from_markdown(book_root)


def _parse_from_markdown(book_root: Path) -> list[dict]:
    canon_path = book_root / "plot" / "canon-log.md"
    if not canon_path.is_file():
        return []
    try:
        from tools.state.review_brief import _parse_canon_log_facts
        text = canon_path.read_text(encoding="utf-8")
        return _parse_canon_log_facts(text)
    except (OSError, ValueError):
        return []
