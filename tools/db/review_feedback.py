"""CRUD helpers for the review_feedback table — Epic #663 / Issue #664."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Sequence

VALID_SOURCES: frozenset[str] = frozenset({
    "writer", "reviewer", "fixer", "rewriter", "humanizer", "proofreader", "self_edit",
})
VALID_DECISIONS: frozenset[str] = frozenset({"accepted", "reworked", "rejected", "self_edit"})
VALID_STATUSES: frozenset[str] = frozenset({"pending", "classified", "harvested", "discarded"})
VALID_CATEGORIES: frozenset[str] = frozenset({"fiction", "memoir"})

TERMINAL_STATUSES: frozenset[str] = frozenset({"harvested", "discarded"})
OPEN_STATUSES: tuple[str, ...] = ("pending", "classified")

_TEXT_FIELDS = ("comment_text", "before_text", "after_text", "proposal_text")
_COLUMNS = (
    "id, author_slug, book_slug, chapter_slug, book_category, genres, source_skill, "
    "decision, comment_text, before_text, after_text, proposal_text, dimension, "
    "direction, normalized_rule, status, content_hash, created_at, updated_at"
)


def _content_hash(source_skill: str, decision: str, texts: Sequence[str]) -> str:
    # JSON encoding keeps field boundaries unambiguous, whatever the texts contain.
    payload = json.dumps(
        [source_skill, decision, *(t.strip() for t in texts)], ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_slug(value: str | None, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _check(value: str, allowed: frozenset[str], name: str) -> None:
    if value not in allowed:
        raise ValueError(f"invalid {name} {value!r}; expected one of {sorted(allowed)}")


def insert_feedback(
    conn: sqlite3.Connection,
    *,
    author_slug: str,
    book_slug: str,
    chapter_slug: str,
    source_skill: str,
    decision: str,
    book_category: str,
    genres: str = "",
    comment_text: str = "",
    before_text: str = "",
    after_text: str = "",
    proposal_text: str = "",
    dimension: str | None = None,
    direction: str | None = None,
    normalized_rule: str | None = None,
) -> int | None:
    """Insert one feedback entry and return its id, or None for a duplicate.

    Memoir rows are stored without any raw text and must arrive already
    classified, so names and facts about real people never reach the table.
    ``book_category`` is required on purpose: a default would fail open for memoir.

    Note: the content hash of a memoir row is computed over the raw text before it
    is discarded. Treat it as a dedup key, not as anonymisation; ``dimension``,
    ``direction`` and ``normalized_rule`` must be written without names or facts.
    """
    _require_slug(author_slug, "author_slug")
    _require_slug(book_slug, "book_slug")
    _require_slug(chapter_slug, "chapter_slug")
    _check(source_skill, VALID_SOURCES, "source_skill")
    _check(decision, VALID_DECISIONS, "decision")
    _check(book_category, VALID_CATEGORIES, "book_category")

    texts = (comment_text, before_text, after_text, proposal_text)
    if not any(t.strip() for t in texts):
        raise ValueError("feedback entry has no content (comment, before/after or proposal)")

    classified = False
    if dimension is not None or direction is not None:
        dimension = (dimension or "").strip()
        direction = (direction or "").strip()
        if not dimension or not direction:
            raise ValueError("classification needs both a non-empty dimension and direction")
        classified = True
    if book_category == "memoir":
        if not classified:
            raise ValueError("memoir feedback requires a classification at insert time")
        comment_text = before_text = after_text = proposal_text = ""

    cur = conn.execute(
        """
        INSERT OR IGNORE INTO review_feedback
            (author_slug, book_slug, chapter_slug, book_category, genres, source_skill,
             decision, comment_text, before_text, after_text, proposal_text,
             dimension, direction, normalized_rule, status, content_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            author_slug, book_slug, chapter_slug, book_category, genres, source_skill,
            decision, comment_text, before_text, after_text, proposal_text,
            dimension if classified else None,
            direction if classified else None,
            normalized_rule if classified else None,
            "classified" if classified else "pending",
            _content_hash(source_skill, decision, texts),
        ),
    )
    conn.commit()
    return cur.lastrowid if cur.rowcount == 1 else None


def get_feedback(conn: sqlite3.Connection, feedback_id: int) -> dict | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM review_feedback WHERE id=?", (feedback_id,)
    ).fetchone()
    return dict(row) if row else None


def list_feedback(
    conn: sqlite3.Connection,
    author_slug: str,
    *,
    book_slug: str | None = None,
    chapter_slug: str | None = None,
    statuses: str | Sequence[str] = OPEN_STATUSES,
) -> list[dict]:
    """Return an author's feedback entries (open ones by default), oldest first."""
    if isinstance(statuses, str):
        statuses = (statuses,)
    for status in statuses:
        _check(status, VALID_STATUSES, "status")
    if not statuses:
        return []

    clauses = ["author_slug=?", f"status IN ({','.join('?' * len(statuses))})"]
    params: list[str] = [author_slug, *statuses]
    if book_slug is not None:
        clauses.append("book_slug=?")
        params.append(book_slug)
    if chapter_slug is not None:
        clauses.append("chapter_slug=?")
        params.append(chapter_slug)

    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM review_feedback WHERE {' AND '.join(clauses)} ORDER BY id",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def set_classification(
    conn: sqlite3.Connection,
    feedback_id: int,
    *,
    dimension: str,
    direction: str,
    normalized_rule: str,
) -> bool:
    """Store the (single) classification of an open entry. False if not found or closed."""
    if not dimension.strip() or not direction.strip():
        raise ValueError("dimension and direction must not be empty")
    cur = conn.execute(
        """
        UPDATE review_feedback
        SET dimension=?, direction=?, normalized_rule=?, status='classified',
            updated_at=CURRENT_TIMESTAMP
        WHERE id=? AND status IN ('pending', 'classified')
        """,
        (dimension, direction, normalized_rule, feedback_id),
    )
    conn.commit()
    return cur.rowcount == 1


def mark_feedback(conn: sqlite3.Connection, ids: Iterable[int], status: str) -> int:
    """Close open entries as harvested or discarded. Returns the number of rows changed.

    Rows that are already closed are left alone, so the count is the number of
    entries this call actually transitioned.
    """
    _check(status, TERMINAL_STATUSES, "status")
    id_list = list(ids)
    if not id_list:
        return 0
    cur = conn.execute(
        f"""
        UPDATE review_feedback SET status=?, updated_at=CURRENT_TIMESTAMP
        WHERE id IN ({','.join('?' * len(id_list))})
          AND status IN ('pending', 'classified')
        """,
        [status, *id_list],
    )
    conn.commit()
    return cur.rowcount


def remove_author_feedback(conn: sqlite3.Connection, author_slug: str) -> int:
    """Delete every feedback row of an author (used by delete_author). Returns the count."""
    cur = conn.execute("DELETE FROM review_feedback WHERE author_slug=?", (author_slug,))
    conn.commit()
    return cur.rowcount
