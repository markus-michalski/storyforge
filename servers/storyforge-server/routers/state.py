"""System-state tools: session, rebuild, generic field update, path resolution.

This module also owns ``get_book_category_dir`` (path lookup for category
knowledge bundles) since it's a thin filesystem-state helper.
"""

from __future__ import annotations
from mcp.types import ToolAnnotations

import json
import re
from pathlib import Path

from tools.db.connection import open_session_db
from tools.db.sessions import get_session_from_db, update_session_in_db
from tools.shared.paths import resolve_project_path, resolve_world_dir
from tools.state.indexer import rebuild
from tools.state.parsers import parse_frontmatter

from . import _app
from ._app import _cache, mcp

_SESSION_USER_ID = "local"

# Path E (#54): allowed book_category values for get_book_category_dir.
# Phase 1 only ships fiction + memoir. Other non-fiction subtypes
# (biography, how-to, academic, history) are deferred per #49 / #97.
_ALLOWED_BOOK_CATEGORIES = ("fiction", "memoir")

# Field-name format guard for update_field(). Accepts the same identifiers
# that appear throughout the YAML frontmatter schema: letters, digits,
# underscores, hyphens; must start with a letter; max 64 chars.
# Rejects null bytes, shell metacharacters, path separators, and injected
# YAML structure characters.
_FIELD_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")

# Isolates a frontmatter block into its three parts (opening ---, raw body,
# closing ---) so a single field's line can be patched without touching the
# rest. Same delimiters as tools.state.parsers._RE_FRONTMATTER, but the body
# group here keeps its trailing newline (needed for line-based splicing) —
# the two patterns are not literally identical, only delimiter-compatible.
_RE_FRONTMATTER_SPLIT = re.compile(r"^(---\s*\n)(.*?\n)(---\s*\n)", re.DOTALL)


def _yaml_inline_scalar(value: str) -> str:
    """Render `value` exactly as ``yaml.dump`` would inline it in a mapping.

    Reuses PyYAML's own quoting rules (only quote when needed to disambiguate
    from int/bool/date/etc.) so a single patched line stays indistinguishable
    from what a full re-serialize of the same value would have produced. Note:
    a `value` containing "\\n" renders as a multi-line quoted scalar — valid
    YAML, but it means the "one line changes" guarantee only holds for
    single-line values, which covers every real caller in this codebase.
    """
    import yaml

    dumped = yaml.safe_dump(value, allow_unicode=True).rstrip("\n")
    if dumped.endswith("..."):
        dumped = dumped[: -len("...")].rstrip("\n")
    return dumped


_RE_BLOCK_SEQUENCE_ITEM = re.compile(r"^-(\s|$)")


def _patch_frontmatter_line(fm_body: str, field: str, value: str) -> str | None:
    """Try a surgical single-line patch of `field` inside frontmatter raw text.

    Returns the patched block, or None if `field`'s line looks like it opens
    a block scalar or a nested mapping/sequence — the caller should fall back
    to a full re-serialize in that case. This codebase's frontmatter schemas
    (book/chapter/character/person/author) are all flat scalars plus one
    flow-style list (`genres`), so the None branch is a safety net, not the
    common path.
    """
    lines = fm_body.split("\n")
    key_re = re.compile(rf"^{re.escape(field)}:(\s.*)?$")
    new_line = f"{field}: {_yaml_inline_scalar(value)}"

    patched: str | None = None
    for i, line in enumerate(lines):
        if not key_re.match(line):
            continue
        rest = line.split(":", 1)[1].strip()
        if rest[:1] in ("|", ">"):
            return None  # block scalar — needs full YAML handling
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        # Nested mapping/sequence continues on the next line — either
        # indented (standard nesting) or, for a block sequence, at the same
        # (zero) indent as the key itself (e.g. `genres:\n- drama`), which
        # is exactly the shape the full-reserialize fallback below emits.
        if (next_line[:1] in (" ", "\t") and next_line.strip()) or _RE_BLOCK_SEQUENCE_ITEM.match(next_line):
            return None
        new_lines = list(lines)
        new_lines[i] = new_line
        patched = "\n".join(new_lines)
        break
    else:
        # Field not present yet — append before the trailing blank entry
        # that split() leaves from the block's final newline.
        new_lines = list(lines)
        if new_lines and new_lines[-1] == "":
            new_lines.insert(-1, new_line)
        else:
            new_lines.append(new_line)
        patched = "\n".join(new_lines)

    # Safety net: confirm the patch is still valid YAML and left every other
    # key's value unchanged. Catches any line-shape the heuristics above
    # didn't anticipate instead of silently corrupting the file.
    import yaml

    try:
        before = yaml.safe_load(fm_body) or {}
        after = yaml.safe_load(patched) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(after, dict):
        return None
    if any(k != field and after.get(k) != v for k, v in before.items()):
        return None
    return patched


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def get_session() -> str:
    """Get current session context from DB (Issue #280)."""
    conn = open_session_db()
    try:
        session = get_session_from_db(conn, _SESSION_USER_ID)
    finally:
        conn.close()
    return json.dumps(session)


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
def update_session(
    last_book: str | None = None,
    last_chapter: str | None = None,
    last_phase: str | None = None,
    active_author: str | None = None,
) -> str:
    """Update session context in DB (Issue #280).

    Omit a field (or pass None) to leave it unchanged. Pass an explicit ""
    to clear it — e.g. active_author="" resets the session's active author.
    """
    conn = open_session_db()
    try:
        update_session_in_db(
            conn,
            _SESSION_USER_ID,
            last_book=last_book,
            last_chapter=last_chapter,
            last_phase=last_phase,
            active_author=active_author,
        )
        session = get_session_from_db(conn, _SESSION_USER_ID)
    finally:
        conn.close()

    return json.dumps({"success": True, "session": session})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def get_review_handle_config() -> str:
    """Return the configured review comment handle from config.

    Used by chapter-writer to replace the hardcoded author name in
    inline review comment blocks (e.g. 'Author: this feels off').
    Configurable via defaults.review_handle in ~/.storyforge/config.yaml.
    """
    config = _app.load_config()
    handle = _app.get_review_handle(config)
    return json.dumps({"review_handle": handle})


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
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


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
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

    if not _FIELD_NAME_RE.match(field):
        return json.dumps({"error": f"Invalid field name '{field}': must match [a-zA-Z][a-zA-Z0-9_-]{{0,63}}"})

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
        fm_match = _RE_FRONTMATTER_SPLIT.match(text)
        patched_block = _patch_frontmatter_line(fm_match.group(2), field, value) if fm_match else None
        if fm_match and patched_block is not None:
            # Surgical patch (Issue #372): only the touched field's line
            # changes — key order, quote style, and flow/block style of every
            # other field stay exactly as they were on disk.
            new_text = fm_match.group(1) + patched_block + fm_match.group(3) + text[fm_match.end() :]
        else:
            # Fallback: no frontmatter block yet, or the field's existing
            # line is a block scalar / nested structure a single-line patch
            # can't safely touch. sort_keys=False at least keeps key
            # insertion order stable across this re-serialize.
            meta, body = parse_frontmatter(text)
            meta[field] = value
            new_text = "---\n" + yaml.dump(meta, default_flow_style=False, sort_keys=False, allow_unicode=True) + "---\n" + body
        path.write_text(new_text, encoding="utf-8")

    _cache.invalidate()
    return json.dumps({"success": True, "file": file_path, "field": field, "value": value})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
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


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
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
