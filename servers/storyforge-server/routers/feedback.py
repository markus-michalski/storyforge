"""Review-feedback MCP tools — Epic #663 / Issue #665.

Thin layer over ``tools/db/review_feedback.py``: it resolves author, genres
and book category from the book itself, validates classifications against the
closed vocabulary in ``reference/craft/voice-dimensions.md`` and keeps real
names out of memoir rows. Promotion into the author profile is not done here;
it keeps going through ``write_author_discovery``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from mcp.types import ToolAnnotations

from tools.analysis.voice_dimensions import VoiceDimensionError, validate_classification
from tools.db.connection import open_authors_db
from tools.db.review_feedback import (
    VALID_DECISIONS,
    VALID_SOURCES,
    get_feedback,
    insert_feedback,
    list_feedback,
    mark_feedback,
    set_classification,
)

from . import _app
from ._app import mcp

MAX_RULE_LENGTH = 240


def _error(message: str) -> str:
    return json.dumps({"error": message})


def _resolve_book(book_slug: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return ``(book, error_message)`` from the state cache."""
    book = (_app._cache.get().get("books") or {}).get(book_slug)
    if not book:
        return None, f"Book '{book_slug}' not found"
    if not str(book.get("author", "")).strip():
        return None, (
            f"Book '{book_slug}' has no author in its README; set `author` so feedback "
            f"can be attributed to an author profile"
        )
    return book, None


def _category(book: dict[str, Any]) -> str:
    return str(book.get("book_category") or "fiction")


def _person_names(book: dict[str, Any]) -> set[str]:
    """Names (full and parts of at least 3 letters) of the real people in a memoir book."""
    names: set[str] = set()
    for person in (book.get("people") or {}).values():
        for key in ("name", "real_name"):
            value = str(person.get(key) or "").strip()
            if not value:
                continue
            names.add(value.lower())
            names.update(part.lower() for part in re.findall(r"\w+", value) if len(part) >= 3)
    return names


def _check_rule(book: dict[str, Any], normalized_rule: str) -> str | None:
    rule = normalized_rule.strip()
    if not rule:
        return "normalized_rule must state the rule in one plain sentence"
    if len(rule) > MAX_RULE_LENGTH or "\n" in rule or "\r" in rule:
        return f"normalized_rule must be a single line of at most {MAX_RULE_LENGTH} characters"
    if _category(book) == "memoir":
        words = {w.lower() for w in re.findall(r"\w+", rule)}
        lowered = rule.lower()
        for name in sorted(_person_names(book)):
            if name in words or (" " in name and name in lowered):
                return (
                    "normalized_rule must not contain the name of a person from this memoir "
                    "(name or real name); state the rule without names or facts"
                )
    return None


def _check_classification(
    book: dict[str, Any], dimension: str, direction: str, normalized_rule: str
) -> str | None:
    try:
        validate_classification(dimension, direction, _category(book))
    except VoiceDimensionError as exc:
        return str(exc)
    return _check_rule(book, normalized_rule)


def _entry_view(row: dict[str, Any], chapter_slug: str) -> dict[str, Any]:
    keys = (
        "id", "book_slug", "chapter_slug", "source_skill", "decision", "comment_text",
        "before_text", "after_text", "proposal_text", "dimension", "direction",
        "normalized_rule", "status", "genres", "book_category", "created_at",
    )
    view = {k: row[k] for k in keys}
    view["carried_over"] = bool(chapter_slug) and row["chapter_slug"] != chapter_slug
    return view


