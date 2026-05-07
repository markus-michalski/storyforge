"""Series-tracker loaders (Issue #194).

Bridges the gap between book-level character files
(``projects/{book}/characters/{slug}.md``) and series-level evolution
trackers (``series/{series}/characters/{tracker-slug}.md``).

The series-planner skill may pick role/title-prefixed slugs at series
scope when a character is recurringly addressed by title across the
trilogy (e.g. ``king-caelan`` for "King Caelan", whose book-level file
is just ``caelan.md``). The tracker schema therefore supports an
optional ``book_slug:`` frontmatter field that declares the explicit
mapping. When absent, the tracker slug IS the book-level slug — no
breakage for the common case where they match.

The future series-evolution tooling (harvest, bootstrap, brief-source —
see Issue #195) consumes this resolver.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.state.parsers import parse_frontmatter


def parse_series_tracker(path: Path) -> dict[str, Any]:
    """Parse a series-character-tracker frontmatter into a dict.

    Returns at minimum: ``slug``, ``name``, ``role``, ``species``,
    ``status``, ``recurs_in``, ``tracker_type``, ``book_slug``.
    The ``book_slug`` value is ``None`` when the field is absent.
    ``slug`` falls back to the path stem so downstream callers always
    have a non-empty value.
    """
    text = path.read_text(encoding="utf-8")
    meta, _body = parse_frontmatter(text)

    return {
        "slug": str(meta.get("slug") or path.stem),
        "name": str(meta.get("name", path.stem)),
        "role": str(meta.get("role", "supporting")),
        "species": str(meta.get("species", "")),
        "status": str(meta.get("status", "Profile")),
        "recurs_in": list(meta.get("recurs_in") or []),
        "tracker_type": str(meta.get("tracker_type", "thin")),
        "book_slug": meta.get("book_slug"),
    }


def resolve_book_slug_for_series_tracker(tracker: dict[str, Any]) -> str:
    """Return the book-level slug for a series tracker.

    Priority: explicit ``book_slug`` field (when truthy) > tracker
    ``slug`` as-is. Returns an empty string when neither is set so
    callers can branch without exception handling.
    """
    book_slug = tracker.get("book_slug")
    if book_slug:
        return str(book_slug)
    return str(tracker.get("slug") or "")


def find_series_trackers(series_dir: Path) -> list[Path]:
    """Return all series-character-tracker files for a series.

    Looks under ``{series_dir}/characters/`` and returns every ``*.md``
    sorted by path, excluding ``INDEX.md``. Returns an empty list when
    the directory does not exist.
    """
    chars_dir = series_dir / "characters"
    if not chars_dir.exists():
        return []
    return sorted(p for p in chars_dir.glob("*.md") if p.name != "INDEX.md")
