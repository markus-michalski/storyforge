"""Canon-facts MCP tools — Issue #280.

add_canon_fact(): persist a structured fact to the series/book SQLite DB
instead of manually editing canon-log.md.
"""

from __future__ import annotations

import json

import tools.db.connection as _db_conn
from tools.db.canon_facts import insert_fact
from tools.shared.paths import resolve_project_path

from . import _app
from ._app import mcp


@mcp.tool(annotations={"idempotentHint": True})
def add_canon_fact(
    book_slug: str,
    chapter_num: int,
    subject: str,
    fact: str,
    book_num: int = 1,
    domain: str = "",
    is_revision: bool = False,
    old_value: str = "",
    revision_impacts: list[str] | None = None,
) -> str:
    """Persist a structured canon fact to the series SQLite DB.

    Replaces manual editing of canon-log.md for new facts discovered
    or confirmed during writing. Facts are served to the chapter-writer
    via get_chapter_writing_brief(), which queries the DB first and
    merges results with any legacy Markdown archive (Issue #291).

    Facts are stored per-series (or per-book for standalone books).
    Duplicate (book_num, chapter_num, subject, fact) tuples are silently
    ignored — calling this twice with the same data is safe.

    Args:
        book_slug: Book identifier (used to resolve the correct DB).
        chapter_num: Chapter number where this fact was established.
        subject: Short subject label (character name, place, concept).
        fact: The fact statement itself.
        book_num: Book number within the series (default 1).
        domain: Optional domain tag (e.g. "Character Facts", "World").
        is_revision: True if this fact supersedes an older fact.
        old_value: The superseded fact text (required if is_revision=True).
        revision_impacts: Chapter slugs affected by this revision.
    """
    config = _app.load_config()
    book_root = resolve_project_path(config, book_slug)

    if not book_root.is_dir():
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    db_slug = _db_conn.get_db_slug_for_book(book_root)
    conn = _db_conn.open_canon_db(db_slug)

    try:
        insert_fact(
            conn,
            book_num=book_num,
            chapter_num=chapter_num,
            subject=subject,
            fact=fact,
            domain=domain,
            is_revision=is_revision,
            old_value=old_value or None,
            revision_impacts=json.dumps(revision_impacts) if revision_impacts else None,
        )
    finally:
        conn.close()

    return json.dumps({
        "success": True,
        "book_slug": book_slug,
        "db": db_slug,
        "book_num": book_num,
        "chapter_num": chapter_num,
        "subject": subject,
        "fact": fact,
    })
