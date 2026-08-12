"""CRUD helpers for the cover_images table — Issue #551."""

from __future__ import annotations

import sqlite3


def upsert_cover_image(
    conn: sqlite3.Connection,
    *,
    book_num: int,
    filename: str,
    is_final: bool = False,
) -> None:
    """Record an imported cover image file, keyed on (book_num, filename).

    Re-importing the same filename updates its ``is_final`` flag and
    ``imported_at`` timestamp rather than creating a duplicate row.

    When ``is_final=True``, every other cover image recorded for this
    book_num is cleared to ``is_final=0`` first — only one file can be
    "the" final version a consumer (e.g. Pandoc export) should use.
    """
    if is_final:
        conn.execute(
            "UPDATE cover_images SET is_final = 0 WHERE book_num = ? AND filename != ?",
            (book_num, filename),
        )
    conn.execute(
        """
        INSERT INTO cover_images (book_num, filename, is_final)
        VALUES (?, ?, ?)
        ON CONFLICT(book_num, filename) DO UPDATE SET
            is_final = excluded.is_final,
            imported_at = CURRENT_TIMESTAMP
        """,
        (book_num, filename, int(is_final)),
    )
    conn.commit()


def get_final_cover_image(conn: sqlite3.Connection, *, book_num: int) -> str | None:
    """Return the filename marked as final for this book, or None."""
    row = conn.execute(
        "SELECT filename FROM cover_images WHERE book_num = ? AND is_final = 1 LIMIT 1",
        (book_num,),
    ).fetchone()
    return row["filename"] if row else None


def list_cover_images(conn: sqlite3.Connection, *, book_num: int) -> list[dict]:
    """Return every cover image recorded for this book, newest first."""
    rows = conn.execute(
        "SELECT filename, is_final, imported_at FROM cover_images WHERE book_num = ? ORDER BY imported_at DESC",
        (book_num,),
    ).fetchall()
    return [dict(r) for r in rows]
