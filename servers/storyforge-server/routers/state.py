"""System-state tools: session, rebuild, generic field update, path resolution.

This module also owns ``get_book_category_dir`` (path lookup for category
knowledge bundles) since it's a thin filesystem-state helper.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.shared.paths import resolve_project_path, resolve_world_dir
from tools.state.indexer import rebuild
from tools.state.parsers import parse_frontmatter

from . import _app
from ._app import _cache, mcp

# Path E (#54): allowed book_category values for get_book_category_dir.
# Phase 1 only ships fiction + memoir. Other non-fiction subtypes
# (biography, how-to, academic, history) are deferred per #49 / #97.
_ALLOWED_BOOK_CATEGORIES = ("fiction", "memoir")


@mcp.tool()
def get_session() -> str:
    """Get current session context."""
    state = _cache.get()
    return json.dumps(state.get("session", {}))


@mcp.tool()
def update_session(
    last_book: str = "",
    last_chapter: str = "",
    last_phase: str = "",
    active_author: str = "",
) -> str:
    """Update session context with current work info."""
    state = _cache.get()
    session = state.get("session", {})

    if last_book:
        session["last_book"] = last_book
    if last_chapter:
        session["last_chapter"] = last_chapter
    if last_phase:
        session["last_phase"] = last_phase
    if active_author:
        session["active_author"] = active_author

    state["session"] = session
    from tools.state.indexer import _write_state

    _write_state(state)
    _cache.invalidate()

    return json.dumps({"success": True, "session": session})


@mcp.tool()
def get_review_handle_config() -> str:
    """Return the configured review comment handle from config.

    Used by chapter-writer to replace the hardcoded author name in
    inline review comment blocks (e.g. 'Author: this feels off').
    Configurable via defaults.review_handle in ~/.storyforge/config.yaml.
    """
    config = _app.load_config()
    handle = _app.get_review_handle(config)
    return json.dumps({"review_handle": handle})


@mcp.tool()
def rebuild_state() -> str:
    """Force rebuild of the state cache from filesystem.

    Also runs the Issue #25 auto-sync: any book whose derived status
    (from chapter aggregates) is a forward move from its on-disk README
    frontmatter gets its README updated in place. Floor rule — never
    downgrades a user-set higher tier. Sync events are returned in the
    ``synced`` list so the user can see what changed.
    """
    state = rebuild(preserve_session=True)
    _cache.invalidate()
    books_count = len(state.get("books", {}))
    authors_count = len(state.get("authors", {}))
    synced = state.get("sync_log", [])
    msg = f"Rebuilt state: {books_count} books, {authors_count} authors"
    if synced:
        msg += f"; synced {len(synced)} book status(es) to disk"
    return json.dumps(
        {
            "success": True,
            "books": books_count,
            "authors": authors_count,
            "synced": synced,
            "message": msg,
        }
    )


@mcp.tool()
def update_field(file_path: str, field: str, value: str) -> str:
    """Update a field in a markdown frontmatter block or a plain YAML file.

    For ``.yaml``/``.yml`` files (e.g. ``chapter.yaml``) the file is treated
    as pure YAML — no frontmatter delimiters are written. For all other files
    the standard ``---`` frontmatter format is used.
    """
    # Audit H1 (#115): file_path must resolve under content_root or
    # authors_root. Without containment a poisoned prompt could rewrite any
    # existing user file (~/.bashrc, ~/.ssh/authorized_keys, dotfiles in
    # ~/.claude/...) as YAML.
    config = _app.load_config()
    allowed_roots = [
        Path(config["paths"]["content_root"]).resolve(),
        Path(config["paths"]["authors_root"]).resolve(),
    ]
    try:
        resolved = Path(file_path).resolve()
    except (OSError, RuntimeError) as exc:
        return json.dumps({"error": f"Invalid file_path: {exc}"})

    if not any(resolved.is_relative_to(root) for root in allowed_roots):
        return json.dumps({"error": (f"file_path must be within content_root or authors_root (got: {file_path})")})

    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    import yaml

    if path.suffix in (".yaml", ".yml"):
        # Pure YAML file — chapter.yaml and similar; never use frontmatter markers.
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            meta = loaded if isinstance(loaded, dict) else {}
        except yaml.YAMLError:
            meta = {}
        meta[field] = value
        path.write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True), encoding="utf-8")
    else:
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        meta[field] = value
        new_text = "---\n" + yaml.dump(meta, default_flow_style=False, allow_unicode=True) + "---\n" + body
        path.write_text(new_text, encoding="utf-8")

    _cache.invalidate()
    return json.dumps({"success": True, "file": file_path, "field": field, "value": value})


@mcp.tool()
def resolve_path(book_slug: str, component: str = "", sub_path: str = "") -> str:
    """Resolve filesystem path for a book component.

    Args:
        book_slug: Book project slug
        component: Component type (chapters, characters, plot, world, cover, export, research)
        sub_path: Optional sub-path within the component

    Note: ``world`` resolves to the first existing of ``world/``,
    ``worldbuilding/``, or ``world-building/`` (Issue #17). When no world dir
    exists, the canonical ``world/`` path is returned with ``exists: false``.
    """
    config = _app.load_config()
    project = resolve_project_path(config, book_slug)

    if component == "world":
        world_dir = resolve_world_dir(project)
        base = world_dir if world_dir is not None else project / "world"
    elif component:
        base = project / component
    else:
        base = project

    if sub_path:
        base = base / sub_path

    # Audit H2 (#116): defense-in-depth — even with a validated book_slug,
    # `component` and `sub_path` flow into the join unsanitized. Reject any
    # final path that escapes content_root.
    content_root = Path(config["paths"]["content_root"]).resolve()
    try:
        resolved = base.resolve()
    except (OSError, RuntimeError) as exc:
        return json.dumps({"error": f"Invalid path components: {exc}"})

    if not resolved.is_relative_to(content_root):
        return json.dumps(
            {"error": (f"Resolved path escapes content_root (component='{component}', sub_path='{sub_path}')")}
        )

    return json.dumps({"path": str(base), "exists": base.exists()})


@mcp.tool()
def get_book_category_dir(category: str) -> str:
    """Resolve the plugin-relative path to a book category's knowledge dir.

    Path E (#55): skills loading category-specific knowledge (memoir craft
    docs, status models) call this to get the canonical directory under
    ``{plugin_root}/book_categories/{category}/``.

    Args:
        category: One of the allowed book categories (fiction, memoir).

    Returns JSON with ``category``, ``path``, and ``exists`` (bool).
    """
    if category not in _ALLOWED_BOOK_CATEGORIES:
        allowed = ", ".join(_ALLOWED_BOOK_CATEGORIES)
        return json.dumps({"error": (f"Unknown book_category '{category}'. Allowed: {allowed}.")})

    base = _app.get_book_categories_dir() / category
    return json.dumps(
        {
            "category": category,
            "path": str(base),
            "exists": base.exists(),
        }
    )
