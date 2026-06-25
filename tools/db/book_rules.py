"""CRUD helpers for the book_rules table — Issue #282.

book_rules stores per-book (or series-wide) rules, callbacks, and workflow
instructions that previously lived as HTML-marker blocks inside CLAUDE.md.

rule_type values: "rule" | "callback" | "workflow" | "suppression"
book_num=NULL means the entry applies series-wide (not yet used in Phase 4).
"""

from __future__ import annotations

import sqlite3

_COLS = "id, book_num, rule_type, text, added_at"


def insert_rule(
    conn: sqlite3.Connection,
    *,
    book_num: int | None,
    rule_type: str,
    text: str,
) -> dict:
    """Insert a rule row, idempotent (no-op if text already exists).

    SQLite UNIQUE constraints treat NULL as distinct, so we handle
    book_num=None via explicit pre-check instead of INSERT OR IGNORE.

    Returns {'inserted': bool, 'rule_id': int} — rule_id is the existing id
    when the row already exists and insertion is skipped.
    """
    existing = conn.execute(
        "SELECT id FROM book_rules WHERE book_num IS ? AND rule_type=? AND text=?",
        (book_num, rule_type, text),
    ).fetchone()
    if existing:
        return {"inserted": False, "rule_id": existing["id"]}

    cur = conn.execute(
        "INSERT INTO book_rules (book_num, rule_type, text) VALUES (?, ?, ?)",
        (book_num, rule_type, text),
    )
    conn.commit()
    return {"inserted": True, "rule_id": cur.lastrowid}


def list_rules(
    conn: sqlite3.Connection,
    *,
    book_num: int | None = None,
    rule_type: str | None = None,
) -> list[dict]:
    """Return rules matching the given filters, ordered by id (insertion order).

    book_num=None without rule_type returns ALL rows for the DB.
    To query series-wide rows (book_num IS NULL), pass book_num=None explicitly
    together with a rule_type.
    """
    conditions: list[str] = []
    params: list = []

    if rule_type is not None:
        conditions.append("rule_type = ?")
        params.append(rule_type)

    if book_num is not None:
        conditions.append("book_num = ?")
        params.append(book_num)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = conn.execute(
        f"SELECT {_COLS} FROM book_rules {where} ORDER BY id",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_rule(conn: sqlite3.Connection, rule_id: int) -> dict | None:
    """Return a single rule by id, or None if not found."""
    row = conn.execute(
        f"SELECT {_COLS} FROM book_rules WHERE id = ?",
        (rule_id,),
    ).fetchone()
    return dict(row) if row else None


def update_rule_text(conn: sqlite3.Connection, rule_id: int, new_text: str) -> bool:
    """Update the text of an existing rule. Returns True if a row was changed."""
    cur = conn.execute(
        "UPDATE book_rules SET text = ? WHERE id = ?",
        (new_text.strip(), rule_id),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_rule(conn: sqlite3.Connection, rule_id: int) -> bool:
    """Delete a rule by id. Returns True if a row was deleted."""
    cur = conn.execute("DELETE FROM book_rules WHERE id = ?", (rule_id,))
    conn.commit()
    return cur.rowcount > 0


__all__ = [
    "delete_rule",
    "get_rule",
    "insert_rule",
    "list_rules",
    "update_rule_text",
]
