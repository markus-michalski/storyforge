"""CRUD helpers for the cover_images table — Issue #551."""

from __future__ import annotations

import sqlite3


def upsert_cover_image(
    conn: sqlite3.Connection,
    *,
    book_slug: str,
    filename: str,
    is_final: bool = False,
) -> None:
    """Record an imported cover image file, keyed on (book_slug, filename).

    Re-importing the same filename updates its ``is_final`` flag and
    ``imported_at`` timestamp rather than creating a duplicate row.

    When ``is_final=True``, every other cover image recorded for this
    book_slug is cleared to ``is_final=0`` first — only one file can be
    "the" final version a consumer (e.g. Pandoc export) should use.

    Keyed on ``book_slug`` rather than ``book_num`` (#558): ``book_num``
    defaults to 1 whenever a book's README frontmatter is missing or has an
    unparseable ``series_number``, so two under-specified books in the same
    series-scoped DB would otherwise collide on ``book_num=1`` — sharing
    rows and clobbering each other's final-cover flag. ``book_slug`` is
    unique per book even within a series.

    The clear-then-upsert pair runs inside one explicit transaction
    (``with conn:``) rather than the old trailing ``conn.commit()`` after
    two separately-issued statements. This does NOT make the pair atomic
    under every ``isolation_level`` — ``with conn:`` only commits on
    success / rolls back on exception, it does not itself open a
    transaction; the implicit ``BEGIN`` that makes rollback meaningful here
    still comes from ``sqlite3.isolation_level`` defaulting to ``''``
    (legacy implicit-transaction mode, what ``open_db()`` always uses in
    this codebase). What this change actually buys: if the ``INSERT``
    fails after the ``UPDATE`` already cleared other rows' final flags, the
    ``UPDATE`` is deterministically rolled back instead of being left as a
    dirty, uncommitted statement on the connection for whatever runs next
    to accidentally commit. Previously that failure mode depended on the
    caller never calling ``conn.commit()`` again before handling the error
    (#556 L-3).
    """
    with conn:
        if is_final:
            conn.execute(
                "UPDATE cover_images SET is_final = 0 WHERE book_slug = ? AND filename != ?",
                (book_slug, filename),
            )
        conn.execute(
            """
            INSERT INTO cover_images (book_slug, filename, is_final)
            VALUES (?, ?, ?)
            ON CONFLICT(book_slug, filename) DO UPDATE SET
                is_final = excluded.is_final,
                imported_at = CURRENT_TIMESTAMP
            """,
            (book_slug, filename, int(is_final)),
        )


def get_final_cover_image(conn: sqlite3.Connection, *, book_slug: str) -> str | None:
    """Return the filename marked as final for this book, or None.

    Ordered by ``imported_at DESC, id DESC`` even though the
    ``idx_ci_one_final`` partial unique index (tools/db/connection.py)
    should make at most one ``is_final=1`` row possible per ``book_slug`` —
    defense in depth, matching M-2's fix below, so a hand-edited DB that
    somehow violates that invariant returns the most recent match instead
    of an arbitrary one from an unordered ``LIMIT 1`` (#556 L-1).
    """
    row = conn.execute(
        "SELECT filename FROM cover_images WHERE book_slug = ? AND is_final = 1 "
        "ORDER BY imported_at DESC, id DESC LIMIT 1",
        (book_slug,),
    ).fetchone()
    return row["filename"] if row else None


def list_cover_images(conn: sqlite3.Connection, *, book_slug: str) -> list[dict]:
    """Return every cover image recorded for this book, newest first.

    Ordered by ``imported_at DESC, id DESC`` — ``imported_at`` alone is not
    a reliable "newest first" ordering: SQLite's ``CURRENT_TIMESTAMP`` has
    1-second resolution, so a batch of *new* imports landing within the
    same second degrades to insertion order, the opposite of newest-first.
    ``id`` is monotonically increasing on insert, so using it as the
    tiebreak fixes that case (#556 M-2). Not a complete fix: re-importing
    an existing filename refreshes its ``imported_at`` via ``ON CONFLICT
    ... DO UPDATE`` but keeps its original ``id``, so a same-second
    re-import can still sort behind a same-second row it's actually newer
    than. Root cause is ``imported_at``'s 1-second resolution, not
    something an ``id`` tiebreak alone can fully close.
    """
    rows = conn.execute(
        "SELECT filename, is_final, imported_at FROM cover_images "
        "WHERE book_slug = ? ORDER BY imported_at DESC, id DESC",
        (book_slug,),
    ).fetchall()
    return [dict(r) for r in rows]
