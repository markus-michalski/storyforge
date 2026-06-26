"""Helpers to load canon_log_facts and book_rules from DB — Issue #280/#304.

Usage in brief assemblers (continuity_brief, review_brief, chapter_writing_brief):
    from tools.db.brief_helpers import (
        load_canon_facts_for_brief,
        load_rules_for_brief,
        load_callbacks_for_brief,
    )
    facts = load_canon_facts_for_brief(book_root)
    rules = load_rules_for_brief(book_root)
    callbacks = load_callbacks_for_brief(book_root)
    # book_num is auto-derived from README series_number (C1/H1 fix)

Note: both canon_facts and book_rules read from DB exclusively (Issue #291/#304).
If the DB is empty, callers receive an empty list.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from tools.db.book_rules import list_rules
from tools.db.canon_facts import query_facts
from tools.db.connection import get_book_num, get_db_slug_for_book, open_canon_db

_BAN_CUE_RE = re.compile(
    r"\b(banned|ban|avoid|never|don['']?t\s+use|do\s+not\s+use|limit|stop\s+using)\b",
    re.IGNORECASE,
)


def _classify_rule(text: str) -> str:
    if "`" in text and _BAN_CUE_RE.search(text):
        return "block"
    return "advisory"

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


def load_rules_for_brief(book_root: Path) -> list[dict]:
    """Return rule-type entries from the book_rules DB for a brief.

    Returns list of {"text": str, "severity": "block" | "advisory"}.
    Empty list if DB is unreachable or empty.
    """
    book_num = get_book_num(book_root)
    db_slug = get_db_slug_for_book(book_root)
    try:
        conn = open_canon_db(db_slug)
        try:
            rows = list_rules(conn, book_num=book_num, rule_type="rule")
        finally:
            conn.close()
        return [{"text": r["text"], "severity": _classify_rule(r["text"])} for r in rows]
    except (sqlite3.Error, OSError):
        return []


def load_callbacks_for_brief(book_root: Path) -> list[str]:
    """Return callback-type entries from the book_rules DB for a brief.

    Returns list of callback text strings.
    Empty list if DB is unreachable or empty.
    """
    book_num = get_book_num(book_root)
    db_slug = get_db_slug_for_book(book_root)
    try:
        conn = open_canon_db(db_slug)
        try:
            rows = list_rules(conn, book_num=book_num, rule_type="callback")
        finally:
            conn.close()
        return [r["text"] for r in rows]
    except (sqlite3.Error, OSError):
        return []
