"""Continuity brief assembler — Issue #100.

Bundles canonical_calendar, travel_matrix, canon_log_facts,
character_index, and chapter_timelines into one structured JSON brief.

Chapter draft texts are intentionally NOT included — they are the data
being checked, not project-state metadata (ADR-0001: data-briefs-over-
prompt-instructions).

Design follows ``chapter_writing_brief.py`` (Issue #78).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.analysis.timeline_validator import parse_plot_timeline
from tools.state.chapter_timeline_parser import parse_chapter_timeline_grid
from tools.state.parsers import parse_frontmatter
from tools.state.review_brief import (
    _Recorder,
    _CHAPTER_NUM_RE,
    _parse_canon_log_facts,
    _parse_travel_matrix,
)


# ---------------------------------------------------------------------------
# Character index builder
# ---------------------------------------------------------------------------


def _build_character_index(book_root: Path) -> list[dict[str, str]]:
    """Load all character files and return a flat index.

    Returns a list of dicts with ``slug``, ``name``, ``role``,
    ``description`` keys. INDEX.md is excluded.
    """
    chars_dir = book_root / "characters"
    if not chars_dir.is_dir():
        return []

    index: list[dict[str, str]] = []
    for path in sorted(chars_dir.iterdir()):
        if path.suffix.lower() != ".md" or path.name.upper() == "INDEX.MD":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, _body = parse_frontmatter(text)
        index.append({
            "slug": path.stem,
            "name": str(meta.get("name", path.stem)),
            "role": str(meta.get("role", "supporting")),
            "description": str(meta.get("description", "")),
        })

    return index


# ---------------------------------------------------------------------------
# All-chapter timelines (no review-rank filter — continuity needs all)
# ---------------------------------------------------------------------------


def _get_all_chapter_timelines(book_root: Path) -> list[dict[str, Any]]:
    """Return timeline grids for ALL chapters regardless of status.

    Unlike ``get_recent_chapter_timelines``, this imposes no review-rank
    filter — continuity-checker scans the full manuscript, including
    drafts and outline-stage chapters.
    """
    chapters_dir = book_root / "chapters"
    if not chapters_dir.is_dir():
        return []

    numbered: list[tuple[int, Path]] = []
    for entry in chapters_dir.iterdir():
        if not entry.is_dir():
            continue
        m = _CHAPTER_NUM_RE.match(entry.name)
        if not m:
            continue
        numbered.append((int(m.group(1)), entry))
    numbered.sort(key=lambda pair: pair[0])

    grids: list[dict[str, Any]] = []
    for _, chapter_dir in numbered:
        grid = parse_chapter_timeline_grid(chapter_dir)
        if grid is not None:
            grids.append(grid.to_dict())
    return grids


# ---------------------------------------------------------------------------
# Public assembler
# ---------------------------------------------------------------------------


def build_continuity_brief(
    *,
    book_root: Path,
    book_slug: str,
) -> dict[str, Any]:
    """Assemble the continuity-checker brief — Issue #100.

    Bundles canonical_calendar, travel_matrix, canon_log_facts,
    character_index, and all chapter_timelines into a single
    JSON-serializable dict. ``continuity-checker`` calls this once
    instead of reading timeline/setting/canon/character files by hand.

    Chapter draft texts are intentionally excluded — they are the data
    being checked, not project-state metadata (ADR-0001).

    Args:
        book_root: Absolute path to the book project directory.
        book_slug: Book identifier.

    Returns dict with:
        canonical_calendar  — parsed plot/timeline.md events
        travel_matrix       — parsed world/setting.md Travel Matrix rows
        canon_log_facts     — parsed plot/canon-log.md Established Facts
        character_index     — all character files as flat list
        chapter_timelines   — all chapter timeline grids (any status)
        errors              — component → error map for graceful degrade
    """
    recorder = _Recorder(errors=[])

    # ----- canonical calendar -----------------------------------------------
    canonical_calendar: list[dict[str, Any]] = []
    calendar = recorder.run(
        "canonical_calendar",
        lambda: parse_plot_timeline(book_root),
        None,
    )
    if calendar is not None:
        canonical_calendar = [e.to_dict() for e in calendar.events]

    # ----- travel matrix ----------------------------------------------------
    travel_matrix: list[dict[str, str]] = []
    setting_path = book_root / "world" / "setting.md"
    if setting_path.is_file():
        setting_text = recorder.run(
            "setting.read",
            lambda: setting_path.read_text(encoding="utf-8"),
            "",
        )
        if setting_text:
            travel_matrix = recorder.run(
                "travel_matrix",
                lambda: _parse_travel_matrix(setting_text),
                [],
            )

    # ----- canon log facts --------------------------------------------------
    canon_log_facts: list[dict[str, str]] = []
    canon_path = book_root / "plot" / "canon-log.md"
    if canon_path.is_file():
        canon_text = recorder.run(
            "canon_log.read",
            lambda: canon_path.read_text(encoding="utf-8"),
            "",
        )
        if canon_text:
            canon_log_facts = recorder.run(
                "canon_log_facts",
                lambda: _parse_canon_log_facts(canon_text),
                [],
            )

    # ----- character index --------------------------------------------------
    character_index = recorder.run(
        "character_index",
        lambda: _build_character_index(book_root),
        [],
    )

    # ----- all chapter timelines (no status filter) -------------------------
    chapter_timelines = recorder.run(
        "chapter_timelines",
        lambda: _get_all_chapter_timelines(book_root),
        [],
    )

    return {
        "book_slug": book_slug,
        "canonical_calendar": canonical_calendar,
        "travel_matrix": travel_matrix,
        "canon_log_facts": canon_log_facts,
        "character_index": character_index,
        "chapter_timelines": chapter_timelines,
        "errors": list(recorder.errors),
    }
