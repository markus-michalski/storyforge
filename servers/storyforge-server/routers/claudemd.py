"""Per-book CLAUDE.md tools + ``get_character`` (which reads the character
profile that the CLAUDE.md context references).

The CLAUDE.md tools wrap ``tools.claudemd.manager`` — they're the only
state-mutating MCP entry points that touch the per-book CLAUDE.md.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from tools.claudemd.manager import (
    append_callback as _append_callback_impl,
    append_rule as _append_rule_impl,
    append_workflow as _append_workflow_impl,
    get_claudemd as _get_claudemd_impl,
    init_claudemd as _init_claudemd_impl,
    update_book_facts as _update_book_facts_impl,
)
from tools.claudemd.parser import extract_prefixed_lines as _extract_prefixed_lines
from tools.shared.paths import resolve_character_path, resolve_project_path

from . import _app
from ._app import mcp


def _plugin_root() -> Path:
    """Resolve plugin root from env override, falling back to filesystem layout."""
    return Path(
        os.environ.get(
            "CLAUDE_PLUGIN_ROOT",
            # routers/_app.py is at servers/storyforge-server/routers/_app.py;
            # plugin root is four levels up.
            str(Path(__file__).resolve().parent.parent.parent.parent),
        )
    )


@mcp.tool()
def init_book_claudemd(
    book_slug: str,
    book_title: str = "",
    pov: str = "",
    tense: str = "",
    genre: str = "",
    writing_mode: str = "scene-by-scene",
    overwrite: bool = False,
) -> str:
    """Create CLAUDE.md from template in the book project root.

    Called by new-book after scaffolding a project. Populates the Book Facts
    section from the given metadata. Use overwrite=True to regenerate.

    Ephemeral state (current chapter, next beat) is NOT stored here — it
    belongs in the session cache (``update_session``) because it changes
    after every chapter.
    """
    config = _app.load_config()
    facts = {
        "book_title": book_title or book_slug,
        "pov": pov,
        "tense": tense,
        "genre": genre,
        "writing_mode": writing_mode,
    }
    try:
        path = _init_claudemd_impl(config, _plugin_root(), book_slug, facts=facts, overwrite=overwrite)
    except FileExistsError as exc:
        return json.dumps({"error": str(exc)})
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"path": str(path), "created": True})


@mcp.tool()
def get_book_claudemd(book_slug: str) -> str:
    """Read the current CLAUDE.md for a book."""
    config = _app.load_config()
    try:
        content = _get_claudemd_impl(config, book_slug)
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"content": content})


@mcp.tool()
def get_character(book_slug: str, character_slug: str) -> str:
    """Read the full character file for a book.

    Args:
        book_slug: Book slug (exact match)
        character_slug: Character slug without extension
    """
    config = _app.load_config()
    project_path = resolve_project_path(config, book_slug)
    if not project_path.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    # Primary layout: characters/{slug}.md
    primary = resolve_character_path(config, book_slug, character_slug)
    if primary.exists():
        return json.dumps({"content": primary.read_text(encoding="utf-8")})

    # Legacy layout: characters/{slug}/README.md
    legacy = project_path / "characters" / character_slug / "README.md"
    if legacy.exists():
        return json.dumps({"content": legacy.read_text(encoding="utf-8")})

    return json.dumps({"error": f"Character '{character_slug}' not found in book '{book_slug}'"})


@mcp.tool()
def append_book_rule(book_slug: str, text: str) -> str:
    """Append a rule to the Rules section of a book's CLAUDE.md."""
    config = _app.load_config()
    try:
        path = _append_rule_impl(config, book_slug, text)
    except (FileNotFoundError, ValueError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"path": str(path), "kind": "rule", "text": text})


@mcp.tool()
def append_book_workflow(book_slug: str, text: str) -> str:
    """Append a workflow instruction to a book's CLAUDE.md."""
    config = _app.load_config()
    try:
        path = _append_workflow_impl(config, book_slug, text)
    except (FileNotFoundError, ValueError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"path": str(path), "kind": "workflow", "text": text})


@mcp.tool()
def append_book_callback(book_slug: str, text: str) -> str:
    """Append a callback to the Callback Register of a book's CLAUDE.md."""
    config = _app.load_config()
    try:
        path = _append_callback_impl(config, book_slug, text)
    except (FileNotFoundError, ValueError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"path": str(path), "kind": "callback", "text": text})


@mcp.tool()
def update_book_claudemd_facts(
    book_slug: str,
    pov: str = "",
    tense: str = "",
    genre: str = "",
    writing_mode: str = "",
) -> str:
    """Update one or more Book Facts fields in a book's CLAUDE.md.

    Empty strings are ignored (field left unchanged). Only stable facts
    live in CLAUDE.md; per-chapter progress belongs in the session cache.
    """
    config = _app.load_config()
    provided = {
        "pov": pov,
        "tense": tense,
        "genre": genre,
        "writing_mode": writing_mode,
    }
    facts = {k: v for k, v in provided.items() if v}
    if not facts:
        return json.dumps({"error": "No fields provided"})
    try:
        path = _update_book_facts_impl(config, book_slug, facts)
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"path": str(path), "updated": list(facts.keys())})


@mcp.tool()
def sync_book_claudemd_from_text(book_slug: str, text: str) -> str:
    """Extract prefixed entries (Regel:/Workflow:/Callback:) and persist them.

    Used by the PreCompact hook: pass a text blob (e.g. recent session
    messages) and all matching lines are appended to the appropriate
    sections. Returns counts per kind.
    """
    config = _app.load_config()
    entries = _extract_prefixed_lines(text)
    counts = {"rule": 0, "workflow": 0, "callback": 0, "errors": 0}
    errors: list[str] = []

    impl_map = {
        "rule": _append_rule_impl,
        "workflow": _append_workflow_impl,
        "callback": _append_callback_impl,
    }

    for kind, body in entries:
        try:
            impl_map[kind](config, book_slug, body)
            counts[kind] += 1
        except (FileNotFoundError, ValueError) as exc:
            counts["errors"] += 1
            errors.append(f"{kind}: {exc}")

    result: dict[str, Any] = {"counts": counts}
    if errors:
        result["errors"] = errors
    return json.dumps(result)
