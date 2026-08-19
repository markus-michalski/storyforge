"""CRUD helpers for the canon_facts table — Issue #280."""

from __future__ import annotations

import sqlite3


def insert_fact(
    conn: sqlite3.Connection,
    *,
    book_num: int,
    chapter_num: int,
    subject: str,
    fact: str,
    domain: str = "",
    is_revision: bool = False,
    old_value: str | None = None,
    revision_impacts: str | None = None,
) -> None:
    """Insert a canon fact. Silently ignores exact duplicates (UNIQUE constraint)."""
    conn.execute(
        """
        INSERT OR IGNORE INTO canon_facts
            (book_num, chapter_num, subject, fact, domain, is_revision, old_value, revision_impacts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (book_num, chapter_num, subject, fact, domain,
         int(is_revision), old_value, revision_impacts),
    )
    conn.commit()


def query_facts(
    conn: sqlite3.Connection,
    *,
    book_num: int,
    up_to_chapter: int,
) -> list[dict]:
    """Return all facts visible when writing chapter `up_to_chapter` of book `book_num`.

    Includes facts from all prior books (book_num < current) and all chapters
    up to and including up_to_chapter in the current book.
    """
    rows = conn.execute(
        """
        SELECT id, book_num, chapter_num, subject, fact, domain,
               is_revision, old_value, revision_impacts, created_at
        FROM canon_facts
        WHERE (book_num < ?)
           OR (book_num = ? AND chapter_num <= ?)
        ORDER BY book_num, chapter_num
        """,
        (book_num, book_num, up_to_chapter),
    ).fetchall()
    return [dict(r) for r in rows]


def count_facts_per_chapter(
    conn: sqlite3.Connection,
    *,
    book_num: int,
) -> dict[int, int]:
    """Return ``{chapter_num: fact_count}`` for a book's recorded canon facts.

    Issue #476: book-dashboard needs a per-chapter canon-fact count, and
    neither ``get_book_progress()`` nor ``get_canon_brief()`` expose one —
    the latter is a backward-looking context window that always excludes the
    target chapter's own facts, structurally the wrong tool for this. This
    aggregates directly from the ``canon_facts`` table instead.

    Chapters with zero recorded facts are simply absent from the returned
    mapping — callers should treat a missing key as a count of 0, not an
    error.
    """
    rows = conn.execute(
        """
        SELECT chapter_num, COUNT(*) as cnt
        FROM canon_facts
        WHERE book_num = ?
        GROUP BY chapter_num
        """,
        (book_num,),
    ).fetchall()
    return {int(r["chapter_num"]): int(r["cnt"]) for r in rows}


def import_from_parsed_facts(
    conn: sqlite3.Connection,
    *,
    book_num: int,
    chapter_num: int,
    parsed_facts: list[dict],
) -> int:
    """Bulk-insert facts from _parse_canon_log_facts() output. Returns inserted count."""
    inserted = 0
    for f in parsed_facts:
        subject = f.get("fact", "")[:120]  # fact field holds the sentence; use as subject
        fact_body = f.get("notes", "") or f.get("established_in", "")
        domain = f.get("domain", "")
        if not subject:
            continue
        try:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO canon_facts
                    (book_num, chapter_num, subject, fact, domain)
                VALUES (?, ?, ?, ?, ?)
                """,
                (book_num, chapter_num, subject, fact_body or subject, domain),
            )
            inserted += cur.rowcount  # 1 on insert, 0 on IGNORE-skip
        except sqlite3.Error:
            continue
    conn.commit()
    return inserted
