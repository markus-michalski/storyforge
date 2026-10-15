"""Review-feedback MCP tools — Epic #663 / Issue #665.

Thin layer over ``tools/db/review_feedback.py``: it resolves author, genres
and book category from the book itself, validates classifications against the
closed vocabulary in ``reference/craft/voice-dimensions.md`` and keeps real
names out of memoir rows. Promotion into the author profile is not done here;
it keeps going through ``write_author_discovery``.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from mcp.types import ToolAnnotations

from tools.analysis.voice_candidates import build_voice_candidates
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

from tools.shared.config import get_review_handle
from tools.shared.paths import catch_slug_value_error, resolve_project_path
from tools.shared.person_names import person_name_hit
from tools.state import draft_snapshots

from . import _app
from ._app import mcp

MAX_RULE_LENGTH = 240
MAX_TEXT_LENGTH = 8000

def _error(message: str) -> str:
    return json.dumps({"error": message})


def _db_error(exc: sqlite3.Error) -> str:
    return _error(f"Review feedback database error: {exc}. Try again; nothing was changed.")


def _first_non_str(**params: Any) -> str | None:
    for name, value in params.items():
        if not isinstance(value, str):
            return name
    return None


def _is_int_id(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _resolve_book(book_slug: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return ``(book, error_message)`` from the state cache, with a stripped author."""
    if not isinstance(book_slug, str) or not book_slug.strip():
        return None, "book_slug must be a non-empty string"
    book = (_app._cache.get().get("books") or {}).get(book_slug)
    if not book:
        return None, f"Book '{book_slug}' not found"
    author = str(book.get("author") or "").strip()
    if not author:
        return None, (
            f"Book '{book_slug}' has no author in its README; set `author` so feedback "
            f"can be attributed to an author profile"
        )
    return {**book, "author": author}, None


def _category(book: dict[str, Any]) -> str:
    return str(book.get("book_category") or "fiction")


def _check_rule(rule_text: str, *, memoir: bool, people: dict[str, Any]) -> str | None:
    rule = rule_text.strip()
    if not rule:
        return "normalized_rule must state the rule in one plain sentence"
    if len(rule) > MAX_RULE_LENGTH or "\n" in rule or "\r" in rule:
        return f"normalized_rule must be a single line of at most {MAX_RULE_LENGTH} characters"
    if memoir:
        hit = person_name_hit(rule, people)
        if hit:
            return (
                f"normalized_rule must not contain the name of a person from this memoir "
                f"(matched {hit!r}); state the rule without names or facts"
            )
    return None


def _check_classification(
    category: str, dimension: str, direction: str, rule: str,
    *, memoir: bool, people: dict[str, Any],
) -> str | None:
    try:
        validate_classification(dimension, direction, category)
    except VoiceDimensionError as exc:
        return str(exc)
    return _check_rule(rule, memoir=memoir, people=people)


def _entry_view(row: dict[str, Any], book_slug: str, chapter_slug: str) -> dict[str, Any]:
    keys = (
        "id", "book_slug", "chapter_slug", "source_skill", "decision", "comment_text",
        "before_text", "after_text", "proposal_text", "dimension", "direction",
        "normalized_rule", "status", "genres", "book_category", "created_at",
    )
    view = {k: row[k] for k in keys}
    view["carried_over"] = bool(chapter_slug) and (
        row["chapter_slug"] != chapter_slug or row["book_slug"] != book_slug
    )
    return view


