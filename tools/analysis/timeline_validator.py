"""Timeline drift validator — Issue #79.

Cross-references the per-chapter ``## Chapter Timeline`` anchor (in
each chapter's README) and relative-time phrases in draft prose
(``yesterday``, ``last week``, ``tomorrow``, ...) against the canonical
``plot/timeline.md`` Event Calendar. When the implied story-date of a
phrase diverges from the calendar event for the same chapter, the
validator emits a finding so the writer can investigate cascade drift.

The module is consumed by:
- ``/storyforge:continuity-checker`` skill via the orchestrator
- a future PostToolUse hook for inline drift warnings

Public entry points:
- ``validate_timeline(book_path)`` — full orchestrator
- ``parse_plot_timeline(book_path)`` — anchor + event calendar parser

All other helpers are private (underscore prefix) and exposed only for
direct unit testing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from tools.timeline_anchor import (
    ChapterAnchor,
    TimePoint,
    _to_datetime,
    compute_relative_phrase_mapping,
    get_chapter_anchor,
    shift_days,
    shift_hours,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CalendarEvent:
    """One row of the ``plot/timeline.md`` Event Calendar.

    ``year_is_synthetic`` is ``True`` only for events whose year had to
    be invented by ``_parse_yearless_timeline`` (Issue #509) because the
    row itself gave no year — never set by the primary parse path, and
    not set for a year-less-fallback event whose row *did* state its
    own explicit year. ``to_dict()`` only emits ``real_date_display``
    for such events, so a normal book's payload is unchanged.
    """

    story_day: int
    real_date: date
    chapter_slug: str
    key_events: str
    year_is_synthetic: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "story_day": self.story_day,
            "real_date": self.real_date.isoformat(),
        }
        if self.year_is_synthetic:
            d["real_date_display"] = f"{_MONTH_ABBR[self.real_date.month]} {self.real_date.day}"
        d["chapter_slug"] = self.chapter_slug
        d["key_events"] = self.key_events
        return d


@dataclass
class TimelineCalendar:
    """Parsed ``plot/timeline.md`` — anchor + ordered event list.

    ``synthetic_year`` is ``True`` when at least one date in the file had
    no stated year and was resolved via ``_parse_yearless_timeline``'s
    internal, non-canonical year counter (Issue #509) — never set by the
    primary parse path. Drift detection re-projects against it (see
    ``_detect_drift``) so a synthetic year doesn't get diffed against a
    real one as if they were the same calendar.

    ``out_of_order_steps`` counts document-order backward month steps
    that were *not* large enough to be treated as a real year wrap (see
    ``_YEAR_WRAP_MONTH_DROP``) — always 0 outside the year-less fallback.
    A nonzero count means the file's row order doesn't strictly track
    chronological order, which the fallback's date arithmetic assumes;
    consumers can use it to gauge confidence in the resolved dates
    without it blocking parsing (Issue #509 follow-up from code review).
    """

    anchor_date: date
    anchor_story_day: int
    events: list[CalendarEvent] = field(default_factory=list)
    synthetic_year: bool = False
    out_of_order_steps: int = 0


@dataclass
class PhraseMatch:
    """A relative time phrase found in draft prose."""

    chapter: str
    line: int
    phrase: str
    snippet: str
    implied_date: date


@dataclass
class TimelineFinding:
    """Drift between phrase-implied date and calendar event date."""

    chapter: str
    scene: str | None
    line: int
    phrase: str
    implied_date: date
    actual_event_date: date
    drift_days: int
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter": self.chapter,
            "scene": self.scene,
            "line": self.line,
            "phrase": self.phrase,
            "implied_date": self.implied_date.isoformat(),
            "actual_event_date": self.actual_event_date.isoformat(),
            "drift_days": self.drift_days,
            "snippet": self.snippet,
        }


# ---------------------------------------------------------------------------
# plot/timeline.md parser
# ---------------------------------------------------------------------------


# Matches "Dec 25, 2025" — the human-readable format used by the
# template.
_HUMAN_DATE_RE = re.compile(
    r"^(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"(?P<day>\d{1,2}),?\s+"
    r"(?P<year>\d{4})$"
)
# Matches "2025-12-25" — ISO 8601, also accepted.
# NB: anchored with \Z, not $ — same anchoring gap #518/#520/#526 fixed
# elsewhere; `$` also matches before a trailing newline (#527).
_ISO_DATE_RE = re.compile(r"^(?P<year>\d{4})-(?P<mon>\d{2})-(?P<day>\d{2})\Z")
_STORY_DAY_RE = re.compile(r"Day\s+(?P<n>\d+)", re.IGNORECASE)

_MONTH_ABBR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}
_MONTH_NUMBERS = {abbr.lower(): num for num, abbr in _MONTH_ABBR.items()}

# Finds the first bare "Mon DD" (optionally ", YYYY") occurrence
# anywhere in free-form cell text — Issue #509's year-less timelines.
# Tolerates a leading weekday ("Sat Nov 16"), markdown bold emphasis
# ("**Oct 18**"), and a trailing day range ("Oct 15-17" — only the
# range's first day is taken). Month names are enumerated (not a bare
# \w* tail) and the day group carries the same (?!\d) lookahead as
# _ANCHOR_BULLET_RE, so a month-and-year-only cell like "Oct 2025"
# isn't misread as day 20 of an unspecified year.
_CELL_MONTH_DAY_RE = re.compile(
    r"(?P<mon>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+"
    r"(?P<day>\d{1,2})(?!\d)"
    r"(?:,?\s*(?P<year>\d{4}))?",
    re.IGNORECASE,
)

# Internal-only synthetic starting year for year-less timelines — never
# exposed to consumers as story canon (see CalendarEvent.to_dict()'s
# real_date_display), only used so datetime.date arithmetic (drift
# detection) works across a book that never states an absolute year.
_SENTINEL_BASE_YEAR = 1

# Minimum month-number drop (relative to the previous item) treated as
# a real Dec -> Jan-style year wrap rather than a table simply listed
# slightly out of strict chronological order (e.g. a lead-up week
# appearing textually after the anchor bullet, one month earlier/later
# than a neighboring table). 6 comfortably separates a Dec(12)->Jan(1)
# wrap (drop of 11) from any plausible single-table misordering.
_YEAR_WRAP_MONTH_DROP = 6

# Matches a markdown heading line, capturing hash-run length so ###+
# sub-headings can be told apart from top-level ## headings.
_HEADING_RE = re.compile(r"^(#{2,6})\s*(.*)$")

# Matches a bullet anchor like "Story Day 1 = Friday, October 18" or
# "...October 18, 2025" — Issue #508. The weekday is optional (some
# authors omit it); the month token accepts both the 3-letter
# abbreviation and the full name (\w* swallows the rest). The
# day-of-month lookahead (?!\d) stops "October 2025" (no day given)
# from misreading "20" as the day and "25" as a truncated year.
_ANCHOR_BULLET_RE = re.compile(
    r"Story\s+Day\s+(?P<day>\d+)\s*=\s*"
    r"(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*,\s*)?"
    r"(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+"
    r"(?P<daynum>\d{1,2})(?!\d)"
    r"(?:,?\s*(?P<year>\d{4}))?",
    re.IGNORECASE,
)

# Markdown list-item marker — bullet anchors must be actual list items,
# not arbitrary prose that happens to mention "Story Day N = ..." (a
# discussion of a rejected anchor date, for example).
_LIST_ITEM_RE = re.compile(r"^[-*+]\s")

# Fenced code block delimiter (``` or ~~~, any length ≥ 3) — lines
# inside a fence are documentation/examples, not live timeline data.
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")


def _parse_real_date(value: str) -> date | None:
    """Parse the Real Date cell — supports ``Dec 25, 2025`` and ISO."""
    text = value.strip()
    iso = _ISO_DATE_RE.match(text)
    if iso:
        try:
            return date(
                int(iso.group("year")),
                int(iso.group("mon")),
                int(iso.group("day")),
            )
        except ValueError:
            return None
    human = _HUMAN_DATE_RE.match(text)
    if human:
        try:
            return datetime.strptime(
                f"{human.group('mon')} {human.group('day')} {human.group('year')}",
                "%b %d %Y",
            ).date()
        except ValueError:
            return None
    return None


def _parse_story_day(value: str) -> int | None:
    match = _STORY_DAY_RE.search(value)
    if match:
        return int(match.group("n"))
    return None


def _split_table_row(line: str) -> list[str]:
    """Split a markdown table row into trimmed cell values."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_separator_row(line: str) -> bool:
    """Detect ``|---|---|`` style separator rows."""
    cells = _split_table_row(line)
    if not cells:
        return False
    return all(re.fullmatch(r":?-+:?", cell) for cell in cells if cell)


def _normalize_header_cells(cells: list[str]) -> list[str]:
    """Lowercase header cells and strip markdown emphasis (``**bold**``,
    ``_italic_``, `` `code` ``) so ``**Story Start**`` classifies the same
    as ``Story Start``.
    """
    return [c.strip().strip("*_`").strip().lower() for c in cells]


def _classify_table_header(cells: list[str]) -> str | None:
    """Classify a table by its header cells rather than the heading text
    above it — Issue #508. Narrative act/week headings (``## Act 1: ...``
    / ``### Week 0 ...``) don't match the ``## Event Calendar`` text
    whitelist, so relying on heading text alone silently drops every
    event table nested under a differently-worded section.

    ``story start`` is checked before ``chapter``/``story day`` since an
    anchor table could plausibly carry its own chapter column — the more
    specific signal must win. Events classification requires *both* a
    chapter and a story-day column (not just any date+chapter table) so
    unrelated tables sharing a heading section (a revision log, a
    documentation example) aren't ingested as calendar events.
    """
    lowered = _normalize_header_cells(cells)
    if any("story start" in c for c in lowered):
        return "anchor"
    if any("chapter" in c for c in lowered) and any("story day" in c for c in lowered):
        return "events"
    return None


def _find_column(lowered_cells: list[str], *needles: str) -> int | None:
    """Find the header cell matching the most specific of ``needles``.

    Tries each needle in order across *all* cells before falling back to
    the next, looser needle — a single per-cell "any needle" scan would
    let a loose fallback term (``"day"``) match an unrelated column
    (``"Cabin Day"``, ``"Day of Week"``) ahead of the specific one
    (``"Story Day"``) it was meant to only catch as a last resort.
    """
    for needle in needles:
        for i, cell in enumerate(lowered_cells):
            if needle in cell:
                return i
    return None


def _map_event_columns(header_cells: list[str]) -> dict[str, int | None] | None:
    """Resolve semantic column indices from an events-table header row.

    Column order/count isn't fixed across books — Firelight's tables
    drop the Day-of-Week/Characters columns and add a Cabin Day column
    (Issue #508) — so rows are read by header name, not hardcoded index.
    Returns ``None`` if the header lacks the columns ``_classify_table_header``
    already required (a caller bug if this ever triggers on a table it
    classified as "events").
    """
    lowered = _normalize_header_cells(header_cells)
    date_idx = _find_column(lowered, "real date", "date")
    chapter_idx = _find_column(lowered, "chapter")
    story_day_idx = _find_column(lowered, "story day")
    if date_idx is None or chapter_idx is None or story_day_idx is None:
        return None
    return {
        "story_day": story_day_idx,
        "date": date_idx,
        "chapter": chapter_idx,
        "key_events": _find_column(lowered, "key events", "events", "summary"),
    }


def _map_anchor_columns(header_cells: list[str]) -> dict[str, int | None] | None:
    """Resolve semantic column indices from an anchor-table header row.

    Mirrors ``_map_event_columns`` so a reordered Anchor Point table
    (e.g. ``Real Date`` before ``Story Start``) is read correctly
    instead of via the hardcoded ``cells[0]``/``cells[1]`` positions of
    the canonical layout.
    """
    lowered = _normalize_header_cells(header_cells)
    date_idx = _find_column(lowered, "real date", "date")
    if date_idx is None:
        return None
    return {
        "story_day": _find_column(lowered, "story start", "story day", "day"),
        "date": date_idx,
    }


def _cell_at(cells: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(cells):
        return ""
    return cells[idx]


def _iter_timeline_lines(
    text: str,
    classify_header: Callable[[list[str]], tuple[str | None, dict[str, int | None] | None]],
):
    """Shared fence/heading/table state-machine walk over a timeline document.

    Both ``parse_plot_timeline`` (Issue #79/#508) and its year-less
    fallback ``_parse_yearless_timeline`` (Issue #509) need to walk the
    same document shape — skip fenced code blocks, track whether we're
    under an ``## Anchor Point``-titled section (a ``###+`` sub-heading
    doesn't reset it, only another top-level ``##`` does), collect
    anchor bullets, and classify+read markdown tables — differing only
    in *how* a table header is classified and *what* to do with a
    classified row. This generator owns the shared walk; callers own
    the per-mode interpretation.

    Yields ``("anchor_bullet", match)`` for each ``_ANCHOR_BULLET_RE``
    match found on a list-item line under the anchor heading, or
    ``("row", table_kind, column_map, cells)`` for each data row of a
    table whose header ``classify_header`` recognized (returned
    ``table_kind`` is an opaque label — ``"anchor"``/``"events"`` in
    current callers — interpreted by the caller, not this function).
    Rows of an unrecognized table (``classify_header`` returned
    ``(None, ...)``) are silently skipped, matching how both callers
    already treated them before this was extracted.
    """
    under_anchor_heading = False
    in_fence = False
    header_seen = False
    pending_header_cells: list[str] | None = None
    table_kind: str | None = None
    column_map: dict[str, int | None] | None = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()

        if _FENCE_RE.match(stripped):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        heading_match = _HEADING_RE.match(stripped)
        if heading_match:
            hashes, heading_text = heading_match.groups()
            title = heading_text.strip().strip("*_`").strip().lower()
            if title.startswith("anchor"):
                under_anchor_heading = True
            elif len(hashes) == 2:
                # Only a top-level ## heading switches section away from
                # anchor — a ###+ sub-heading (e.g. "### Week 0") nests
                # inside whatever ## section it appears under and must
                # not reset it.
                under_anchor_heading = False
            header_seen = False
            pending_header_cells = None
            table_kind = None
            column_map = None
            continue

        if not stripped.startswith("|"):
            header_seen = False
            pending_header_cells = None
            table_kind = None
            column_map = None
            if under_anchor_heading and _LIST_ITEM_RE.match(stripped):
                m = _ANCHOR_BULLET_RE.search(stripped)
                if m:
                    yield "anchor_bullet", m
            continue

        # Inside a markdown table.
        if _is_separator_row(stripped):
            if pending_header_cells is not None:
                header_seen = True
                table_kind, column_map = classify_header(pending_header_cells)
            continue

        cells = _split_table_row(stripped)
        if not header_seen:
            # First row is the header — capture it and wait for the separator.
            pending_header_cells = cells
            continue
        if table_kind is None or not cells:
            continue

        yield "row", table_kind, column_map, cells


def _classify_header_primary(cells: list[str]) -> tuple[str | None, dict[str, int | None] | None]:
    """``classify_header`` for the primary parse path (Issue #79/#508)."""
    kind = _classify_table_header(cells)
    if kind == "events":
        return kind, _map_event_columns(cells)
    if kind == "anchor":
        return kind, _map_anchor_columns(cells)
    return kind, None


def _classify_header_yearless(cells: list[str]) -> tuple[str | None, dict[str, int | None] | None]:
    """``classify_header`` for the year-less fallback (Issue #509)."""
    column_map = _classify_events_header_yearless(cells)
    return ("events" if column_map is not None else None), column_map


def _resolve_bullet_anchor(
    candidates: list[tuple[bool, int, str, int, str | None]],
    events: list[CalendarEvent],
) -> tuple[date, int] | None:
    """Pick the best bullet-anchor candidate and resolve it to a date.

    Candidates with an explicit year are preferred over year-less ones
    (in document order within each tier) — a discussion of a rejected
    anchor earlier in the section must not shadow a later, more precise
    bullet. A year-less candidate's year is inferred from the
    chronologically earliest matching calendar event, falling back to
    the earliest event overall.
    """
    with_year = [c for c in candidates if c[0]]
    chosen = with_year[0] if with_year else candidates[0] if candidates else None
    if chosen is None:
        return None
    _, day, mon, daynum, year_str = chosen
    if year_str is None:
        same_day = [e for e in events if e.story_day == day]
        if same_day:
            year_str = str(min(same_day, key=lambda e: e.real_date).real_date.year)
        elif events:
            year_str = str(min(events, key=lambda e: e.real_date).real_date.year)
        else:
            return None
    try:
        resolved = datetime.strptime(f"{mon} {daynum} {year_str}", "%b %d %Y").date()
    except ValueError:
        return None
    return resolved, day


def parse_plot_timeline(book_path: Path) -> TimelineCalendar | None:
    """Parse ``{book_path}/plot/timeline.md`` into a TimelineCalendar.

    Returns ``None`` if the file is missing, can't be opened, or no
    usable anchor could be found. Parsing is forgiving — unrecognized
    rows are skipped rather than aborting, so partial timelines still
    yield usable calendars.

    Event tables are recognized structurally by their header cells (a
    date, chapter, and story-day column), not by the heading text above
    them, so narrative act/week headings work the same as a canonical
    ``## Event Calendar`` heading (Issue #508). The anchor may also be
    given as a bullet list item under ``## Anchor Point`` instead of a
    table row (``- Story Day 1 = Friday, October 18``); when that text
    omits a year, it's inferred from a matching calendar event. A table
    anchor row always takes precedence over a bullet, regardless of
    which appears first in the file. Fenced code blocks are skipped
    entirely — a documentation example embedded in the file must not be
    read as live timeline data.
    """
    timeline_path = book_path / "plot" / "timeline.md"
    if not timeline_path.is_file():
        return None
    try:
        text = timeline_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    anchor_date: date | None = None
    anchor_story_day: int | None = None
    events: list[CalendarEvent] = []
    bullet_candidates: list[tuple[bool, int, str, int, str | None]] = []

    for item in _iter_timeline_lines(text, _classify_header_primary):
        if item[0] == "anchor_bullet":
            m = item[1]
            bullet_candidates.append(
                (
                    bool(m.group("year")),
                    int(m.group("day")),
                    m.group("mon"),
                    int(m.group("daynum")),
                    m.group("year"),
                )
            )
            continue

        _, table_kind, column_map, cells = item
        if table_kind == "anchor" and anchor_date is None and column_map is not None:
            # Anchor row layout: | Story Start | Real Date | DoW | Notes |
            # — column order isn't assumed, resolved via _map_anchor_columns.
            # A table row always wins over a bullet candidate, regardless
            # of which appears first in the file.
            d = _parse_real_date(_cell_at(cells, column_map["date"]))
            if d is not None:
                anchor_date = d
                row_day = _parse_story_day(_cell_at(cells, column_map["story_day"]))
                anchor_story_day = row_day if row_day is not None else 1
        elif table_kind == "events" and column_map is not None:
            d = _parse_real_date(_cell_at(cells, column_map["date"]))
            if d is None:
                continue
            story_day = _parse_story_day(_cell_at(cells, column_map["story_day"])) or 0
            chapter_slug = _cell_at(cells, column_map["chapter"])
            key_events = _cell_at(cells, column_map["key_events"])
            events.append(
                CalendarEvent(
                    story_day=story_day,
                    real_date=d,
                    chapter_slug=chapter_slug,
                    key_events=key_events,
                )
            )

    if anchor_date is None and bullet_candidates:
        resolved = _resolve_bullet_anchor(bullet_candidates, events)
        if resolved is not None:
            anchor_date, anchor_story_day = resolved

    if anchor_date is None:
        # No usable anchor via the strict/borrowed-year paths above — try
        # the year-less fallback (Issue #509) before giving up.
        return _parse_yearless_timeline(text)
    return TimelineCalendar(
        anchor_date=anchor_date,
        anchor_story_day=anchor_story_day or 1,
        events=events,
    )


def _extract_month_day(text: str) -> tuple[int, int, int | None] | None:
    """Find the first bare "Mon DD" occurrence in free-form cell text.

    Returns ``(month, day, year_or_None)`` — a row may state its own
    year even when the anchor doesn't (Issue #509's fallback must not
    discard a year the file actually gives it).
    """
    m = _CELL_MONTH_DAY_RE.search(text)
    if not m:
        return None
    year = int(m.group("year")) if m.group("year") else None
    return _MONTH_NUMBERS[m.group("mon")[:3].lower()], int(m.group("day")), year


def _classify_events_header_yearless(cells: list[str]) -> dict[str, int | None] | None:
    """Map an events-table header for year-less timelines (Issue #509).

    Firelight's real tables use a plain ``Day`` (weekday, sometimes
    merged with the date — ``Sat Nov 16``) + ``Date`` column pair
    instead of the template's ``Story Day``/``Real Date`` naming, so
    ``_classify_table_header`` never recognizes them. Requires a
    chapter column *and* both a ``Date`` and a ``Day`` column — a
    foreign date+chapter table (a revision log, with no ``Day`` column)
    isn't ingested as event data. Column lookup is substring-based (via
    ``_find_column``, matching ``_classify_table_header``'s own
    convention) rather than an exact-name match, so this is a heuristic
    rather than a guarantee against every foreign table shape.
    """
    lowered = _normalize_header_cells(cells)
    chapter_idx = _find_column(lowered, "chapter")
    date_idx = _find_column(lowered, "real date", "date")
    day_idx = _find_column(lowered, "day")
    if chapter_idx is None or date_idx is None or day_idx is None:
        return None
    return {
        "chapter": chapter_idx,
        "date": date_idx,
        "day": day_idx,
        "story_day": _find_column(lowered, "story day"),
        "key_events": _find_column(lowered, "key events", "events", "summary"),
    }


def _parse_yearless_timeline(text: str) -> TimelineCalendar | None:
    """Last-resort parse for year-less, weekday-tagged timelines (Issue #509).

    Invoked only when the primary parse above finds no usable anchor at
    all — i.e. the anchor bullet has no year and there's no dated event
    to borrow one from via ``_resolve_bullet_anchor`` (a book that is
    deliberately real-world-year-agnostic, not a data-entry oversight).
    Individual rows may still state their own explicit year even when
    the anchor doesn't; those years are honored as-is. Every date that
    has no year of its own — the anchor's included, when it lacks one —
    is resolved to a synthetic, strictly-internal year via document
    order plus a running counter that increments on a Dec -> Jan-style
    wrap. Whenever any part of the calendar had to be synthesized this
    way, ``TimelineCalendar.synthetic_year`` is set — that flag governs
    drift-detection date arithmetic in ``_detect_drift`` and is why the
    synthetic year is never meant to reach consumers as established
    canon on its own (see ``CalendarEvent.to_dict()``'s
    ``real_date_display``, e.g. ``"Oct 18"``).

    Only a bullet anchor is supported (Firelight's actual layout); a
    year-less anchor *table* row would need its own extension.
    """
    anchor_candidates: list[tuple[bool, int, int, int, int | None]] = []
    raw_events: list[dict[str, Any]] = []

    for item in _iter_timeline_lines(text, _classify_header_yearless):
        if item[0] == "anchor_bullet":
            m = item[1]
            anchor_candidates.append(
                (
                    bool(m.group("year")),
                    int(m.group("day")),
                    _MONTH_NUMBERS[m.group("mon")[:3].lower()],
                    int(m.group("daynum")),
                    int(m.group("year")) if m.group("year") else None,
                )
            )
            continue

        _, table_kind, column_map, cells = item
        if table_kind != "events" or column_map is None:
            continue

        date_idx = column_map["date"]
        extracted = _extract_month_day(_cell_at(cells, date_idx)) if date_idx is not None else None
        if extracted is None and column_map["day"] is not None:
            extracted = _extract_month_day(_cell_at(cells, column_map["day"]))
        if extracted is None:
            continue
        month, day, year = extracted
        story_day_idx = column_map["story_day"]
        story_day = _parse_story_day(_cell_at(cells, story_day_idx)) if story_day_idx is not None else None
        raw_events.append(
            {
                "month": month,
                "day": day,
                "year": year,
                "story_day": story_day,
                "chapter_slug": _cell_at(cells, column_map["chapter"]),
                "key_events": _cell_at(cells, column_map["key_events"]),
            }
        )

    if not anchor_candidates:
        return None

    with_year = [c for c in anchor_candidates if c[0]]
    _, anchor_story_day, anchor_month, anchor_day, anchor_year = (
        with_year[0] if with_year else anchor_candidates[0]
    )
    # Normalize once, up front — the same value must feed both the
    # story_day backfill below and the returned calendar, or a "Story
    # Day 0" bullet would backfill events relative to 0 while the
    # calendar itself claimed anchor_story_day == 1.
    anchor_story_day = anchor_story_day or 1

    # Document-order sequence — anchor first, then every event row — feeds
    # the year-resolution walk below. A row's own explicit year (Issue
    # #509 H2: a book may be year-less only in the anchor bullet, with
    # individual rows still stating a year) always overrides the running
    # counter; only rows with no year of their own inherit/synthesize one.
    sequence: list[tuple[int | None, int]] = [(anchor_year, anchor_month)]
    sequence.extend((e["year"], e["month"]) for e in raw_events)
    synthetic_year = anchor_year is None or any(e["year"] is None for e in raw_events)

    current_year = _SENTINEL_BASE_YEAR
    last_month: int | None = None
    resolved_years: list[int] = []
    out_of_order_steps = 0
    for year, month in sequence:
        if year is not None:
            current_year = year
        elif last_month is not None and month < last_month:
            if last_month - month >= _YEAR_WRAP_MONTH_DROP:
                # A genuine Dec -> Jan-style wrap, not just a table
                # listed slightly out of chronological order (e.g. a
                # lead-up week appearing after the anchor bullet but
                # within the same month, or a table off by one month
                # either way).
                current_year += 1
            else:
                # A smaller backward step that wasn't treated as a wrap
                # — the document's row order doesn't strictly track
                # chronological order here. Not fatal (the resolved
                # year is still whatever the counter already was), but
                # recorded so callers can gauge how much to trust the
                # resolved dates (Issue #509 code-review follow-up).
                out_of_order_steps += 1
        resolved_years.append(current_year)
        last_month = month

    try:
        anchor_date = date(resolved_years[0], anchor_month, anchor_day)
    except ValueError:
        # Sentinel year 1 isn't a leap year — an anchor of Feb 29 (or
        # any other invalid combination) has no usable calendar to
        # build, same as a missing anchor.
        return None
    events: list[CalendarEvent] = []
    for year, raw_event in zip(resolved_years[1:], raw_events):
        try:
            real_date = date(year, raw_event["month"], raw_event["day"])
        except ValueError:
            continue
        story_day = raw_event["story_day"]
        if story_day is None:
            story_day = anchor_story_day + (real_date - anchor_date).days
        events.append(
            CalendarEvent(
                story_day=story_day,
                real_date=real_date,
                chapter_slug=raw_event["chapter_slug"],
                key_events=raw_event["key_events"],
                year_is_synthetic=raw_event["year"] is None,
            )
        )

    return TimelineCalendar(
        anchor_date=anchor_date,
        anchor_story_day=anchor_story_day,
        events=events,
        synthetic_year=synthetic_year,
        out_of_order_steps=out_of_order_steps,
    )


# ---------------------------------------------------------------------------
# Phrase matching
# ---------------------------------------------------------------------------


def _resolve_phrase_dates(anchor: ChapterAnchor) -> dict[str, date]:
    """Map relative phrases → real ``date`` objects via the anchor.

    Reuses ``compute_relative_phrase_mapping`` to know which phrases
    are recognized, then re-derives the real date by shifting the
    anchor's start TimePoint and converting through ``_to_datetime`` —
    string-parsing the human-readable labels would lose information.
    """
    if anchor.start is None:
        return {}
    start = anchor.start
    available = compute_relative_phrase_mapping(anchor)
    out: dict[str, date] = {}

    def _add(phrase: str, point: TimePoint | None) -> None:
        if point is None:
            return
        dt = _to_datetime(point)
        if dt is None:
            return
        out[phrase] = dt.date()

    if "yesterday" in available:
        _add("yesterday", shift_days(start, -1))
    if "tomorrow" in available:
        _add("tomorrow", shift_days(start, 1))
    if "last week" in available:
        _add("last week", shift_days(start, -7))
    if "next week" in available:
        _add("next week", shift_days(start, 7))
    # Same-day phrases all collapse onto the anchor date.
    today_dt = _to_datetime(start)
    if today_dt is not None:
        today = today_dt.date()
        for phrase in (
            "this morning",
            "this afternoon",
            "this evening",
            "tonight",
        ):
            if phrase in available:
                out[phrase] = today
    if "last night" in available:
        _add("last night", shift_days(start, -1))
    # Hour-relative phrases — same calendar day for shifts < 24h.
    if "an hour ago" in available:
        _add("an hour ago", shift_hours(start, -1))
    if "one hour ago" in available:
        _add("one hour ago", shift_hours(start, -1))
    if "two hours ago" in available:
        _add("two hours ago", shift_hours(start, -2))
    return out


def _build_phrase_pattern(phrases: list[str]) -> re.Pattern[str]:
    """Compile a longest-first, word-boundary, case-insensitive matcher."""
    # Sort longest first so "last week" wins over "last".
    sorted_phrases = sorted(phrases, key=len, reverse=True)
    escaped = [re.escape(p) for p in sorted_phrases]
    pattern = r"\b(?:" + "|".join(escaped) + r")\b"
    return re.compile(pattern, re.IGNORECASE)


def _line_for_offset(text: str, offset: int) -> int:
    """1-based line number for a character offset within ``text``."""
    return text.count("\n", 0, offset) + 1


def _make_snippet(text: str, start: int, end: int, context: int = 60) -> str:
    """Extract ±context characters around ``[start:end]``, single-line."""
    lo = max(0, start - context)
    hi = min(len(text), end + context)
    snippet = text[lo:hi].replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", snippet).strip()


def _find_phrase_matches(
    chapter_slug: str,
    draft_text: str,
    phrase_date_map: dict[str, date],
) -> list[PhraseMatch]:
    """Locate every recognized phrase in the draft and tag with its date.

    Longest-phrase-first ordering ensures multi-word phrases like
    ``last week`` aren't shadowed by their substrings (``last``).
    """
    if not phrase_date_map or not draft_text:
        return []
    pattern = _build_phrase_pattern(list(phrase_date_map.keys()))
    matches: list[PhraseMatch] = []
    # Build a lowercase-key lookup so case-insensitive matches resolve.
    lowered = {k.lower(): v for k, v in phrase_date_map.items()}
    for m in pattern.finditer(draft_text):
        phrase_key = m.group(0).lower()
        implied = lowered.get(phrase_key)
        if implied is None:
            continue
        line_no = _line_for_offset(draft_text, m.start())
        snippet = _make_snippet(draft_text, m.start(), m.end())
        matches.append(
            PhraseMatch(
                chapter=chapter_slug,
                line=line_no,
                phrase=phrase_key,
                snippet=snippet,
                implied_date=implied,
            )
        )
    return matches


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


def _reprojected_day_diff(event_date: date, implied_date: date) -> int:
    """Day distance tolerant of a synthetic (non-canonical) event year.

    ``implied_date`` comes from a chapter-README anchor and always
    carries a real calendar year; a year-less timeline's ``event_date``
    (Issue #509) carries an internal synthetic one instead, so diffing
    them directly can yield a distance of hundreds of thousands of days
    for what's actually a same-week event. Re-projecting the implied
    date onto the event's year (and its immediate neighbors, to survive
    a Dec/Jan boundary) recovers the intended day-of-year distance.
    """
    best: int | None = None
    for offset in (-1, 0, 1):
        try:
            candidate = implied_date.replace(year=event_date.year + offset)
        except ValueError:
            continue
        diff = abs((event_date - candidate).days)
        if best is None or diff < best:
            best = diff
    return best if best is not None else abs((event_date - implied_date).days)


def _detect_drift(
    matches: list[PhraseMatch],
    calendar: TimelineCalendar,
    chapter_slug: str,
    threshold_days: int = 0,
) -> list[TimelineFinding]:
    """Flag matches whose implied date diverges from the chapter's event."""
    chapter_events = [e for e in calendar.events if e.chapter_slug == chapter_slug]
    if not chapter_events:
        return []
    # If multiple events for the same chapter exist, prefer the one whose
    # date is closest to the implied date — that's the most charitable
    # mapping when chapters span days.
    day_diff = _reprojected_day_diff if calendar.synthetic_year else (
        lambda event_date, implied_date: abs((event_date - implied_date).days)
    )
    findings: list[TimelineFinding] = []
    for match in matches:
        event = min(
            chapter_events,
            key=lambda e: day_diff(e.real_date, match.implied_date),
        )
        diff = day_diff(event.real_date, match.implied_date)
        if diff > threshold_days:
            findings.append(
                TimelineFinding(
                    chapter=match.chapter,
                    scene=None,
                    line=match.line,
                    phrase=match.phrase,
                    implied_date=match.implied_date,
                    actual_event_date=event.real_date,
                    drift_days=diff,
                    snippet=match.snippet,
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Scene resolution
# ---------------------------------------------------------------------------


# Matches scene headings: "### Szene 3" or "### Scene 3" (with optional
# trailing dash + name and time-range parenthetical).
_SCENE_HEADER_RE = re.compile(
    r"^###\s+(?P<header>(?:Szene|Scene)\s+\d+)",
)


def _find_scene_at_line(draft_text: str, line: int) -> str | None:
    """Walk backwards from ``line`` to find the enclosing scene header."""
    lines = draft_text.splitlines()
    # Clamp to valid range; convert 1-based to 0-based.
    idx = min(max(line - 1, 0), len(lines) - 1) if lines else -1
    while idx >= 0:
        m = _SCENE_HEADER_RE.match(lines[idx])
        if m:
            return m.group("header")
        idx -= 1
    return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


_CHAPTER_DIR_RE = re.compile(r"^(?P<num>\d{1,3})-")


def _list_chapter_dirs(book_path: Path) -> list[Path]:
    chapters_dir = book_path / "chapters"
    if not chapters_dir.is_dir():
        return []
    out: list[tuple[int, Path]] = []
    for entry in chapters_dir.iterdir():
        if not entry.is_dir():
            continue
        m = _CHAPTER_DIR_RE.match(entry.name)
        if not m:
            continue
        out.append((int(m.group("num")), entry))
    out.sort(key=lambda pair: pair[0])
    return [path for _, path in out]


def validate_timeline(book_path: Path) -> dict[str, Any]:
    """Cross-validate chapter anchors + draft phrases against plot/timeline.md.

    Returns a JSON-serializable dict matching the Issue #79 schema:
    ``book_slug``, ``chapters_checked``, ``calendar_built``,
    ``findings``, ``missing_anchors``, ``report_path``.
    """
    calendar = parse_plot_timeline(book_path)
    chapters = _list_chapter_dirs(book_path)

    findings_out: list[dict[str, Any]] = []
    missing_anchors: list[str] = []

    for chapter_dir in chapters:
        slug = chapter_dir.name
        anchor = get_chapter_anchor(chapter_dir)
        if anchor is None or anchor.start is None:
            # Chapter README lacks a parseable Chapter Timeline section.
            missing_anchors.append(slug)
            continue

        draft_path = chapter_dir / "draft.md"
        if not draft_path.is_file():
            # No draft yet — nothing to validate against.
            continue
        try:
            draft_text = draft_path.read_text(encoding="utf-8")
        except OSError:
            continue

        phrase_dates = _resolve_phrase_dates(anchor)
        if not phrase_dates:
            continue

        matches = _find_phrase_matches(slug, draft_text, phrase_dates)
        if not matches or calendar is None:
            continue

        for finding in _detect_drift(matches, calendar, slug):
            # Late-bind the scene name now that we have the draft text.
            scene_name = _find_scene_at_line(draft_text, finding.line)
            finding.scene = scene_name
            findings_out.append(finding.to_dict())

    report_dir = book_path / "reports"
    report_path = report_dir / "timeline-validation.json"
    result = {
        "book_slug": book_path.name,
        "chapters_checked": len(chapters),
        "calendar_built": calendar is not None,
        "findings": findings_out,
        "missing_anchors": missing_anchors,
        "report_path": str(report_path),
    }
    # Best-effort persistence — never crash the validator on disk errors.
    try:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass
    return result
