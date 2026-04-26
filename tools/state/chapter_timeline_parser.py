"""Chapter Timeline grid parser — Issue #77.

Loads the per-chapter ``## Chapter Timeline`` section as a structured
intra-day grid (start/end TimePoints + scene rows). The MCP tool
``get_recent_chapter_timelines`` surfaces the last N review-or-later
chapters as JSON so ``chapter-writer`` can anchor against three real
grids instead of remembered times — the cross-chapter cascade-drift
fix from beta-feedback.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tools.state.parsers import (
    _chapter_rank,
    parse_chapter_readme,
)
from tools.timeline_anchor import TimePoint, parse_chapter_timeline


# ---------------------------------------------------------------------------
# Scene parser
# ---------------------------------------------------------------------------

# Matches scene heading lines:
#   ### Szene 1 — Christmas Eve (~14:45 → ~15:50)
#   ### Scene 2 — The Library (~15:50 → ~16:00)
# The dash between scene number and name is em-dash, en-dash, or hyphen.
# Times are HH:MM with optional ~ prefix; separator is → or -> or --.
_SCENE_HEADER_RE = re.compile(
    r"^###\s+(?:Szene|Scene)\s+\d+\s*[—–\-]\s*"
    r"(?P<name>.+?)\s*"
    r"\(\s*~?(?P<start>\d{1,2}:\d{2})\s*"
    r"(?:→|->|-->|—>|–>)\s*"
    r"~?(?P<end>\d{1,2}:\d{2})\s*\)\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class ChapterScene:
    """One intra-day scene with start/end clock times.

    Times are ``HH:MM`` strings (no date) — scenes within a chapter
    typically all share the same story-day, with the calendar date
    living on the parent ``ChapterTimelineGrid``.
    """

    name: str
    start_time: str | None = None
    end_time: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_scenes(readme_text: str) -> list[ChapterScene]:
    """Extract scene rows from a chapter README body.

    Recognizes ``### Szene N — Name (~HH:MM → ~HH:MM)`` and the English
    variant ``### Scene N — ...``. Headers that lack the time-range
    parenthetical are silently skipped — the caller gets an empty list
    rather than partial data, since malformed scenes provide no
    anchor value to the writer.
    """
    scenes: list[ChapterScene] = []
    for match in _SCENE_HEADER_RE.finditer(readme_text):
        scenes.append(
            ChapterScene(
                name=match.group("name").strip(),
                start_time=match.group("start"),
                end_time=match.group("end"),
            )
        )
    return scenes


# ---------------------------------------------------------------------------
# Chapter timeline grid (single chapter)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChapterTimelineGrid:
    """Per-chapter intra-day timeline grid.

    Combines chapter metadata (number, slug, title, status) with the
    parsed Chapter Timeline section (start/end anchor + scene list).
    Returned as JSON by the ``get_recent_chapter_timelines`` MCP tool.
    """

    number: int
    slug: str
    title: str
    status: str
    start: TimePoint | None
    end: TimePoint | None
    scenes: list[ChapterScene]

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "slug": self.slug,
            "title": self.title,
            "status": self.status,
            "start": self.start.to_dict() if self.start else None,
            "end": self.end.to_dict() if self.end else None,
            "scenes": [s.to_dict() for s in self.scenes],
        }


def parse_chapter_timeline_grid(
    chapter_dir: Path,
) -> ChapterTimelineGrid | None:
    """Load a single chapter's timeline grid, or ``None`` if README missing.

    Graceful with malformed input: a chapter that has metadata but no
    parseable Chapter Timeline section yields a grid with ``None``
    anchors and an empty scene list — useful for the ``chapter-writer``
    brief, which can show "this chapter exists but had no timeline".
    """
    readme = chapter_dir / "README.md"
    if not readme.is_file():
        return None
    try:
        text = readme.read_text(encoding="utf-8")
    except OSError:
        return None

    meta = parse_chapter_readme(readme)
    start, end = parse_chapter_timeline(text)
    scenes = parse_scenes(text)

    return ChapterTimelineGrid(
        number=int(meta.get("number") or 0),
        slug=meta.get("slug", chapter_dir.name),
        title=meta.get("title", chapter_dir.name),
        status=meta.get("status", "Outline"),
        start=start,
        end=end,
        scenes=scenes,
    )


# ---------------------------------------------------------------------------
# Book-level orchestrator
# ---------------------------------------------------------------------------


# Matches "01-something", "22-the-night-before". Mirrors the convention
# used in ``timeline_anchor`` so chapter ordering stays consistent.
_CHAPTER_DIR_RE = re.compile(r"^(?P<num>\d{1,3})-")


# "Review-status or later" per Issue #77 acceptance criteria. The
# parsers module ranks ``review``/``reviewed``/``revision`` at 2,
# ``polished``/``polishing`` at 3, ``final``/``done`` at 4. Anything
# under 2 (drafts, outlines) is filtered out.
_REVIEW_RANK_THRESHOLD = 2


def _list_chapter_dirs(book_root: Path) -> list[tuple[int, Path]]:
    chapters_dir = book_root / "chapters"
    if not chapters_dir.is_dir():
        return []
    out: list[tuple[int, Path]] = []
    for entry in chapters_dir.iterdir():
        if not entry.is_dir():
            continue
        match = _CHAPTER_DIR_RE.match(entry.name)
        if not match:
            continue
        out.append((int(match.group("num")), entry))
    out.sort(key=lambda pair: pair[0])
    return out


def get_recent_chapter_timelines(
    book_root: Path,
    n: int = 3,
) -> list[ChapterTimelineGrid]:
    """Return the last ``n`` review-or-later chapters in chronological order.

    Filters out drafts and outlines so the writer only sees stable,
    locked-in time grids. Fewer than ``n`` results are returned without
    padding when the book has fewer eligible chapters; empty list when
    the chapters directory is missing or contains no eligible chapters.
    """
    chapters = _list_chapter_dirs(book_root)
    eligible: list[ChapterTimelineGrid] = []
    for _, chapter_dir in chapters:
        grid = parse_chapter_timeline_grid(chapter_dir)
        if grid is None:
            continue
        if _chapter_rank(grid.status) < _REVIEW_RANK_THRESHOLD:
            continue
        eligible.append(grid)

    # Most-recent N in chronological order (oldest first within the slice).
    return eligible[-n:] if n > 0 else []