@mcp.tool(annotations=ToolAnnotations(idempotent_hint=True, destructive_hint=False))
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
    bad = _first_non_str(
        chapter_slug=chapter_slug, source_skill=source_skill, decision=decision,
        comment_text=comment_text, before_text=before_text, after_text=after_text,
        proposal_text=proposal_text, dimension=dimension, direction=direction,
        normalized_rule=normalized_rule,
    )
    if bad:
        return _error(f"{bad} must be a string")

    book, error = _resolve_book(book_slug)
    if error or book is None:
        return _error(error or "book not resolved")

    category = _category(book)
    if category == "fiction" and book.get("people"):
        return _error(
            f"Book '{book_slug}' has people profiles but book_category is 'fiction'; set "
            f"`book_category: memoir` in its README so raw text is not stored"
        )

    chapters = book.get("chapters_data") or {}
    if chapter_slug not in chapters:
        return _error(
            f"Chapter '{chapter_slug}' not found in book '{book_slug}'; "
            f"known chapters: {', '.join(sorted(chapters)) or 'none'}"
        )
    if source_skill not in VALID_SOURCES:
        return _error(f"invalid source_skill {source_skill!r}; allowed: {', '.join(sorted(VALID_SOURCES))}")
    if decision not in VALID_DECISIONS:
        return _error(f"invalid decision {decision!r}; allowed: {', '.join(sorted(VALID_DECISIONS))}")

    for name, value in (("comment_text", comment_text), ("before_text", before_text),
                        ("after_text", after_text), ("proposal_text", proposal_text)):
        if len(value) > MAX_TEXT_LENGTH:
            return _error(f"{name} is too long ({len(value)} characters, maximum {MAX_TEXT_LENGTH})")

    classified = bool(dimension.strip() or direction.strip())
    if classified:
        if not (dimension.strip() and direction.strip()):
            return _error("classification needs both dimension and direction")
        problem = _check_classification(
            category, dimension, direction, normalized_rule,
            memoir=category == "memoir", people=book.get("people") or {},
        )
        if problem:
            return _error(problem)
    elif category == "memoir":
        return _error(
            "memoir feedback requires a classification (dimension, direction, normalized_rule): "
            "raw text is not stored for memoir books"
        )

    raw_genres = book.get("genres") or []
    if isinstance(raw_genres, str):
        raw_genres = [raw_genres]
    genres = "" if category == "memoir" else ",".join(str(g).strip() for g in raw_genres)

    try:
        conn = open_authors_db()
        try:
            row_id = insert_feedback(
                conn,
                author_slug=book["author"],
                book_slug=book_slug,
                chapter_slug=chapter_slug,
                source_skill=source_skill,
                decision=decision,
                book_category=category,
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
    except sqlite3.Error as exc:
        return _db_error(exc)

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
    if not isinstance(chapter_slug, str):
        return _error("chapter_slug must be a string")
    book, error = _resolve_book(book_slug)
    if error or book is None:
        return _error(error or "book not resolved")
    if chapter_slug and chapter_slug not in (book.get("chapters_data") or {}):
        return _error(f"Chapter '{chapter_slug}' not found in book '{book_slug}'")

    try:
        conn = open_authors_db()
        try:
            rows = list_feedback(conn, book["author"])
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return _db_error(exc)

    entries = [_entry_view(r, book_slug, chapter_slug) for r in rows]
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
    ``reference/craft/voice-dimensions.md`` for the entry's book category, and
    the rule is checked against the people of the entry's own book (not the
    book passed here). Only entries of the book's author can be changed;
    closed entries are not.

    Returns ``{updated}`` or ``{error: ...}``.
    """
    bad = _first_non_str(dimension=dimension, direction=direction, normalized_rule=normalized_rule)
    if bad:
        return _error(f"{bad} must be a string")
    if not _is_int_id(feedback_id):
        return _error("feedback_id must be an integer")

    book, error = _resolve_book(book_slug)
    if error or book is None:
        return _error(error or "book not resolved")

    author_slug = book["author"]
    try:
        conn = open_authors_db()
        try:
            row = get_feedback(conn, feedback_id)
            if row is None or row["author_slug"] != author_slug:
                return json.dumps({"updated": False})

            row_category = str(row["book_category"])
            own_book = (_app._cache.get().get("books") or {}).get(row["book_slug"])
            if own_book is None and row_category == "memoir":
                return _error(
                    f"The memoir book '{row['book_slug']}' of this entry is no longer indexed, "
                    f"so the rule cannot be checked for names; restore the book first"
                )
            people = (own_book or {}).get("people") or {}
            memoir = row_category == "memoir" or _category(own_book or {}) == "memoir"

            problem = _check_classification(
                row_category, dimension, direction, normalized_rule,
                memoir=memoir, people=people,
            )
            if problem:
                return _error(problem)

            updated = set_classification(
                conn, feedback_id,
                dimension=dimension.strip(), direction=direction.strip(),
                normalized_rule=normalized_rule.strip(), author_slug=author_slug,
            )
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return _db_error(exc)
    return json.dumps({"updated": updated})


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
def get_voice_candidates(author_slug: str, book_slug: str = "") -> str:
    """Promotion candidates for an author's voice, mined from review feedback (Epic #663).

    Only classified entries count. A candidate needs a weighted evidence sum of 3
    from at least two chapters; its scope is the intersection of the genres of
    all evidence (empty intersection = universal). Opposite directions in
    overlapping scope are returned as ``conflicts`` instead of candidates, and a
    discarded candidate only returns once its open evidence has caught up.

    With ``book_slug`` the book must belong to the author; only candidates of
    that book's category (fiction or memoir) are returned.

    Returns ``{author_slug, candidates, conflicts, suppressed, unclassified,
    skipped_unknown}`` or ``{error: ...}``.
    """
    bad = _first_non_str(author_slug=author_slug, book_slug=book_slug)
    if bad:
        return _error(f"{bad} must be a string")
    if not author_slug.strip():
        return _error("author_slug must be a non-empty string")
    author = author_slug.strip()

    category = ""
    if book_slug:
        book, error = _resolve_book(book_slug)
        if error or book is None:
            return _error(error or "book not resolved")
        if book["author"] != author:
            return _error(f"Book '{book_slug}' belongs to author '{book['author']}', not '{author}'")
        category = _category(book)

    try:
        conn = open_authors_db()
        try:
            rows = list_feedback(
                conn, author, statuses=("pending", "classified", "harvested", "discarded"),
            )
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return _db_error(exc)

    if category:
        rows = [r for r in rows if r["book_category"] == category]
    try:
        result = build_voice_candidates(rows)
    except VoiceDimensionError as exc:
        return _error(f"Voice vocabulary unavailable: {exc}")
    return json.dumps({"author_slug": author, **result})


def _close(book_slug: str, ids: list[int], status: str) -> str:
    book, error = _resolve_book(book_slug)
    if error or book is None:
        return _error(error or "book not resolved")
    if not isinstance(ids, list) or not ids or not all(_is_int_id(i) for i in ids):
        return _error("ids must be a non-empty list of integer feedback ids")

    try:
        conn = open_authors_db()
        try:
            changed = mark_feedback(conn, ids, status, author_slug=book["author"])
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return _db_error(exc)
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


def _draft_path(book_slug: str, chapter_slug: str) -> tuple[Path | None, str | None]:
    config = _app.load_config()
    draft = resolve_project_path(config, book_slug) / "chapters" / chapter_slug / "draft.md"
    if not draft.is_file():
        return None, f"No draft.md for chapter '{chapter_slug}' of '{book_slug}'"
    return draft, None


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
@catch_slug_value_error
def get_self_edit_hunks(book_slug: str, chapter_slug: str, offset: int = 0) -> str:
    """Differences between a chapter draft and the text Claude last wrote (Epic #663, phase 2).

    Call it when the author says they edited the text themselves. A baseline is
    kept for every fiction chapter by a PostToolUse hook; the comparison runs
    only on request. Changes of up to three words, whitespace/punctuation-only
    changes and the author's own review-comment blocks are left out. Memoir
    books are not supported.

    At most 20 hunks are returned per call; page with ``offset`` until
    ``truncated`` is false. A hunk with ``clipped: true`` is partial.

    Baselines are per machine: text changed by Claude on another machine, by a
    shell command or by git shows up as the author's edit. Show the hunks to the
    author before logging them.

    Returns ``{status, hunks, total, offset, ignored_small, truncated}`` with
    ``status`` ``ok``, ``no_baseline``, ``stale`` or ``memoir_unsupported``, or
    ``{error}``.
    """
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        return _error("offset must be a non-negative integer")
    book, error = _resolve_book(book_slug)
    if error or book is None:
        return _error(error or "book not resolved")
    if not isinstance(chapter_slug, str) or chapter_slug not in (book.get("chapters_data") or {}):
        return _error(f"Chapter '{chapter_slug}' not found in book '{book_slug}'")
    if not draft_snapshots.is_fiction_category(book.get("book_category")):
        return json.dumps({
            "status": "memoir_unsupported",
            "message": "Manual-edit capture is not available for memoir books.",
        })

    draft, error = _draft_path(book_slug, chapter_slug)
    if error or draft is None:
        return _error(error or "draft not found")
    if draft_snapshots.is_stale(book_slug, chapter_slug):
        return json.dumps({
            "status": "stale",
            "message": "The baseline could not be kept in step with an edit. Call "
                       "refresh_draft_baseline to start from the current draft; earlier "
                       "manual edits of this chapter cannot be attributed.",
        })
    baseline = draft_snapshots.read_snapshot(book_slug, chapter_slug)
    if baseline is None:
        return json.dumps({
            "status": "no_baseline",
            "message": "No baseline exists for this chapter yet. Call refresh_draft_baseline "
                       "to record the current draft; later manual edits can then be compared.",
        })

    handle = get_review_handle(_app.load_config())
    result = draft_snapshots.compute_hunks(
        baseline, draft.read_text(encoding="utf-8"), review_handle=handle, offset=offset,
    )
    return json.dumps({"status": "ok", **result})


@mcp.tool(annotations=ToolAnnotations(idempotent_hint=True))
@catch_slug_value_error
def refresh_draft_baseline(book_slug: str, chapter_slug: str) -> str:
    """Record the current chapter draft as the new baseline (Epic #663, phase 2).

    Call it after the author's manual edits were logged (or deliberately
    dismissed) so they are not reported again, and to recover from a stale or
    missing baseline. Memoir books are not supported.

    Returns ``{refreshed}`` or ``{status: "memoir_unsupported"}`` or ``{error}``.
    """
    book, error = _resolve_book(book_slug)
    if error or book is None:
        return _error(error or "book not resolved")
    if not isinstance(chapter_slug, str) or chapter_slug not in (book.get("chapters_data") or {}):
        return _error(f"Chapter '{chapter_slug}' not found in book '{book_slug}'")
    if not draft_snapshots.is_fiction_category(book.get("book_category")):
        draft_snapshots.remove_book_snapshots(book_slug)
        return json.dumps({
            "status": "memoir_unsupported",
            "message": "Manual-edit capture is not available for memoir books.",
        })

    draft, error = _draft_path(book_slug, chapter_slug)
    if error or draft is None:
        return _error(error or "draft not found")
    text = draft.read_text(encoding="utf-8")
    draft_snapshots.write_snapshot(book_slug, chapter_slug, text)
    return json.dumps({"refreshed": True, "characters": len(text)})
