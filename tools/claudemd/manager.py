"""Read and mutate per-book CLAUDE.md files — Issue #282.

After Phase 4, structured entries (rules / callbacks / workflows) live in
SQLite (book_rules table). CLAUDE.md retains only free-prose sections:
Book Facts, Style Suppressions, and Workflow Notes.

get_claudemd() returns a combined view: prose from the file + structured
sections rendered from DB rows.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from tools.claudemd.parser import EntryKind
from tools.db.book_rules import insert_rule, list_rules
from tools.db.connection import get_book_num, get_db_slug_for_book, open_canon_db
from tools.shared.paths import resolve_project_path

CLAUDE_MD_FILENAME = "CLAUDE.md"
DEFAULT_TEMPLATE_REL = "templates/book-claude-md.template"

# Deprecated marker pairs — still parsed by the migration script, no longer
# written by append_rule/callback/workflow after Phase 4.
_DEPRECATED_MARKERS = {
    "rule": ("<!-- RULES:START -->", "<!-- RULES:END -->"),
    "callback": ("<!-- CALLBACKS:START -->", "<!-- CALLBACKS:END -->"),
    "workflow": ("<!-- WORKFLOW:START -->", "<!-- WORKFLOW:END -->"),
}


def resolve_claudemd_path(config: dict[str, Any], book_slug: str) -> Path:
    """Return the absolute path to a book's CLAUDE.md file."""
    return resolve_project_path(config, book_slug) / CLAUDE_MD_FILENAME


def _load_template(plugin_root: Path) -> str:
    template_path = plugin_root / DEFAULT_TEMPLATE_REL
    if not template_path.exists():
        raise FileNotFoundError(f"CLAUDE.md template missing: {template_path}")
    return template_path.read_text(encoding="utf-8")


def _render_template(template: str, facts: dict[str, str]) -> str:
    """Replace ``{{key}}`` placeholders with values from ``facts``.

    Missing keys are replaced with an em-dash so the output stays readable.
    """

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return facts.get(key, "—")

    return re.sub(r"\{\{\s*([a-z_]+)\s*\}\}", replace, template)


