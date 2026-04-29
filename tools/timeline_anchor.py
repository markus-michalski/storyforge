"""Story-time anchor for the active chapter.

Parses the per-chapter ``## Chapter Timeline`` section in a chapter
README and returns a structured anchor (start/end day-of-week, month,
day, time). The anchor lets the PostToolUse hook warn when prose uses
relative time phrases (``yesterday``, ``this morning``, ``tomorrow``,
etc.) so the writer can verify the implied date against
``plot/timeline.md``.

The MCP server surfaces the anchor via ``get_current_story_anchor`` so
``chapter-writer`` can consume it as structured data instead of doing
date math itself (the source of #72's beta-feedback bug).

Pure stdlib so the hook can call it without extra setup.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Calendar primitives
# ---------------------------------------------------------------------------

DAY_NAMES_SHORT: tuple[str, ...] = (
    "Mon",
    "Tue",
    "Wed",
    "Thu",
    "Fri",
    "Sat",
    "Sun",
)
DAY_NAMES_FULL: tuple[str, ...] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
MONTH_NAMES_SHORT: tuple[str, ...] = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

_DAY_FULL_BY_SHORT = dict(zip(DAY_NAMES_SHORT, DAY_NAMES_FULL))
_MONTH_INDEX = {name: idx + 1 for idx, name in enumerate(MONTH_NAMES_SHORT)}

# Fallback year for the rare case where no real year produces the
# point's stated day-of-week (corrupt input). Otherwise we auto-detect a
# matching year so date arithmetic preserves the README's calendar.
_FALLBACK_YEAR = 2025


# ---------------------------------------------------------------------------
# TimePoint dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimePoint:
    """A single moment on the story calendar."""

    day_of_week: str  # short name: "Tue"
    month: str  # short name: "Dec"
    day: int  # 24
    time: str | None = None  # "19:30" or None when not specified

    def label(self) -> str:
        """Human-readable label like 'Tue Dec 24 ~19:30'."""
        base = f"{self.day_of_week} {self.month} {self.day}"
        if self.time:
            return f"{base} ~{self.time}"
        return base

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChapterAnchor:
    """Story-time anchor for a single chapter."""

    chapter_slug: str
    start: TimePoint | None = None
    end: TimePoint | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_slug": self.chapter_slug,
            "start": self.start.to_dict() if self.start else None,
            "end": self.end.to_dict() if self.end else None,
        }


# ---------------------------------------------------------------------------
# Chapter Timeline parser
# ---------------------------------------------------------------------------

# Matches:
#   **Start:** Tue Dec 24 ~19:30 (library window seat, ...)
#   **End:** Wed Dec 25 ~07:00 (trailhead, ...)
# Time is optional; the leading "~" is consumed as part of the time prefix.
_TIMELINE_LINE_RE = re.compile(
    r"^\*\*(?P<label>Start|End):\*\*\s+"
    r"(?P<dow>Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    r"(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"(?P<day>\d{1,2})"
    r"(?:\s+~?(?P<time>\d{1,2}:\d{2}))?",
    re.MULTILINE,
)


def parse_chapter_timeline(
    readme_text: str,
) -> tuple[TimePoint | None, TimePoint | None]:
    """Return ``(start, end)`` TimePoints from a chapter README, or
    ``(None, None)`` if no Chapter Timeline section is present.

    Tolerant of extra whitespace and case-variants — the regex anchors
    on the bold ``**Start:**`` / ``**End:**`` markers that the
    chapter-writer skill writes when a chapter reaches review status.
    """
    start: TimePoint | None = None
    end: TimePoint | None = None
    for match in _TIMELINE_LINE_RE.finditer(readme_text):
        point = TimePoint(
            day_of_week=match.group("dow"),
            month=match.group("mon"),
            day=int(match.group("day")),
            time=match.group("time"),
        )
        if match.group("label") == "Start":
            start = point
        else:
            end = point
    return start, end


def get_chapter_anchor(chapter_dir: Path) -> ChapterAnchor | None:
    """Load the anchor for a single chapter directory.

    Returns ``None`` when the README is missing or has no parseable
    Chapter Timeline section.
    """
    readme = chapter_dir / "README.md"
    if not readme.is_file():
        return None
    try:
        text = readme.read_text(encoding="utf-8")
    except OSError:
        return None
    start, end = parse_chapter_timeline(text)
    if start is None and end is None:
        return None
    return ChapterAnchor(
        chapter_slug=chapter_dir.name,
        start=start,
        end=end,
    )


# ---------------------------------------------------------------------------
# Day-shift arithmetic
# ---------------------------------------------------------------------------


def _matching_year(point: TimePoint) -> int:
    """Find a real year where ``point.month`` ``point.day`` falls on
    ``point.day_of_week``. Required so calendar arithmetic preserves
    the README-stated day-of-week across shifts.
    """
    month = _MONTH_INDEX.get(point.month)
    if month is None:
        return _FALLBACK_YEAR
    target = None
    try:
        target = DAY_NAMES_SHORT.index(point.day_of_week)
    except ValueError:
        return _FALLBACK_YEAR
    for year in range(2020, 2040):
        try:
            candidate = datetime(year, month, point.day)
        except ValueError:
            continue
        if candidate.weekday() == target:
            return year
    return _FALLBACK_YEAR


def _to_datetime(point: TimePoint) -> datetime | None:
    """Map a TimePoint into a real datetime using a year that preserves
    its stated day-of-week.

    Returns ``None`` if the month/day combination is invalid
    (e.g. Feb 30) or month is unknown.
    """
    month = _MONTH_INDEX.get(point.month)
    if month is None:
        return None
    hour = 0
    minute = 0
    if point.time and ":" in point.time:
        try:
            hour_str, minute_str = point.time.split(":", 1)
            hour = int(hour_str)
            minute = int(minute_str)
        except ValueError:
            pass
    year = _matching_year(point)
    try:
        return datetime(year, month, point.day, hour, minute)
    except ValueError:
        return None


def _from_datetime(dt: datetime, time: str | None) -> TimePoint:
    return TimePoint(
        day_of_week=DAY_NAMES_SHORT[dt.weekday()],
        month=MONTH_NAMES_SHORT[dt.month - 1],
        day=dt.day,
        time=time,
    )


def shift_days(point: TimePoint, delta_days: int) -> TimePoint | None:
    """Shift a TimePoint by ``delta_days``. Returns None on invalid math."""
    base = _to_datetime(point)
    if base is None:
        return None
    shifted = base + timedelta(days=delta_days)
    return _from_datetime(shifted, point.time)


def shift_hours(point: TimePoint, delta_hours: int) -> TimePoint | None:
    """Shift a TimePoint by ``delta_hours`` (preserves time-of-day)."""
    base = _to_datetime(point)
    if base is None:
        return None
    shifted = base + timedelta(hours=delta_hours)
    new_time = f"{shifted.hour:02d}:{shifted.minute:02d}"
    return _from_datetime(shifted, new_time)


# ---------------------------------------------------------------------------
# Relative phrase mapping
# ---------------------------------------------------------------------------


def compute_relative_phrase_mapping(
    anchor: ChapterAnchor,
) -> dict[str, str]:
    """Map common relative time phrases to their implied story-calendar
    target, given the chapter's start point.

    Used by the hook to surface "phrase X implies date Y — verify against
    timeline" warnings.
    """
    mapping: dict[str, str] = {}
    if anchor.start is None:
        return mapping
    start = anchor.start

    yesterday = shift_days(start, -1)
    if yesterday is not None:
        mapping["yesterday"] = yesterday.label()

    tomorrow = shift_days(start, 1)
    if tomorrow is not None:
        mapping["tomorrow"] = tomorrow.label()

    last_week = shift_days(start, -7)
    if last_week is not None:
        mapping["last week"] = f"week of {last_week.label()}"

    next_week = shift_days(start, 7)
    if next_week is not None:
        mapping["next week"] = f"week of {next_week.label()}"

    today_label = f"{start.day_of_week} {start.month} {start.day}"
    mapping["this morning"] = f"morning of {today_label}"
    mapping["this afternoon"] = f"afternoon of {today_label}"
    mapping["this evening"] = f"evening of {today_label}"
    mapping["tonight"] = f"night of {today_label}"

    # "last night" = the night previous to today, not 12h ago.
    if yesterday is not None:
        prev_label = f"{yesterday.day_of_week} {yesterday.month} {yesterday.day}"
        mapping["last night"] = f"night of {prev_label}"

    one_hour = shift_hours(start, -1)
    if one_hour is not None:
        mapping["an hour ago"] = one_hour.label()
        mapping["one hour ago"] = one_hour.label()

    two_hours = shift_hours(start, -2)
    if two_hours is not None:
        mapping["two hours ago"] = two_hours.label()

    return mapping


# ---------------------------------------------------------------------------
# Multi-chapter anchor (used by the MCP tool)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StoryAnchor:
    """Anchor that combines current chapter + previous chapter context."""

    current: ChapterAnchor | None
    previous: ChapterAnchor | None
    relative_phrase_mapping: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        current_dict = self.current.to_dict() if self.current else None
        previous_dict = self.previous.to_dict() if self.previous else None
        return {
            "current_chapter": current_dict,
            "previous_chapter": previous_dict,
            "available_relative_phrases": self.relative_phrase_mapping,
        }


# Matches "01-something", "22-the-night-before", etc. The leading number
# is the chapter index used for ordering.
_CHAPTER_DIR_RE = re.compile(r"^(?P<num>\d{1,3})-")


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


def _previous_chapter_dir(book_root: Path, current_slug: str) -> Path | None:
    chapters = _list_chapter_dirs(book_root)
    prev: Path | None = None
    for _, chapter_dir in chapters:
        if chapter_dir.name == current_slug:
            return prev
        prev = chapter_dir
    return None


def get_story_anchor(book_root: Path, current_chapter_slug: str) -> StoryAnchor:
    """Load current + previous chapter anchors and compute the relative
    phrase mapping.

    Returns a ``StoryAnchor`` even when one or both chapters lack a
    Chapter Timeline section — the relative-phrase mapping is then
    derived from whichever anchor is available (current, then previous).
    """
    chapters_dir = book_root / "chapters"
    current_dir = chapters_dir / current_chapter_slug
    current = get_chapter_anchor(current_dir) if current_dir.is_dir() else None

    prev_dir = _previous_chapter_dir(book_root, current_chapter_slug)
    previous = get_chapter_anchor(prev_dir) if prev_dir is not None else None

    # Pick whichever anchor we can use as the "now" for the mapping.
    base_anchor = current
    if base_anchor is None or base_anchor.start is None:
        # Fall back to the previous chapter's end as the current "now".
        if previous is not None and previous.end is not None:
            base_anchor = ChapterAnchor(
                chapter_slug=current_chapter_slug,
                start=previous.end,
                end=None,
            )

    mapping: dict[str, str] = {}
    if base_anchor is not None:
        mapping = compute_relative_phrase_mapping(base_anchor)

    return StoryAnchor(
        current=current,
        previous=previous,
        relative_phrase_mapping=mapping,
    )
