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
from typing import Any

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
    """One row of the ``plot/timeline.md`` Event Calendar."""

    story_day: int
    real_date: date
    chapter_slug: str
    key_events: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "story_day": self.story_day,
            "real_date": self.real_date.isoformat(),
            "chapter_slug": self.chapter_slug,
            "key_events": self.key_events,
        }


@dataclass
class TimelineCalendar:
    """Parsed ``plot/timeline.md`` — anchor + ordered event list."""

    anchor_date: date
    anchor_story_day: int
    events: list[CalendarEvent] = field(default_factory=list)


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
_ISO_DATE_RE = re.compile(r"^(?P<year>\d{4})-(?P<mon>\d{2})-(?P<day>\d{2})$")
_STORY_DAY_RE = re.compile(r"Day\s+(?P<n>\d+)", re.IGNORECASE)


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


def parse_plot_timeline(book_path: Path) -> TimelineCalendar | None:
    """Parse ``{book_path}/plot/timeline.md`` into a TimelineCalendar.

    Returns ``None`` if the file is missing or can't be opened. Parsing
    is forgiving — unrecognized rows are skipped rather than aborting,
    so partial timelines still yield usable calendars.
    """
    timeline_path = book_path / "plot" / "timeline.md"
    if not timeline_path.is_file():
        return None
    try:
        text = timeline_path.read_text(encoding="utf-8")
    except OSError:
        return None

    anchor_date: date | None = None
    anchor_story_day: int | None = None
    events: list[CalendarEvent] = []

    section: str | None = None  # "anchor" | "events" | None
    in_table = False
    header_seen = False

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        # Section transitions — heading lines reset the table state.
        if stripped.startswith("##"):
            heading = stripped.lstrip("#").strip().lower()
            if heading.startswith("anchor"):
                section = "anchor"
            elif heading.startswith("event calendar") or heading.startswith(
                "events"
            ):
                section = "events"
            else:
                section = None
            in_table = False
            header_seen = False
            continue

        if section is None or not stripped.startswith("|"):
            in_table = False
            header_seen = False
            continue

        # Inside a markdown table.
        if _is_separator_row(stripped):
            in_table = True
            header_seen = True
            continue

        cells = _split_table_row(stripped)
        if not header_seen:
            # First row is the header — skip and wait for the separator.
            continue
        if not in_table or not cells:
            continue

        if section == "anchor" and anchor_date is None:
            # Anchor row layout: | Story Start | Real Date | DoW | Notes |
            if len(cells) >= 2:
                day = _parse_story_day(cells[0])
                d = _parse_real_date(cells[1])
                if d is not None:
                    anchor_date = d
                    anchor_story_day = day if day is not None else 1
        elif section == "events":
            # Event row layout: | Story Day | Real Date | DoW | Chapter |
            #                   | Location | Key Events | Characters |
            if len(cells) >= 4:
                d = _parse_real_date(cells[1])
                if d is None:
                    continue
                story_day = _parse_story_day(cells[0]) or 0
                chapter_slug = cells[3]
                key_events = cells[5] if len(cells) > 5 else ""
                events.append(
                    CalendarEvent(
                        story_day=story_day,
                        real_date=d,
                        chapter_slug=chapter_slug,
                        key_events=key_events,
                    )
                )

    if anchor_date is None:
        # No usable anchor — caller treats this as "calendar not built".
        return None
    return TimelineCalendar(
        anchor_date=anchor_date,
        anchor_story_day=anchor_story_day or 1,
        events=events,
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


def _detect_drift(
    matches: list[PhraseMatch],
    calendar: TimelineCalendar,
    chapter_slug: str,
    threshold_days: int = 0,
) -> list[TimelineFinding]:
    """Flag matches whose implied date diverges from the chapter's event."""
    chapter_events = [
        e for e in calendar.events if e.chapter_slug == chapter_slug
    ]
    if not chapter_events:
        return []
    # If multiple events for the same chapter exist, prefer the one whose
    # date is closest to the implied date — that's the most charitable
    # mapping when chapters span days.
    findings: list[TimelineFinding] = []
    for match in matches:
        event = min(
            chapter_events,
            key=lambda e: abs((e.real_date - match.implied_date).days),
        )
        diff = abs((event.real_date - match.implied_date).days)
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
