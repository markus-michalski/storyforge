"""Book-level read tools: list/find/get_full/get_progress/list_chapters/count_words/get_canon_brief.

These tools are pure-read against the cached state index — no filesystem
mutations happen here. The only exception is ``count_words`` which reads
chapter draft files directly when a chapter slug is supplied.
"""

from __future__ import annotations

import json

from tools.shared.paths import resolve_chapter_path, resolve_project_path
from tools.state.loaders.canon_brief import build_canon_brief
from tools.state.parsers import count_words_in_file, is_chapter_drafted

from . import _app
from ._app import _cache, mcp


@mcp.tool()
def list_books() -> str:
    """List all book projects with status and word count."""
    state = _cache.get()
    books = state.get("books", {})
    if not books:
        return json.dumps({"books": [], "count": 0})

    result = []
    for slug, book in books.items():
        result.append(
            {
                "slug": slug,
                "title": book.get("title", slug),
                "status": book.get("status", "Idea"),
                "genres": book.get("genres", []),
                "author": book.get("author", ""),
                "book_type": book.get("book_type", "novel"),
                "book_category": book.get("book_category", "fiction"),
                "chapter_count": book.get("chapter_count", 0),
                "total_words": book.get("total_words", 0),
            }
        )
    return json.dumps({"books": result, "count": len(result)})


@mcp.tool()
def find_book(query: str) -> str:
    """Find a book by slug or title (partial match)."""
    state = _cache.get()
    query_lower = query.lower()
    matches = []

    for slug, book in state.get("books", {}).items():
        if query_lower in slug or query_lower in book.get("title", "").lower():
            matches.append({"slug": slug, "title": book.get("title", slug)})

    return json.dumps({"matches": matches, "count": len(matches)})


@mcp.tool()
def get_book_full(slug: str) -> str:
    """Get complete book data including all chapters and characters.

    Returns effective_author_writing_mode: book-level override takes precedence
    over the author profile value; falls back to "outliner" if neither is set.
    """
    state = _cache.get()
    book = state.get("books", {}).get(slug)
    if not book:
        return json.dumps({"error": f"Book '{slug}' not found"})

    author_slug = book.get("author", "")
    author = state.get("authors", {}).get(author_slug, {})
    book_override = book.get("author_writing_mode", "")
    effective = book_override or author.get("author_writing_mode", "outliner")
    book = {**book, "effective_author_writing_mode": effective}

    return json.dumps(book)


@mcp.tool()
def get_book_progress(slug: str) -> str:
    """Get book progress: chapter statuses, word counts, completion percentage."""
    state = _cache.get()
    book = state.get("books", {}).get(slug)
    if not book:
        return json.dumps({"error": f"Book '{slug}' not found"})

    chapters = book.get("chapters_data", {})
    total = len(chapters)
    # Issue #19: tolerate non-canonical chapter statuses ("review", etc.) —
    # anything past "Outline" counts as drafted. Final stays strict.
    final = sum(1 for c in chapters.values() if c.get("status") == "Final")
    drafted = sum(1 for c in chapters.values() if is_chapter_drafted(c.get("status", "")))
    total_words = book.get("total_words", 0)
    target = book.get("target_word_count", 0)

    return json.dumps(
        {
            "slug": slug,
            "title": book.get("title", slug),
            # Indexer already derived this from chapter state (Issue #19).
            "status": book.get("status", "Idea"),
            "status_disk": book.get("status_disk", book.get("status", "Idea")),
            "book_category": book.get("book_category", "fiction"),
            "chapters_total": total,
            "chapters_drafted": drafted,
            "chapters_final": final,
            # Issue #19: completion tracks forward progress (drafted), not sign-off (final).
            "completion_percent": round(drafted / total * 100) if total else 0,
            "total_words": total_words,
            "target_words": target,
            "word_progress_percent": round(total_words / target * 100) if target else 0,
            "chapters": {
                slug: {"status": ch.get("status"), "words": ch.get("word_count", 0)} for slug, ch in chapters.items()
            },
        }
    )


@mcp.tool()
def list_chapters(book_slug: str) -> str:
    """List all chapters of a book with status and word count."""
    state = _cache.get()
    book = state.get("books", {}).get(book_slug)
    if not book:
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    chapters = book.get("chapters_data", {})
    result = [
        {
            "slug": slug,
            "number": ch.get("number", 0),
            "title": ch.get("title", slug),
            "status": ch.get("status", "Outline"),
            "words": ch.get("word_count", 0),
        }
        for slug, ch in sorted(chapters.items(), key=lambda x: x[1].get("number", 0))
    ]
    return json.dumps({"chapters": result, "count": len(result)})


@mcp.tool()
def count_words(book_slug: str, chapter_slug: str = "") -> str:
    """Count words in a chapter draft or entire book."""
    config = _app.load_config()

    if chapter_slug:
        draft = resolve_chapter_path(config, book_slug, chapter_slug) / "draft.md"
        words = count_words_in_file(draft)
        return json.dumps({"book": book_slug, "chapter": chapter_slug, "words": words})

    # Count entire book
    state = _cache.get()
    book = state.get("books", {}).get(book_slug)
    if not book:
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    total = book.get("total_words", 0)
    target = book.get("target_word_count", 0)
    chapters = {slug: ch.get("word_count", 0) for slug, ch in book.get("chapters_data", {}).items()}
    return json.dumps(
        {
            "book": book_slug,
            "total_words": total,
            "target_words": target,
            "progress_percent": round(total / target * 100) if target else 0,
            "per_chapter": chapters,
        }
    )


@mcp.tool()
def get_canon_brief(
    book_slug: str,
    chapter_slug: str,
    pov_character: str = "",
    scope_chapters: int = 8,
) -> str:
    """Return a bounded, structured canon-log brief for the chapter being written.

    Projects ``plot/canon-log.md`` (fiction) or ``plot/people-log.md`` (memoir)
    into a scoped payload — only facts from the last ``scope_chapters``
    review-or-later chapters plus all CHANGED entries (which can affect any
    downstream chapter regardless of age).

    Args:
        book_slug: Book project slug.
        chapter_slug: Chapter being written — anchors the scope window.
        pov_character: Display name of the POV character; used to filter
            ``pov_relevant_facts``.  Pass empty string to skip POV filter.
        scope_chapters: How many review-or-later chapters before the current
            one to include in ``current_facts``.  Defaults to 8.

    Returns JSON with:
        current_facts       — facts within the scope window
        changed_facts       — all CHANGED entries regardless of age
        pov_relevant_facts  — subset of current_facts matching pov_character
        scanned_chapters    — chapter numbers included in current_facts
        as_of               — slug of the most-recent scanned chapter
        extraction_method   — "section_regex" | "heuristic" | "none"
        warnings            — issues the skill should surface to the user
    """
    config = _app.load_config()
    book_root = resolve_project_path(config, book_slug)

    state = _cache.get()
    book = state.get("books", {}).get(book_slug, {})
    book_category = book.get("book_category", "fiction")

    brief = build_canon_brief(
        book_root,
        chapter_slug,
        pov_character,
        book_category=book_category,
        scope_chapters=scope_chapters,
    )
    return json.dumps(brief)