def init_claudemd(
    config: dict[str, Any],
    plugin_root: Path,
    book_slug: str,
    facts: dict[str, str] | None = None,
    overwrite: bool = False,
) -> Path:
    """Create ``CLAUDE.md`` for a book from the template.

    Returns the path to the written file. Raises ``FileExistsError`` if the
    file already exists and ``overwrite`` is ``False``.
    """
    target = resolve_claudemd_path(config, book_slug)
    if target.exists() and not overwrite:
        raise FileExistsError(f"CLAUDE.md already exists: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    template = _load_template(plugin_root)
    rendered = _render_template(template, facts or {})
    target.write_text(rendered, encoding="utf-8")
    return target


def _open_book_db(config: dict[str, Any], book_slug: str) -> tuple[sqlite3.Connection, int]:
    """Return (db_connection, book_num) for a book slug."""
    book_root = resolve_project_path(config, book_slug)
    db_slug = get_db_slug_for_book(book_root)
    book_num = get_book_num(book_root)
    return open_canon_db(db_slug), book_num


def _render_rules_section(rules: list[dict]) -> str:
    """Render a list of DB rule rows as a markdown bullet list."""
    if not rules:
        return ""
    return "\n".join(f"- {r['text']}" for r in rules) + "\n"


def get_claudemd(config: dict[str, Any], book_slug: str) -> str:
    """Return the CLAUDE.md content for a book — prose + DB-rendered sections.

    Reads Book Facts / Style Suppressions / Workflow prose from the file.
    Rules, Callbacks, and Workflows are queried from the book_rules DB table
    and injected as formatted markdown sections.
    """
    path = resolve_claudemd_path(config, book_slug)
    if not path.exists():
        raise FileNotFoundError(f"CLAUDE.md not found for book '{book_slug}': {path}")
    prose = path.read_text(encoding="utf-8")

    try:
        conn, book_num = _open_book_db(config, book_slug)
    except Exception:
        return prose

    try:
        db_rules = list_rules(conn, book_num=book_num, rule_type="rule")
        db_callbacks = list_rules(conn, book_num=book_num, rule_type="callback")
        db_workflows = list_rules(conn, book_num=book_num, rule_type="workflow")
    finally:
        conn.close()

    sections: list[str] = []
    if db_rules:
        sections.append("## Rules (from DB)\n\n" + _render_rules_section(db_rules))
    if db_callbacks:
        sections.append("## Callback Register (from DB)\n\n" + _render_rules_section(db_callbacks))
    if db_workflows:
        sections.append("## Workflow Instructions (from DB)\n\n" + _render_rules_section(db_workflows))

    if not sections:
        return prose

    return prose.rstrip() + "\n\n---\n\n" + "\n\n".join(sections)


# Match a ban-cue followed by an optional 0-2-word qualifier and a
# double-quoted phrase. Tuned to recognize the simple shapes that Claude or
# the user typically produces ("Avoid X", "Do not use X", "Limit the X")
# without grabbing every quoted string on the line. Quotes that come later
# in the bullet (typically examples or replacements) are deliberately left
# untouched.
_BAN_CUE_QUOTE_RE = re.compile(
    r"\b(?P<cue>banned|avoid|never|do(?:\s+not|n[‘’]?t)\s+use|"
    r"never\s+use|limit|stop\s+using)"
    r"(?P<between>(?:[\s:]+[\w-]+){0,2}[\s:]+)"
    r'"(?P<phrase>[^"\n]{2,})"',
    re.IGNORECASE,
)


def _normalize_banned_phrase(text: str) -> str:
    """Convert the *first* ban-cued double-quoted phrase to backticks.

    Rules with ban-cue + quoted phrase ("Avoid \"clocked\" as a verb") get
    rewritten to backtick form ("Avoid `clocked` as a verb") so the
    PostToolUse hook (which only honors backticks for hard-block
    patterns) can enforce them. Conservative by design — only the first
    matching phrase per text is converted; later quoted strings (typically
    examples or replacements) stay double-quoted.
    """
    match = _BAN_CUE_QUOTE_RE.search(text)
    if not match:
        return text
    cue = match.group("cue")
    between = match.group("between")
    phrase = match.group("phrase")
    replacement = f"{cue}{between}`{phrase}`"
    return text[: match.start()] + replacement + text[match.end() :]


def _append_entry(
    config: dict[str, Any],
    book_slug: str,
    kind: EntryKind,
    text: str,
) -> dict:
    """Write a single entry to the book_rules DB table.

    Returns {‘rule_id’: int, ‘inserted’: bool}.
    Raises FileNotFoundError if CLAUDE.md doesn’t exist (ensures the book
    was properly initialized before rules are added).
    """
    text = text.strip()
    if not text:
        raise ValueError("Entry text must not be empty")

    if kind == "rule":
        text = _normalize_banned_phrase(text)

    path = resolve_claudemd_path(config, book_slug)
    if not path.exists():
        raise FileNotFoundError(f"CLAUDE.md not found for book ‘{book_slug}’. Call init_claudemd first.")

    conn, book_num = _open_book_db(config, book_slug)
    try:
        return insert_rule(conn, book_num=book_num, rule_type=kind, text=text)
    finally:
        conn.close()


def append_rule(config: dict[str, Any], book_slug: str, text: str) -> dict:
    """Append a rule entry to the book_rules DB."""
    return _append_entry(config, book_slug, "rule", text)


def append_workflow(config: dict[str, Any], book_slug: str, text: str) -> dict:
    """Append a workflow entry to the book_rules DB."""
    return _append_entry(config, book_slug, "workflow", text)


def append_callback(config: dict[str, Any], book_slug: str, text: str) -> dict:
    """Append a callback entry to the book_rules DB."""
    return _append_entry(config, book_slug, "callback", text)


# Matches "- **Key:** value" lines in the Book Facts section.
_FACT_LINE_RE = re.compile(
    r"^(?P<prefix>- \*\*(?P<label>[^*:]+):\*\*\s*).*$",
    re.MULTILINE,
)

_FACT_LABEL_MAP = {
    "pov": "POV",
    "tense": "Tense",
    "genre": "Genre",
    "writing_mode": "Writing Mode",
}


def update_book_facts(
    config: dict[str, Any],
    book_slug: str,
    facts: dict[str, str],
) -> Path:
    """Update one or more Book Facts fields in CLAUDE.md.

    ``facts`` maps internal keys (e.g. ``"current_chapter"``) to new values.
    Keys not present in the label map are ignored.
    """
    path = resolve_claudemd_path(config, book_slug)
    if not path.exists():
        raise FileNotFoundError(f"CLAUDE.md not found for book '{book_slug}'")

    content = path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        label = match.group("label").strip()
        # Find which key maps to this label (reverse lookup).
        for key, mapped_label in _FACT_LABEL_MAP.items():
            if mapped_label == label and key in facts:
                return f"{match.group('prefix')}{facts[key]}"
        return match.group(0)

    updated = _FACT_LINE_RE.sub(replace, content)
    path.write_text(updated, encoding="utf-8")
    return path
