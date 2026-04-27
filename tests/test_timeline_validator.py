"""Tests for ``tools.analysis.timeline_validator`` — Issue #79.

Cross-references chapter README anchors + relative-phrase usage in
draft prose against the canonical ``plot/timeline.md`` event calendar.
Drift between implied story-date (from a phrase like ``yesterday``) and
the actual calendar event date is reported as a finding.

Tests use ``tmp_path`` for full filesystem fixtures — no mocking — so
the validator's parsers and orchestrator are exercised end-to-end.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from tools.analysis.timeline_validator import (
    CalendarEvent,
    PhraseMatch,
    TimelineCalendar,
    _detect_drift,
    _find_phrase_matches,
    _find_scene_at_line,
    _resolve_phrase_dates,
    parse_plot_timeline,
    validate_timeline,
)
from tools.timeline_anchor import ChapterAnchor, TimePoint


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def make_book(tmp_path: Path, chapters: list[dict]) -> Path:
    """Build a minimal book scaffold for validator tests.

    Each chapter dict supports ``slug`` (required), ``readme`` (optional
    README.md text), and ``draft`` (optional draft.md text). Returns the
    book root path the validator can crawl.
    """
    book = tmp_path / "my-book"
    book.mkdir()
    (book / "chapters").mkdir()
    for ch in chapters:
        ch_dir = book / "chapters" / ch["slug"]
        ch_dir.mkdir()
        if "readme" in ch:
            (ch_dir / "README.md").write_text(ch["readme"], encoding="utf-8")
        if "draft" in ch:
            (ch_dir / "draft.md").write_text(ch["draft"], encoding="utf-8")
    return book


def write_timeline_md(book: Path, body: str) -> Path:
    """Drop a plot/timeline.md into the book scaffold."""
    plot_dir = book / "plot"
    plot_dir.mkdir(exist_ok=True)
    path = plot_dir / "timeline.md"
    path.write_text(body, encoding="utf-8")
    return path


MINIMAL_TIMELINE_MD = (
    "# Story Timeline\n\n"
    "## Anchor Point\n\n"
    "| Story Start | Real Date | Day of Week | Notes |\n"
    "|---|---|---|---|\n"
    "| Day 1 | Dec 25, 2025 | Thursday | Story begins here |\n\n"
    "## Event Calendar\n\n"
    "| Story Day | Real Date | Day of Week | Chapter | Location | Key Events | Characters |\n"
    "|---|---|---|---|---|---|---|\n"
    "| Day 1 | Dec 25, 2025 | Thursday | 01-beginning | Home | Protagonist arrives | Theo |\n"
    "| Day 2 | Dec 26, 2025 | Friday | 02-departure | Airport | Flight booked | Theo, Sarah |\n"
)


# ---------------------------------------------------------------------------
# parse_plot_timeline
# ---------------------------------------------------------------------------


class TestParsePlotTimeline:
    def test_parse_plot_timeline_returns_none_if_missing(self, tmp_path: Path):
        # Empty book with no plot/timeline.md.
        book = make_book(tmp_path, [])
        assert parse_plot_timeline(book) is None

    def test_parse_plot_timeline_extracts_anchor_and_events(
        self, tmp_path: Path
    ):
        book = make_book(tmp_path, [])
        write_timeline_md(book, MINIMAL_TIMELINE_MD)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 12, 25)
        assert calendar.anchor_story_day == 1
        assert len(calendar.events) == 2
        assert calendar.events[0].real_date == date(2025, 12, 25)
        assert calendar.events[0].chapter_slug == "01-beginning"
        assert calendar.events[1].real_date == date(2025, 12, 26)
        assert calendar.events[1].chapter_slug == "02-departure"

    def test_parse_plot_timeline_iso_dates_supported(self, tmp_path: Path):
        # The parser should also accept ISO 8601 dates (2025-12-25).
        body = (
            "## Anchor Point\n\n"
            "| Story Start | Real Date | Day of Week | Notes |\n"
            "|---|---|---|---|\n"
            "| Day 1 | 2025-12-25 | Thursday | Begin |\n\n"
            "## Event Calendar\n\n"
            "| Story Day | Real Date | Day of Week | Chapter | Location | "
            "Key Events | Characters |\n"
            "|---|---|---|---|---|---|---|\n"
            "| Day 1 | 2025-12-25 | Thursday | 01-x | Home | Arrives | Theo |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 12, 25)
        assert calendar.events[0].real_date == date(2025, 12, 25)


# ---------------------------------------------------------------------------
# _find_phrase_matches — regex with longest-first + word boundary
# ---------------------------------------------------------------------------


class TestFindPhraseMatches:
    def test_phrase_regex_longest_match_first(self):
        # "last week" must win over "last" — longest-phrase-first ordering.
        draft = "He thought about last week's disaster."
        phrase_map = {
            "last week": date(2025, 12, 18),
            "last": date(2025, 12, 24),
        }
        matches = _find_phrase_matches("01-test", draft, phrase_map)
        assert len(matches) == 1
        assert matches[0].phrase == "last week"
        assert matches[0].implied_date == date(2025, 12, 18)

    def test_no_match_inside_word(self):
        # "yesterday-gone" has yesterday inside a hyphenated compound; \b
        # should still treat it as a word, so this should match. We test
        # the stricter case: substring inside a single word like
        # "yesterdays" must NOT match.
        draft = "The yesterdays kept piling up."
        phrase_map = {"yesterday": date(2025, 12, 24)}
        matches = _find_phrase_matches("01-test", draft, phrase_map)
        assert matches == []

    def test_match_records_line_number_and_snippet(self):
        draft = (
            "Line one.\n"
            "Line two with yesterday in it.\n"
            "Line three.\n"
        )
        phrase_map = {"yesterday": date(2025, 12, 24)}
        matches = _find_phrase_matches("01-test", draft, phrase_map)
        assert len(matches) == 1
        assert matches[0].line == 2
        assert "yesterday" in matches[0].snippet

    def test_case_insensitive_match(self):
        draft = "Yesterday felt like a year ago."
        phrase_map = {"yesterday": date(2025, 12, 24)}
        matches = _find_phrase_matches("01-test", draft, phrase_map)
        assert len(matches) == 1
        assert matches[0].phrase == "yesterday"


# ---------------------------------------------------------------------------
# _resolve_phrase_dates — anchor → {phrase: date}
# ---------------------------------------------------------------------------


class TestResolvePhraseDates:
    def test_resolves_yesterday_and_tomorrow(self):
        # Anchor at Thu Dec 25 → yesterday=Dec 24, tomorrow=Dec 26.
        anchor = ChapterAnchor(
            chapter_slug="01-test",
            start=TimePoint(
                day_of_week="Thu", month="Dec", day=25, time="08:00"
            ),
        )
        phrase_dates = _resolve_phrase_dates(anchor)
        assert phrase_dates.get("yesterday") == date(2025, 12, 24)
        assert phrase_dates.get("tomorrow") == date(2025, 12, 26)


# ---------------------------------------------------------------------------
# _detect_drift
# ---------------------------------------------------------------------------


class TestDetectDrift:
    def test_drift_zero_when_phrase_matches_calendar(self):
        match = PhraseMatch(
            chapter="01-test",
            line=10,
            phrase="yesterday",
            snippet="...yesterday...",
            implied_date=date(2025, 12, 24),
        )
        calendar = TimelineCalendar(
            anchor_date=date(2025, 12, 25),
            anchor_story_day=1,
            events=[
                CalendarEvent(
                    story_day=1,
                    real_date=date(2025, 12, 24),
                    chapter_slug="01-test",
                    key_events="Arrives",
                ),
            ],
        )
        findings = _detect_drift([match], calendar, "01-test")
        assert findings == []

    def test_drift_detected_eight_days(self):
        match = PhraseMatch(
            chapter="22-test",
            line=15,
            phrase="yesterday",
            snippet="...yesterday...",
            implied_date=date(2025, 12, 23),
        )
        calendar = TimelineCalendar(
            anchor_date=date(2025, 12, 1),
            anchor_story_day=1,
            events=[
                CalendarEvent(
                    story_day=15,
                    real_date=date(2025, 12, 15),
                    chapter_slug="22-test",
                    key_events="Climax",
                ),
            ],
        )
        findings = _detect_drift([match], calendar, "22-test")
        assert len(findings) == 1
        assert findings[0].drift_days == 8


# ---------------------------------------------------------------------------
# _find_scene_at_line
# ---------------------------------------------------------------------------


class TestFindSceneAtLine:
    def test_scene_detection_finds_scene_header(self):
        # Build a draft where the scene header is on line 50 and the
        # phrase is on line 78.
        lines = ["filler"] * 49
        lines.append("### Szene 3 — Der Abend (~18:00 → ~19:00)")
        lines.extend(["body"] * 27)  # lines 51..77
        lines.append("yesterday felt heavy")  # line 78
        draft = "\n".join(lines) + "\n"
        scene = _find_scene_at_line(draft, 78)
        assert scene is not None
        assert "Szene 3" in scene

    def test_returns_none_if_no_scene_header(self):
        draft = "Just prose with no scene marker.\nAnother line.\n"
        assert _find_scene_at_line(draft, 2) is None


# ---------------------------------------------------------------------------
# validate_timeline — orchestrator
# ---------------------------------------------------------------------------


class TestValidateTimeline:
    def test_missing_anchor_reported_not_crashed(self, tmp_path: Path):
        # Chapter README without ``## Chapter Timeline`` section.
        book = make_book(
            tmp_path,
            [
                {
                    "slug": "01-no-anchor",
                    "readme": "# Chapter 1\n\nNo timeline section here.\n",
                    "draft": "Some prose without phrases.\n",
                },
            ],
        )
        write_timeline_md(book, MINIMAL_TIMELINE_MD)
        result = validate_timeline(book)
        # Did not crash:
        assert isinstance(result, dict)
        assert "01-no-anchor" in result["missing_anchors"]

    def test_validate_timeline_empty_book(self, tmp_path: Path):
        book = make_book(tmp_path, [])
        result = validate_timeline(book)
        assert result["chapters_checked"] == 0
        assert result["findings"] == []
        assert result["missing_anchors"] == []

    def test_validate_timeline_full_integration(self, tmp_path: Path):
        # Calendar event for chapter 22-test on Dec 15. The chapter
        # README anchors Dec 24, so "yesterday" implies Dec 23. Drift
        # vs the calendar event = 8 days.
        timeline_body = (
            "## Anchor Point\n\n"
            "| Story Start | Real Date | Day of Week | Notes |\n"
            "|---|---|---|---|\n"
            "| Day 1 | Dec 1, 2025 | Monday | Begin |\n\n"
            "## Event Calendar\n\n"
            "| Story Day | Real Date | Day of Week | Chapter | Location | "
            "Key Events | Characters |\n"
            "|---|---|---|---|---|---|---|\n"
            "| Day 15 | Dec 15, 2025 | Monday | 22-test | Library | "
            "Confrontation | Theo |\n"
        )
        chapter_readme = (
            "# Chapter 22\n\n"
            "## Chapter Timeline\n\n"
            "**Start:** Wed Dec 24 ~18:00\n"
            "**End:** Wed Dec 24 ~22:00\n"
        )
        chapter_draft = (
            "Theo paced.\n"
            "He had not slept since yesterday.\n"
            "The hallway felt long.\n"
        )
        book = make_book(
            tmp_path,
            [
                {
                    "slug": "22-test",
                    "readme": chapter_readme,
                    "draft": chapter_draft,
                },
            ],
        )
        write_timeline_md(book, timeline_body)
        result = validate_timeline(book)
        assert result["calendar_built"] is True
        assert result["chapters_checked"] == 1
        findings = result["findings"]
        assert len(findings) == 1
        # Drift should be > 0 (yesterday from Dec 24 = Dec 23, event = Dec 15).
        assert findings[0]["drift_days"] > 0
        assert findings[0]["chapter"] == "22-test"
        assert findings[0]["phrase"] == "yesterday"
