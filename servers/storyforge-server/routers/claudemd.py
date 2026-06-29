"""Per-book CLAUDE.md tools: rules, workflows, callbacks, and character snapshots.

After Phase 4 (#282), structured entries (rules / callbacks / workflows) are
stored in the book_rules SQLite table instead of CLAUDE.md marker blocks.
append_book_rule / append_book_callback / append_book_workflow write to DB;
get_book_claudemd returns prose + DB-rendered sections combined.

``update_character_snapshot`` writes back end-of-chapter POV state (Issues #157 / #160).
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
from tools.db.character_snapshots import upsert_snapshot
from tools.db.connection import get_db_slug_for_book, get_book_num, open_canon_db
from tools.shared.paths import (
    resolve_character_path,
    resolve_people_dir,
    resolve_project_path,
)

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


@mcp.tool(annotations={"readOnlyHint": True})
def get_book_claudemd(book_slug: str) -> str:
    """Read the current CLAUDE.md for a book."""
    config = _app.load_config()
    try:
        content = _get_claudemd_impl(config, book_slug)
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"content": content})


# Snapshot fields written back to the character file at chapter close.
# ``as_of_chapter`` is a string (chapter slug); all others are list[str].
_SNAPSHOT_FIELDS: frozenset[str] = frozenset(
    {
        "current_inventory",
        "current_clothing",
        "current_injuries",
        "altered_states",
        "environmental_limiters",
        "as_of_chapter",
    }
)


@mcp.tool(annotations={"idempotentHint": True})
def update_character_snapshot(
    book_slug: str,
    character_slug: str,
    snapshot_json: str,
    book_category: str = "fiction",
) -> str:
    """Persist end-of-chapter POV character snapshot to SQLite (Issue #281).

    Writes inventory, clothing, injuries, altered_states, environmental_limiters,
    and as_of_chapter to the ``character_snapshots`` table in the per-series DB
    (``~/.storyforge/db/{series-slug}.db``). The character file is NOT modified.

    The character file must still exist — its presence is used as a validity gate
    to confirm the character is real (not a stale slug from a deleted file).

    Args:
        book_slug: Book project slug.
        character_slug: Character / person slug (without extension).
        snapshot_json: JSON object with any subset of:
            ``current_inventory``, ``current_clothing``, ``current_injuries``,
            ``altered_states``, ``environmental_limiters`` (all list[str]);
            ``as_of_chapter`` (str). Unknown keys are rejected.
        book_category: ``"fiction"`` (default) or ``"memoir"``. Controls
            whether the character lives under ``characters/`` or ``people/``.

    Returns:
        ``{success, character, book, updated_fields}`` on success, or
        ``{error}`` on validation / IO failure.
    """
    config = _app.load_config()

    try:
        snapshot: dict[str, Any] = json.loads(snapshot_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"snapshot_json is not valid JSON: {exc}"})
    if not isinstance(snapshot, dict):
        return json.dumps({"error": "snapshot_json must be a JSON object"})
    if not snapshot:
        return json.dumps({"error": "snapshot_json must not be empty"})

    unknown = set(snapshot.keys()) - _SNAPSHOT_FIELDS
    if unknown:
        return json.dumps(
            {
                "error": (
                    f"Unknown snapshot fields: {sorted(unknown)}. "
                    f"Allowed: {sorted(_SNAPSHOT_FIELDS)}"
                )
            }
        )

    list_fields = _SNAPSHOT_FIELDS - {"as_of_chapter"}
    for field in list_fields:
        if field in snapshot:
            val = snapshot[field]
            if not isinstance(val, list) or not all(isinstance(i, str) for i in val):
                return json.dumps({"error": f"Field '{field}' must be a list of strings"})

    if "as_of_chapter" in snapshot and not isinstance(snapshot["as_of_chapter"], str):
        return json.dumps({"error": "Field 'as_of_chapter' must be a string"})

    project_dir = resolve_project_path(config, book_slug)
    if not project_dir.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    if book_category == "memoir":
        char_file = resolve_people_dir(project_dir, "memoir") / f"{character_slug}.md"
    else:
        char_file = resolve_character_path(config, book_slug, character_slug)

    # Validity gate: confirm the character slug refers to a real file even though
    # we no longer write to it. Prevents snapshotting stale/deleted characters.
    if not char_file.exists():
        return json.dumps({"error": f"Character file not found: {char_file}"})

    # Parse chapter number from as_of_chapter (e.g. "26-the-basement" → 26).
    chapter_num = 0
    if "as_of_chapter" in snapshot:
        raw_ch = snapshot["as_of_chapter"]
        try:
            chapter_num = int(str(raw_ch).split("-")[0])
        except (ValueError, IndexError):
            chapter_num = 0

    db_slug = get_db_slug_for_book(project_dir)
    book_num = get_book_num(project_dir)

    conn = open_canon_db(db_slug)
    try:
        upsert_snapshot(
            conn,
            char_slug=character_slug,
            book_num=book_num,
            chapter_num=chapter_num,
            injuries=snapshot.get("current_injuries"),
            clothing=snapshot.get("current_clothing"),
            inventory=snapshot.get("current_inventory"),
            altered_states=snapshot.get("altered_states"),
            environmental_limiters=(
                ", ".join(snapshot["environmental_limiters"])
                if isinstance(snapshot.get("environmental_limiters"), list)
                else snapshot.get("environmental_limiters") or None
            ),
        )
    finally:
        conn.close()

    _app._cache.invalidate()
    return json.dumps(
        {
            "success": True,
            "character": character_slug,
            "book": book_slug,
            "updated_fields": sorted(snapshot.keys()),
        }
    )


@mcp.tool(annotations={"idempotentHint": True})
def append_book_rule(book_slug: str, text: str, validate: bool = True) -> str:
    """Append a rule to the book_rules DB for this book.

    With ``validate=True`` (default) the rule text is linted and any warnings
    are returned. Warnings are advisory — the rule is stored either way.

    Returns ``{rule_id, inserted, kind, text, warnings, extracted_patterns}``.
    """
    config = _app.load_config()
    try:
        result = _append_rule_impl(config, book_slug, text)
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
            "rule_id": result["rule_id"],
            "inserted": result["inserted"],
            "kind": "rule",
            "text": text,
            "warnings": warnings,
            "extracted_patterns": extracted,
        }
    )


@mcp.tool(annotations={"readOnlyHint": True})
def list_book_rules(book_slug: str) -> str:
    """List all rules stored in the book_rules DB for this book.

    Returns one entry per rule with index, rule_id, title, raw_text,
    has_regex, has_literals, and the patterns the manuscript-checker
    scanner would extract from the rule.
    """
    config = _app.load_config()
    try:
        rules = _list_rules_impl(config, book_slug)
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps(
        {
            "rules": [
                {
                    "index": r.index,
                    "rule_id": r.rule_id,
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


@mcp.tool(annotations={"idempotentHint": True})
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


@mcp.tool(annotations={"readOnlyHint": True})
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


@mcp.tool(annotations={"idempotentHint": True})
def append_book_workflow(book_slug: str, text: str) -> str:
    """Append a workflow instruction to the book_rules DB for this book."""
    config = _app.load_config()
    try:
        result = _append_workflow_impl(config, book_slug, text)
    except (FileNotFoundError, ValueError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"rule_id": result["rule_id"], "inserted": result["inserted"], "kind": "workflow", "text": text})


@mcp.tool(annotations={"idempotentHint": True})
def append_book_callback(book_slug: str, text: str) -> str:
    """Append a callback to the book_rules DB for this book."""
    config = _app.load_config()
    try:
        result = _append_callback_impl(config, book_slug, text)
    except (FileNotFoundError, ValueError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"rule_id": result["rule_id"], "inserted": result["inserted"], "kind": "callback", "text": text})


@mcp.tool(annotations={"idempotentHint": True})
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
