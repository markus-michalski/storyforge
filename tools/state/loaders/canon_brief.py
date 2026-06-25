"""Canon-log projector for the chapter-writing brief (Issue #161, #297).

Queries the ``canon_facts`` SQLite table exclusively.  The Markdown log
(canon-log.md / people-log.md) is no longer read by this module — run
``scripts/migrate_canon_log_to_db.py`` once to import existing log entries.

Schema returned
---------------
::

    {
      "current_facts": [
        {"fact": "...", "chapter": "5", "source": "chapter:5:db:Theo:locations"}
      ],
      "changed_facts": [
        {
          "old": "...", "new": "...",
          "chapter": "14",
          "source": "chapter:14:db:CHANGED:Theo",
          "revision_impact": ["15-aftermath", "17-the-school"]
        }
      ],
      "pov_relevant_facts": [...],   # subset of current_facts filtered on POV name
      "scanned_chapters": [1, 8, 14],
      "as_of": "26",
      "extraction_method": "db" | "none",
      "warnings": []
    }
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from tools.db.canon_facts import query_facts
from tools.db.connection import get_book_num, get_db_slug_for_book, open_canon_db


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CHAPTER_DIR_RE = re.compile(r"^(?P<num>\d{1,3})-")
_DEFAULT_SCOPE = 8


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_canon_brief(
    book_root: Path,
    chapter_slug: str,
    pov_character: str = "",
    *,
    book_category: str = "fiction",  # retained for API compatibility; unused post-#297
    scope_chapters: int = _DEFAULT_SCOPE,
) -> dict[str, Any]:
    """Project canon facts into a bounded, structured brief.

    Queries the ``canon_facts`` SQLite table (Issue #291/#297).
    Run ``scripts/migrate_canon_log_to_db.py`` once to migrate legacy MD facts.

    Args:
        book_root: Project root containing ``plot/``.
        chapter_slug: Chapter being written — defines the scope window.
        pov_character: Display name of the POV character for ``pov_relevant_facts``.
        book_category: Retained for API compatibility; not used post-#297.
        scope_chapters: How many prior chapters to include in ``current_facts``.

    Returns:
        Structured canon brief dict.
    """
    current_num = _chapter_number(chapter_slug)
    pov_name_lower = pov_character.lower().strip() if pov_character else ""

    db_result = _load_db_facts(book_root, current_num, scope_chapters)
    has_db = bool(db_result["current"] or db_result["changed"])

    if not has_db:
        return _empty(
            "No canon facts in DB — use add_canon_fact() to record new facts, "
            "or run scripts/migrate_canon_log_to_db.py to import from canon-log.md."
        )

    current_facts = db_result["current"]
    changed_facts = db_result["changed"]
    pov_facts = _filter_pov(current_facts, pov_name_lower)

    # Derive scanned_chapters + as_of from DB facts for schema consistency.
    chapter_nums = sorted({
        int(f["chapter"]) for f in current_facts
        if str(f.get("chapter", "")).isdigit()
    })
    as_of = str(max(chapter_nums)) if chapter_nums else None

    return {
        "current_facts": current_facts,
        "changed_facts": changed_facts,
        "pov_relevant_facts": pov_facts,
        "scanned_chapters": chapter_nums,
        "as_of": as_of,
        "extraction_method": "db",
        "warnings": _pov_warnings(pov_name_lower),
    }


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _load_db_facts(
    book_root: Path,
    current_num: int,
    scope_chapters: int,
) -> dict[str, list[dict[str, Any]]]:
    """Query canon_facts table and return facts in the brief schema.

    Returns ``{"current": [...], "changed": [...]}`` — empty lists on any
    DB error so the caller can fall through to the empty-brief path.
    """
    if not (book_root / "README.md").is_file():
        return {"current": [], "changed": []}

    try:
        book_num = get_book_num(book_root)
        db_slug = get_db_slug_for_book(book_root)
        conn = open_canon_db(db_slug)
        try:
            rows = query_facts(
                conn, book_num=book_num, up_to_chapter=max(0, current_num - 1)
            )
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return {"current": [], "changed": []}

    scope_min = max(1, current_num - scope_chapters) if scope_chapters > 0 else 1
    current: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []

    for row in rows:
        ch_num = row["chapter_num"]
        subject = row.get("subject", "")
        fact = row["fact"]
        domain = row.get("domain", "")

        if row["is_revision"]:
            raw = row.get("revision_impacts") or ""
            try:
                impacts = json.loads(raw) if raw else []
            except (ValueError, TypeError):
                impacts = []
            changed.append({
                "old": row.get("old_value") or "",
                "new": fact,
                "chapter": str(ch_num),
                "source": f"chapter:{ch_num}:db:CHANGED:{subject}",
                "revision_impact": impacts,
            })
        elif ch_num == 0 or ch_num >= scope_min:
            # ch_num == 0: heuristic-migrated facts with no chapter attribution
            # are always in scope (they're global/uncategorized facts).
            source = f"chapter:{ch_num}:db:{subject}"
            if domain:
                source = f"{source}:{domain}"
            current.append({
                "fact": fact,
                "chapter": str(ch_num),
                "source": source,
            })

    return {"current": current, "changed": changed}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chapter_number(chapter_slug: str) -> int:
    m = _CHAPTER_DIR_RE.match(chapter_slug)
    return int(m.group("num")) if m else 0


def _filter_pov(facts: list[dict[str, Any]], pov_name_lower: str) -> list[dict[str, Any]]:
    if not pov_name_lower:
        return []
    tokens = [t for t in pov_name_lower.split() if len(t) >= 3]
    if not tokens:
        return [
            f for f in facts
            if pov_name_lower in f.get("source", "").lower()
            or pov_name_lower in f.get("fact", "").lower()
        ]
    patterns = [re.compile(rf"\b{re.escape(t)}\b", re.IGNORECASE) for t in tokens]
    return [
        f for f in facts
        if any(
            p.search(f.get("source", "")) or p.search(f.get("fact", ""))
            for p in patterns
        )
    ]


def _pov_warnings(pov_name_lower: str) -> list[str]:
    if not pov_name_lower:
        return [
            "pov_character not set on chapter — pov_relevant_facts cannot be filtered. "
            "Add pov_character to the chapter README frontmatter."
        ]
    return []


def _empty(warning: str) -> dict[str, Any]:
    return {
        "current_facts": [],
        "changed_facts": [],
        "pov_relevant_facts": [],
        "scanned_chapters": [],
        "as_of": None,
        "extraction_method": "none",
        "warnings": [warning],
    }


__all__ = ["build_canon_brief"]