@mcp.tool(annotations=ToolAnnotations(idempotent_hint=True))
def log_review_feedback(
    book_slug: str,
    chapter_slug: str,
    source_skill: str,
    decision: str,
    comment_text: str = "",
    before_text: str = "",
    after_text: str = "",
    proposal_text: str = "",
    dimension: str = "",
    direction: str = "",
    normalized_rule: str = "",
) -> str:
    """Log one piece of review feedback for later voice harvesting (Epic #663).

    Call it whenever the author's correction or review comment has been verified
    and applied, reworked or rejected. Author, genres and book category come
    from the book itself. Logging the same content twice is harmless.

    Memoir books: raw text is never stored, so ``dimension``, ``direction`` and
    ``normalized_rule`` are required, and the rule must not contain the name of
    a person from the book.

    Args:
        book_slug: Book the feedback belongs to.
        chapter_slug: Chapter slug (must exist in the book).
        source_skill: writer, reviewer, fixer, rewriter, humanizer, proofreader or self_edit.
        decision: accepted, reworked, rejected or self_edit.
        comment_text: The author's comment or instruction.
        before_text: Text before the change.
        after_text: Text after the change.
        proposal_text: For a rejected proposal, what was proposed.
        dimension: Voice dimension from reference/craft/voice-dimensions.md (optional for fiction).
        direction: Direction within that dimension (required together with dimension).
        normalized_rule: One plain sentence stating the rule (required with a classification).

    Returns ``{logged, duplicate, id, status}`` or ``{error: ...}``.
    """
    book, error = _resolve_book(book_slug)
    if error or book is None:
        return _error(error or "book not resolved")

    if chapter_slug not in (book.get("chapters_data") or {}):
        return _error(
            f"Chapter '{chapter_slug}' not found in book '{book_slug}'; "
            f"known chapters: {', '.join(sorted(book.get('chapters_data') or {})) or 'none'}"
        )
    if source_skill not in VALID_SOURCES:
        return _error(f"invalid source_skill {source_skill!r}; allowed: {', '.join(sorted(VALID_SOURCES))}")
    if decision not in VALID_DECISIONS:
        return _error(f"invalid decision {decision!r}; allowed: {', '.join(sorted(VALID_DECISIONS))}")

    classified = bool(dimension.strip() or direction.strip())
    if classified:
        if not (dimension.strip() and direction.strip()):
            return _error("classification needs both dimension and direction")
        problem = _check_classification(book, dimension, direction, normalized_rule)
        if problem:
            return _error(problem)
    elif _category(book) == "memoir":
        return _error(
            "memoir feedback requires a classification (dimension, direction, normalized_rule): "
            "raw text is not stored for memoir books"
        )

    genres = ",".join(str(g) for g in (book.get("genres") or [])) if _category(book) != "memoir" else ""

    conn = open_authors_db()
    try:
        try:
            row_id = insert_feedback(
                conn,
                author_slug=str(book["author"]),
                book_slug=book_slug,
                chapter_slug=chapter_slug,
                source_skill=source_skill,
                decision=decision,
                book_category=_category(book),
                genres=genres,
                comment_text=comment_text,
                before_text=before_text,
                after_text=after_text,
                proposal_text=proposal_text,
                dimension=dimension.strip() if classified else None,
                direction=direction.strip() if classified else None,
                normalized_rule=normalized_rule.strip() if classified else None,
            )
        except ValueError as exc:
            return _error(str(exc))
    finally:
        conn.close()

    if row_id is None:
        return json.dumps({"logged": False, "duplicate": True, "id": None})
    return json.dumps({
        "logged": True,
        "duplicate": False,
        "id": row_id,
        "status": "classified" if classified else "pending",
    })


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
def list_pending_feedback(book_slug: str, chapter_slug: str = "") -> str:
    """List open review feedback of the book's author (Epic #663).

    Includes entries carried over from earlier chapters and books of the same
    author. With ``chapter_slug``, entries of other chapters are flagged
    ``carried_over``.

    Returns ``{count, entries}`` or ``{error: ...}``.
    """
    book, error = _resolve_book(book_slug)
    if error or book is None:
        return _error(error or "book not resolved")
    if chapter_slug and chapter_slug not in (book.get("chapters_data") or {}):
        return _error(f"Chapter '{chapter_slug}' not found in book '{book_slug}'")

    conn = open_authors_db()
    try:
        rows = list_feedback(conn, str(book["author"]))
    finally:
        conn.close()

    entries = [_entry_view(r, chapter_slug) for r in rows]
    return json.dumps({"count": len(entries), "entries": entries})


@mcp.tool(annotations=ToolAnnotations(idempotent_hint=True))
def set_feedback_classification(
    book_slug: str,
    feedback_id: int,
    dimension: str,
    direction: str,
    normalized_rule: str,
) -> str:
    """Store the classification of an open feedback entry (Epic #663).

    The pair is validated against the closed vocabulary in
    ``reference/craft/voice-dimensions.md`` for the entry's book category.
    Only entries of the book's author can be changed; closed entries are not.

    Returns ``{updated}`` or ``{error: ...}``.
    """
    book, error = _resolve_book(book_slug)
    if error or book is None:
        return _error(error or "book not resolved")

    author_slug = str(book["author"])
    conn = open_authors_db()
    try:
        row = get_feedback(conn, feedback_id)
        if row is None or row["author_slug"] != author_slug:
            return json.dumps({"updated": False})

        scoped = {**book, "book_category": row["book_category"]}
        problem = _check_classification(scoped, dimension, direction, normalized_rule)
        if problem:
            return _error(problem)

        updated = set_classification(
            conn, feedback_id,
            dimension=dimension.strip(), direction=direction.strip(),
            normalized_rule=normalized_rule.strip(), author_slug=author_slug,
        )
    finally:
        conn.close()
    return json.dumps({"updated": updated})


def _close(book_slug: str, ids: list[int], status: str) -> str:
    book, error = _resolve_book(book_slug)
    if error or book is None:
        return _error(error or "book not resolved")
    if not isinstance(ids, list) or not ids or not all(
        isinstance(i, int) and not isinstance(i, bool) for i in ids
    ):
        return _error("ids must be a non-empty list of integer feedback ids")

    conn = open_authors_db()
    try:
        changed = mark_feedback(conn, ids, status, author_slug=str(book["author"]))
    finally:
        conn.close()
    return json.dumps({"changed": changed, "status": status})


@mcp.tool(annotations=ToolAnnotations(idempotent_hint=True))
def mark_feedback_harvested(book_slug: str, ids: list[int]) -> str:
    """Close open feedback entries as harvested after they were promoted (Epic #663).

    Only the book author's open entries are changed. Returns ``{changed, status}``.
    """
    return _close(book_slug, ids, "harvested")


@mcp.tool(annotations=ToolAnnotations(idempotent_hint=True))
def discard_feedback(book_slug: str, ids: list[int]) -> str:
    """Close open feedback entries as discarded (not voice evidence or rejected in the walk).

    Only the book author's open entries are changed. Returns ``{changed, status}``.
    """
    return _close(book_slug, ids, "discarded")
