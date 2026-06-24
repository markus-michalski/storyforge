"""CRUD helpers for the character_snapshots table — Issue #281."""

from __future__ import annotations

import json
import sqlite3

_LIST_FIELDS = ("injuries", "clothing", "inventory", "altered_states")
_COLS = "char_slug, book_num, chapter_num, injuries, clothing, inventory, altered_states, environmental_limiters, updated_at"


def upsert_snapshot(
    conn: sqlite3.Connection,
    *,
    char_slug: str,
    book_num: int,
    chapter_num: int,
    injuries: list[str] | None = None,
    clothing: list[str] | None = None,
    inventory: list[str] | None = None,
    altered_states: list[str] | None = None,
    environmental_limiters: str | None = None,
) -> None:
    """Insert or replace a character snapshot, merging with the latest prior state.

    Fields not provided (None) are inherited from the latest existing snapshot for
    (char_slug, book_num) so partial updates don't erase established state.
    """
    existing = get_latest_snapshot_for_book(conn, char_slug, book_num) or {}

    merged_injuries = injuries if injuries is not None else existing.get("injuries", [])
    merged_clothing = clothing if clothing is not None else existing.get("clothing", [])
    merged_inventory = inventory if inventory is not None else existing.get("inventory", [])
    merged_states = altered_states if altered_states is not None else existing.get("altered_states", [])
    merged_env = (
        environmental_limiters
        if environmental_limiters is not None
        else existing.get("environmental_limiters", "")
    )

    conn.execute(
        """
        INSERT OR REPLACE INTO character_snapshots
            (char_slug, book_num, chapter_num, injuries, clothing, inventory,
             altered_states, environmental_limiters, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            char_slug,
            book_num,
            chapter_num,
            json.dumps(merged_injuries),
            json.dumps(merged_clothing),
            json.dumps(merged_inventory),
            json.dumps(merged_states),
            merged_env or "",
        ),
    )
    conn.commit()


def get_latest_snapshot(conn: sqlite3.Connection, char_slug: str) -> dict | None:
    """Return the most recent snapshot for a character across all books."""
    row = conn.execute(
        f"SELECT {_COLS} FROM character_snapshots WHERE char_slug=? ORDER BY book_num DESC, chapter_num DESC LIMIT 1",
        (char_slug,),
    ).fetchone()
    return _decode_row(dict(row)) if row else None


def get_latest_snapshot_for_book(
    conn: sqlite3.Connection,
    char_slug: str,
    book_num: int,
) -> dict | None:
    """Return the most recent snapshot for a character within a specific book."""
    row = conn.execute(
        f"SELECT {_COLS} FROM character_snapshots WHERE char_slug=? AND book_num=? ORDER BY chapter_num DESC LIMIT 1",
        (char_slug, book_num),
    ).fetchone()
    return _decode_row(dict(row)) if row else None


def get_all_latest_snapshots(conn: sqlite3.Connection) -> list[dict]:
    """Return the latest snapshot per character (for the continuity brief).

    Uses a subquery to pick the row with the highest combined sort key.
    Assumes chapter_num < 100_000 (i.e., no book has more than 99999 chapters).
    """
    rows = conn.execute(
        f"""
        SELECT {", ".join(f"cs.{c.strip()}" for c in _COLS.split(","))}
        FROM character_snapshots cs
        INNER JOIN (
            SELECT char_slug,
                   MAX(book_num * 100000 + chapter_num) AS max_key
            FROM character_snapshots
            GROUP BY char_slug
        ) latest
            ON cs.char_slug = latest.char_slug
            AND (cs.book_num * 100000 + cs.chapter_num) = latest.max_key
        ORDER BY cs.char_slug
        """
    ).fetchall()
    return [_decode_row(dict(r)) for r in rows]


def _decode_row(row: dict) -> dict:
    """Decode JSON list columns back to Python lists."""
    for field in _LIST_FIELDS:
        raw = row.get(field)
        if isinstance(raw, str):
            try:
                row[field] = json.loads(raw)
            except json.JSONDecodeError:
                row[field] = []
        elif raw is None:
            row[field] = []
    return row
