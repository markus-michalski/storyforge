"""Tests for ``tools.timeline_anchor`` — chapter README parser, anchor
computation, day-shift arithmetic, relative-phrase mapping, and the
multi-chapter ``get_story_anchor`` orchestrator.
"""

from __future__ import annotations

from pathlib import Path

from tools.timeline_anchor import (
    ChapterAnchor,
    TimePoint,
    compute_relative_phrase_mapping,
    get_chapter_anchor,
    get_story_anchor,
    parse_chapter_timeline,
    shift_days,
    shift_hours,
)


# ---------------------------------------------------------------------------
# parse_chapter_timeline
# ---------------------------------------------------------------------------


CH22_README = (
    "# Chapter 22: The Night Before\n\n"
    "## Chapter Timeline\n\n"
    "**Start:** Tue Dec 24 ~19:30 (library window seat)\n"
    "**End:** Wed Dec 25 ~07:00 (trailhead, engine cut)\n"
)

CH4_NO_TIME = (
    "## Chapter Timeline\n\n"
    "**Start:** Mon Oct 21\n"
    "**End:** Mon Oct 21\n"
)


class TestParseChapterTimeline:
    def test_parses_start_and_end(self):
        start, end = parse_chapter_timeline(CH22_README)
        assert start == TimePoint(
            day_of_week="Tue", month="Dec", day=24, time="19:30"
        )
        assert end == TimePoint(
            day_of_week="Wed", month="Dec", day=25, time="07:00"
        )

    def test_optional_time(self):
        start, end = parse_chapter_timeline(CH4_NO_TIME)
        assert start == TimePoint(
            day_of_week="Mon", month="Oct", day=21, time=None
        )
        assert end == TimePoint(
            day_of_week="Mon", month="Oct", day=21, time=None
        )

    def test_empty_returns_none(self):
        start, end = parse_chapter_timeline("# Chapter 1\n\nNo timeline.\n")
        assert start is None
        assert end is None

    def test_only_start_present(self):
        text = "## Chapter Timeline\n\n**Start:** Fri Oct 18 ~08:00\n"
        start, end = parse_chapter_timeline(text)
        assert start is not None
        assert end is None

    def test_handles_extra_whitespace(self):
        text = (
            "## Chapter Timeline\n\n"
            "**Start:**     Tue Dec 24    ~19:30 (anything)\n"
        )
        start, _ = parse_chapter_timeline(text)
        assert start == TimePoint(
            day_of_week="Tue", month="Dec", day=24, time="19:30"
        )


# ---------------------------------------------------------------------------
# get_chapter_anchor (filesystem path)
# ---------------------------------------------------------------------------


def _make_chapter(tmp_path: Path, slug: str, readme_text: str) -> Path:
    chapter = tmp_path / slug
    chapter.mkdir(parents=True)
    (chapter / "README.md").write_text(readme_text, encoding="utf-8")
    return chapter


