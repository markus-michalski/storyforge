"""CRUD helpers for the author_discoveries table — Issue #281."""

from __future__ import annotations

import sqlite3

VALID_TYPES: frozenset[str] = frozenset({"recurring_tics", "style_principles", "donts"})


def insert_discovery(
    conn: sqlite3.Connection,
    *,
    author_slug: str,
    discovery_type: str,
    text: str,
    book_slug: str = "",
    source_genres: str = "",
    universal: bool = False,
    example: str = "",
    date_added: str = "",
) -> bool:
    """Insert a discovery. Returns True if inserted, False if duplicate (UNIQUE ignored)."""
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO author_discoveries
            (author_slug, discovery_type, text, book_slug, source_genres, universal, example, date_added)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (author_slug, discovery_type, text, book_slug, source_genres, int(universal), example, date_added),
    )
    conn.commit()
    return cur.rowcount == 1


def get_discoveries(
    conn: sqlite3.Connection,
    author_slug: str,
    discovery_type: str | None = None,
) -> list[dict]:
    """Return all discoveries for an author, optionally filtered by type."""
    cols = "id, author_slug, discovery_type, text, book_slug, source_genres, universal, example, date_added"
    if discovery_type:
        rows = conn.execute(
            f"SELECT {cols} FROM author_discoveries WHERE author_slug=? AND discovery_type=? ORDER BY id",
            (author_slug, discovery_type),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT {cols} FROM author_discoveries WHERE author_slug=? ORDER BY discovery_type, id",
            (author_slug,),
        ).fetchall()
    return [dict(r) for r in rows]


def discovery_exists(
    conn: sqlite3.Connection,
    author_slug: str,
    discovery_type: str,
    text: str,
) -> bool:
    """Return True if an exact duplicate exists (same author+type+text)."""
    row = conn.execute(
        "SELECT 1 FROM author_discoveries WHERE author_slug=? AND discovery_type=? AND text=?",
        (author_slug, discovery_type, text),
    ).fetchone()
    return row is not None


def update_source_genres(
    conn: sqlite3.Connection,
    *,
    author_slug: str,
    book_slug: str,
    source_genres: str,
) -> int:
    """Set source_genres for all discoveries from a specific book. Returns updated row count."""
    cur = conn.execute(
        """
        UPDATE author_discoveries
        SET source_genres=?, updated_at=CURRENT_TIMESTAMP
        WHERE author_slug=? AND book_slug=?
        """,
        (source_genres, author_slug, book_slug),
    )
    conn.commit()
    return cur.rowcount


def remove_discovery(
    conn: sqlite3.Connection,
    *,
    author_slug: str,
    discovery_type: str,
    text: str,
) -> bool:
    """Delete a single discovery by exact match. Returns True if a row was removed."""
    cur = conn.execute(
        "DELETE FROM author_discoveries WHERE author_slug=? AND discovery_type=? AND text=?",
        (author_slug, discovery_type, text),
    )
    conn.commit()
    return cur.rowcount == 1


def discoveries_as_writing_discoveries(rows: list[dict]) -> dict[str, list[dict]]:
    """Convert DB rows to the writing_discoveries format consumed by get_author().

    Output is backward-compatible with the old _parse_writing_discoveries() shape:
    {"recurring_tics": [...], "style_principles": [...], "donts": [...]}
    Each entry: {"text", "origins": [{"book", "date"}], "genres"?, "example"?}
    """
    result: dict[str, list[dict]] = {"recurring_tics": [], "style_principles": [], "donts": []}
    for row in rows:
        dtype = row.get("discovery_type", "")
        if dtype not in result:
            continue
        entry: dict = {
            "text": row["text"],
            "origins": (
                [{"book": row["book_slug"], "date": row["date_added"]}]
                if row.get("book_slug")
                else []
            ),
        }
        if row.get("source_genres"):
            entry["genres"] = [g.strip() for g in row["source_genres"].split(",") if g.strip()]
        if row.get("example"):
            entry["example"] = row["example"]
        if row.get("universal"):
            entry["universal"] = bool(row["universal"])
        result[dtype].append(entry)
    return result
