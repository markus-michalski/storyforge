"""Read and mutate per-book CLAUDE.md files.

CLAUDE.md lives at ``{book_root}/CLAUDE.md`` and contains workflow rules,
callback register entries, and book facts. Appending to a section is a
deterministic string operation using HTML-comment markers to avoid markdown
parsing.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from tools.claudemd.parser import SECTION_MARKERS, EntryKind
from tools.shared.paths import resolve_project_path

CLAUDE_MD_FILENAME = "CLAUDE.md"
DEFAULT_TEMPLATE_REL = "templates/book-claude-md.template"


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


def get_claudemd(config: dict[str, Any], book_slug: str) -> str:
    """Return the current CLAUDE.md content for a book."""
    path = resolve_claudemd_path(config, book_slug)
    if not path.exists():
        raise FileNotFoundError(f"CLAUDE.md not found for book '{book_slug}': {path}")
    return path.read_text(encoding="utf-8")


def _insert_before_marker(content: str, marker_end: str, new_line: str) -> str:
    """Insert ``new_line`` on its own line before the end-marker.

    Raises ``ValueError`` if the marker is not present.
    """
    if marker_end not in content:
        raise ValueError(f"End marker not found in CLAUDE.md: {marker_end}")

    # Keep a newline before the marker; avoid duplicate blank lines.
    replacement = f"{new_line}\n{marker_end}"
    return content.replace(marker_end, replacement, 1)


def _append_entry(
    config: dict[str, Any],
    book_slug: str,
    kind: EntryKind,
    text: str,
) -> Path:
    """Append a single entry to the appropriate section."""
    text = text.strip()
    if not text:
        raise ValueError("Entry text must not be empty")

    path = resolve_claudemd_path(config, book_slug)
    if not path.exists():
        raise FileNotFoundError(
            f"CLAUDE.md not found for book '{book_slug}'. Call init_claudemd first."
        )

    _, end_marker = SECTION_MARKERS[kind]
    content = path.read_text(encoding="utf-8")

    today = date.today().isoformat()
    bullet = f"- {text} _(added {today})_"

    # Idempotency: same bullet text (ignoring date) already present → skip.
    existing_pattern = re.escape(f"- {text} ")
    if re.search(existing_pattern, content):
        return path

    updated = _insert_before_marker(content, end_marker, bullet)
    path.write_text(updated, encoding="utf-8")
    return path


def append_rule(config: dict[str, Any], book_slug: str, text: str) -> Path:
    """Append a rule entry to CLAUDE.md."""
    return _append_entry(config, book_slug, "rule", text)


def append_workflow(config: dict[str, Any], book_slug: str, text: str) -> Path:
    """Append a workflow entry to CLAUDE.md."""
    return _append_entry(config, book_slug, "workflow", text)


def append_callback(config: dict[str, Any], book_slug: str, text: str) -> Path:
    """Append a callback entry to CLAUDE.md."""
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
