"""Chapter metadata loader (Issue #121).

Resolves a chapter README into a flat metadata dict, honoring two
encodings:

- YAML frontmatter — the canonical source.
- ``## Overview`` markdown table — the legacy Blood & Binary layout.
  Used as a fallback for fields that are missing from the frontmatter.

Also serializes the metadata into a JSON-safe shape for the brief.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.state.parsers import parse_chapter_readme, parse_frontmatter

# Fallback parser for Blood & Binary-style Overview tables. Older
# chapter READMEs encode metadata in a markdown table under
# ``## Overview`` instead of YAML frontmatter. Honor both.
_OVERVIEW_CELL_RE = re.compile(
    r"^\|\s*(?P<key>[A-Za-z][A-Za-z ]+?)\s*\|\s*(?P<value>[^|]+?)\s*\|\s*$",
    re.MULTILINE,
)


def parse_overview_table(readme_text: str) -> dict[str, str]:
    """Pull key/value pairs from a chapter README's ``## Overview`` table.

    Returns an empty dict when the table is absent. Header rows (the
    ``Field/Value`` and the dashes line) are filtered out by the
    caller's key whitelist.
    """
    cells: dict[str, str] = {}
    for match in _OVERVIEW_CELL_RE.finditer(readme_text):
        key = match.group("key").strip().lower()
        value = match.group("value").strip()
        if not value or value.startswith("-"):
            continue
        cells[key] = value
    return cells


def load_chapter_meta(chapter_readme: Path, chapter_slug: str) -> tuple[dict[str, Any], str, dict[str, str]]:
    """Load chapter frontmatter + overview-table fallback.

    Returns ``(meta, pov_character, overview)`` where:

    - ``meta`` is the merged metadata dict
    - ``pov_character`` is the resolved POV (may be ``""`` if neither
      source declares one)
    - ``overview`` is the raw overview-table dict for callers that need
      to inspect specific cells beyond the merged meta
    """
    meta: dict[str, Any] = {}
    overview: dict[str, str] = {}

    if chapter_readme.is_file():
        meta = parse_chapter_readme(chapter_readme)
        try:
            overview = parse_overview_table(chapter_readme.read_text(encoding="utf-8"))
        except OSError:
            overview = {}

    pov_character = str(meta.get("pov_character", "")).strip()
    title_from_meta = str(meta.get("title", "")).strip()
    title_is_default = title_from_meta == chapter_slug

    if not pov_character:
        pov_character = overview.get("pov", "").strip()
    if (not title_from_meta or title_is_default) and overview.get("title"):
        meta["title"] = overview["title"]
    if not meta.get("number") and overview.get("chapter"):
        try:
            meta["number"] = int(re.sub(r"\D", "", overview["chapter"]) or 0)
        except ValueError:
            pass

    return meta, pov_character, overview


def serialize_chapter_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """Trim chapter meta to JSON-safe keys."""
    if not meta:
        return {}
    out: dict[str, Any] = {}
    for key in (
        "slug",
        "title",
        "number",
        "status",
        "pov_character",
        "summary",
        "word_count_target",
    ):
        if key in meta:
            value = meta[key]
            if isinstance(value, (str, int, float, bool)) or value is None:
                out[key] = value
            else:
                out[key] = str(value)
    return out


def load_book_category(book_root: Path) -> str:
    """Read the book's ``book_category`` from its README frontmatter.

    Defaults to ``fiction`` for legacy books pre-#54 that don't carry
    the field.
    """
    book_readme = book_root / "README.md"
    if not book_readme.is_file():
        return "fiction"
    try:
        text = book_readme.read_text(encoding="utf-8")
    except OSError:
        return "fiction"
    if not text:
        return "fiction"
    book_meta, _ = parse_frontmatter(text)
    return str(book_meta.get("book_category", "fiction"))


__all__ = [
    "load_book_category",
    "load_chapter_meta",
    "parse_overview_table",
    "serialize_chapter_meta",
]