class TestGetChapterAnchor:
    def test_loads_anchor_from_readme(self, tmp_path):
        ch = _make_chapter(tmp_path, "22-the-night-before", CH22_README)
        anchor = get_chapter_anchor(ch)
        assert anchor is not None
        assert anchor.chapter_slug == "22-the-night-before"
        assert anchor.start.day == 24
        assert anchor.end.day == 25

    def test_returns_none_for_missing_readme(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert get_chapter_anchor(empty) is None

    def test_returns_none_for_readme_without_timeline(self, tmp_path):
        ch = _make_chapter(
            tmp_path, "01-x", "# Ch\n\nNo timeline section.\n"
        )
        assert get_chapter_anchor(ch) is None


# ---------------------------------------------------------------------------
# Day-shift arithmetic
# ---------------------------------------------------------------------------


class TestShiftDays:
    def test_yesterday_from_tue_dec_24(self):
        tp = TimePoint("Tue", "Dec", 24, "19:30")
        result = shift_days(tp, -1)
        assert result == TimePoint("Mon", "Dec", 23, "19:30")

    def test_tomorrow_from_tue_dec_24(self):
        tp = TimePoint("Tue", "Dec", 24, "19:30")
        result = shift_days(tp, 1)
        assert result == TimePoint("Wed", "Dec", 25, "19:30")

    def test_seven_days_back(self):
        tp = TimePoint("Tue", "Dec", 24, "19:30")
        result = shift_days(tp, -7)
        assert result == TimePoint("Tue", "Dec", 17, "19:30")

    def test_cross_month_boundary(self):
        tp = TimePoint("Tue", "Dec", 31, "12:00")
        result = shift_days(tp, 1)
        assert result.month == "Jan"
        assert result.day == 1

    def test_invalid_month_returns_none(self):
        tp = TimePoint("Tue", "Foo", 24)
        assert shift_days(tp, 1) is None

    def test_year_picked_to_match_dow(self):
        # Tue Dec 24 is real in 2024. The shift logic must use a year
        # where the DOW actually matches, otherwise +7 days lands on the
        # wrong DOW.
        tp = TimePoint("Tue", "Dec", 24, "12:00")
        result = shift_days(tp, 7)
        assert result == TimePoint("Tue", "Dec", 31, "12:00")


class TestShiftHours:
    def test_one_hour_back(self):
        tp = TimePoint("Tue", "Dec", 24, "19:30")
        result = shift_hours(tp, -1)
        assert result == TimePoint("Tue", "Dec", 24, "18:30")

    def test_two_hours_forward(self):
        tp = TimePoint("Tue", "Dec", 24, "19:30")
        result = shift_hours(tp, 2)
        assert result == TimePoint("Tue", "Dec", 24, "21:30")

    def test_crosses_midnight(self):
        tp = TimePoint("Tue", "Dec", 24, "23:30")
        result = shift_hours(tp, 1)
        assert result == TimePoint("Wed", "Dec", 25, "00:30")


# ---------------------------------------------------------------------------
# Relative phrase mapping
# ---------------------------------------------------------------------------


class TestRelativePhraseMapping:
    def _ch22_anchor(self) -> ChapterAnchor:
        return ChapterAnchor(
            chapter_slug="22-the-night-before",
            start=TimePoint("Tue", "Dec", 24, "19:30"),
            end=TimePoint("Wed", "Dec", 25, "07:00"),
        )

    def test_yesterday_resolves_to_prev_day(self):
        mapping = compute_relative_phrase_mapping(self._ch22_anchor())
        assert "Mon Dec 23" in mapping["yesterday"]

    def test_tomorrow_resolves_to_next_day(self):
        mapping = compute_relative_phrase_mapping(self._ch22_anchor())
        assert "Wed Dec 25" in mapping["tomorrow"]

    def test_last_night_is_prev_day_night_not_12h_ago(self):
        mapping = compute_relative_phrase_mapping(self._ch22_anchor())
        # Should be "night of Mon Dec 23" — the night before today.
        assert "Mon Dec 23" in mapping["last night"]
        assert "night" in mapping["last night"]

    def test_an_hour_ago_is_one_hour_back(self):
        mapping = compute_relative_phrase_mapping(self._ch22_anchor())
        assert "18:30" in mapping["an hour ago"]

    def test_last_week_is_seven_days_back(self):
        mapping = compute_relative_phrase_mapping(self._ch22_anchor())
        assert "Dec 17" in mapping["last week"]

    def test_no_start_returns_empty(self):
        anchor = ChapterAnchor("01-x", start=None, end=None)
        assert compute_relative_phrase_mapping(anchor) == {}

    def test_this_morning_includes_today(self):
        mapping = compute_relative_phrase_mapping(self._ch22_anchor())
        assert "Tue Dec 24" in mapping["this morning"]
        assert "morning" in mapping["this morning"]


# ---------------------------------------------------------------------------
# Multi-chapter orchestrator
# ---------------------------------------------------------------------------


def _make_book_with_chapters(tmp_path: Path) -> Path:
    book = tmp_path / "book"
    chapters = book / "chapters"
    chapters.mkdir(parents=True)

    _make_chapter(
        chapters,
        "21-i-forbid-it",
        (
            "## Chapter Timeline\n\n"
            "**Start:** Tue Dec 24 ~14:45\n"
            "**End:** Tue Dec 24 ~17:30\n"
        ),
    )
    _make_chapter(chapters, "22-the-night-before", CH22_README)
    return book


class TestGetStoryAnchor:
    def test_returns_current_and_previous(self, tmp_path):
        book = _make_book_with_chapters(tmp_path)
        story = get_story_anchor(book, "22-the-night-before")
        assert story.current is not None
        assert story.current.chapter_slug == "22-the-night-before"
        assert story.previous is not None
        assert story.previous.chapter_slug == "21-i-forbid-it"

    def test_relative_mapping_uses_current_chapter_start(self, tmp_path):
        book = _make_book_with_chapters(tmp_path)
        story = get_story_anchor(book, "22-the-night-before")
        # Anchor is Tue Dec 24 19:30 → "yesterday" = Mon Dec 23.
        assert "Mon Dec 23" in story.relative_phrase_mapping["yesterday"]

    def test_falls_back_to_prev_end_if_current_lacks_timeline(
        self, tmp_path
    ):
        book = tmp_path / "book"
        chapters = book / "chapters"
        chapters.mkdir(parents=True)
        _make_chapter(
            chapters,
            "01-prev",
            (
                "## Chapter Timeline\n\n"
                "**Start:** Mon Oct 21 ~08:00\n"
                "**End:** Mon Oct 21 ~17:00\n"
            ),
        )
        # Current chapter has no Chapter Timeline yet (still drafting).
        _make_chapter(
            chapters, "02-current", "# Chapter 2\n\nNo timeline yet.\n"
        )

        story = get_story_anchor(book, "02-current")
        assert story.current is None
        # Mapping derived from previous chapter's end.
        assert story.relative_phrase_mapping
        assert "yesterday" in story.relative_phrase_mapping

    def test_serializes_to_dict(self, tmp_path):
        book = _make_book_with_chapters(tmp_path)
        story = get_story_anchor(book, "22-the-night-before")
        payload = story.to_dict()
        assert "current_chapter" in payload
        assert "previous_chapter" in payload
        assert "available_relative_phrases" in payload
        assert "yesterday" in payload["available_relative_phrases"]

    def test_no_chapters_returns_empty(self, tmp_path):
        book = tmp_path / "book"
        (book / "chapters").mkdir(parents=True)
        story = get_story_anchor(book, "no-such-chapter")
        assert story.current is None
        assert story.previous is None
        assert story.relative_phrase_mapping == {}
