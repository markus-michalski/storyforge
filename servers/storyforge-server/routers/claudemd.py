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
from tools.claudemd.rules_editor import (
    AmbiguousMatchError,
    DisagreeingResolutionError,
    MarkersNotFoundError,
    list_rules as _list_rules_impl,
    update_rule as _update_rule_impl,
)
from tools.claudemd.rules_lint import (
    lint_book_rules as _lint_book_rules_impl,
    lint_rule_text as _lint_rule_text_impl,
)
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
def append_book_rule(book_slug: str, text: str, validate: bool = True) -> str:
    """Append a rule to the Rules section of a book's CLAUDE.md.

    With ``validate=True`` (default) the rule text is run through the
    same lint as ``update_book_rule`` and any warnings are returned in
    the response. Warnings are advisory — the rule is appended either way.

    Returns ``{path, kind, text, warnings, extracted_patterns}``.
    """
    config = _app.load_config()
    try:
        path = _append_rule_impl(config, book_slug, text)
    except (FileNotFoundError, ValueError) as exc:
        return json.dumps({"error": str(exc)})

    if validate:
        lint = _lint_rule_text_impl(text)
        warnings = lint["warnings"]
        extracted = lint["extracted_patterns"]
    else:
        warnings = []
        extracted = []

    return json.dumps(
        {
            "path": str(path),
            "kind": "rule",
            "text": text,
            "warnings": warnings,
            "extracted_patterns": extracted,
        }
    )


@mcp.tool()
def list_book_rules(book_slug: str) -> str:
    """List all managed rules in the book's CLAUDE.md RULES block.

    Returns one entry per bullet inside ``<!-- RULES:START -->`` /
    ``<!-- RULES:END -->`` with index, title, raw_text, has_regex,
    has_literals, and the patterns the manuscript-checker scanner
    would extract from the rule.

    Static rules above the marker block are intentionally not listed —
    they're template boilerplate, not user-managed entries.
    """
    config = _app.load_config()
    try:
        rules = _list_rules_impl(config, book_slug)
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    except MarkersNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps(
        {
            "rules": [
                {
                    "index": r.index,
                    "title": r.title,
                    "raw_text": r.raw_text,
                    "has_regex": r.has_regex,
                    "has_literals": r.has_literals,
                    "extracted_patterns": r.extracted_patterns,
                }
                for r in rules
            ]
        }
    )


@mcp.tool()
def update_book_rule(
    book_slug: str,
    rule_index: int = -1,
    rule_match: str = "",
    new_text: str = "",
    delete: bool = False,
    validate: bool = True,
) -> str:
    """Replace or remove a rule in the book's CLAUDE.md RULES block.

    Resolution: ``rule_match`` is matched first against bold titles
    (``**Title**``), then against rule body substrings — case-insensitive.
    ``rule_index`` is the unambiguous fallback. When both are given they
    must agree on the same rule.

    Args:
        book_slug: Book slug.
        rule_index: 0-based index in the RULES block. ``-1`` = unset.
        rule_match: Substring to match against rule title or body. Empty
            string = unset.
        new_text: Replacement text for the rule body (without leading
            ``- ``). Required unless ``delete=True``.
        delete: If True, remove the matched rule. Mutually exclusive
            with ``new_text``.
        validate: If True, lint the new rule against the
            manuscript-checker pattern contract and return warnings.

    Returns: ``{found, changed, rule_index, old_text, new_text,
    warnings, extracted_patterns}``. ``found=False`` means the rule did
    not exist (file unchanged). ``changed=False`` means the new text
    matched the existing text (idempotent no-op).
    """
    config = _app.load_config()
    resolved_index = rule_index if rule_index >= 0 else None
    resolved_match = rule_match.strip() or None
    resolved_new_text = new_text if new_text else None
    try:
        result = _update_rule_impl(
            config,
            book_slug,
            rule_index=resolved_index,
            rule_match=resolved_match,
            new_text=resolved_new_text,
            delete=delete,
            validate=validate,
        )
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    except MarkersNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    except AmbiguousMatchError as exc:
        return json.dumps({"error": str(exc), "code": "ambiguous_match"})
    except DisagreeingResolutionError as exc:
        return json.dumps({"error": str(exc), "code": "disagreeing_resolution"})
    except ValueError as exc:
        return json.dumps({"error": str(exc), "code": "invalid_args"})
    return json.dumps(result)


@mcp.tool()
def lint_book_rules(book_slug: str) -> str:
    """Audit every rule in the book's RULES block against the
    manuscript-checker pattern contract.

    Surfaces rules the scanner will silently ignore or misinterpret
    (italic-wrapped examples with ban cues, mixed positive/negative
    quotes, dead patterns, character-class typos in backtick bodies).

    Returns ``{rules_total, issues: [{rule_index, title, warnings,
    extracted_patterns}, ...]}``. Rules with no warnings are not listed.
    """
    config = _app.load_config()
    try:
        result = _lint_book_rules_impl(config, book_slug)
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    except MarkersNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps(result)


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
