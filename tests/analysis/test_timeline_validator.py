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
    _extract_month_day,
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

    def test_parse_plot_timeline_extracts_anchor_and_events(self, tmp_path: Path):
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

    def test_parse_plot_timeline_unparseable_file_still_returns_none(self, tmp_path: Path):
        # Pure prose, no anchor of any kind — genuinely nothing to parse.
        book = make_book(tmp_path, [])
        write_timeline_md(book, "# Story Timeline\n\nNothing structured here yet.\n")
        assert parse_plot_timeline(book) is None


# ---------------------------------------------------------------------------
# parse_plot_timeline — Issue #508: Firelight-shaped non-canonical layout
# ---------------------------------------------------------------------------

# Firelight's real plot/timeline.md organises events under narrative
# act/week headings (### nested under ##) instead of a flat "## Event
# Calendar" heading, and expresses the anchor as a bullet, not a table
# row. Both previously caused parse_plot_timeline() to silently return
# None (Issue #508).
FIRELIGHT_SHAPED_TIMELINE_MD = (
    "# Story Timeline\n\n"
    "## Anchor Point\n\n"
    "- **Story Day 1 = Friday, October 18** (late October, as established)\n\n"
    "## Act 1: The Nerd and the Stranger\n\n"
    "### Week 0 (lead-up)\n\n"
    "| Story Day | Real Date | Chapter | Location | Cabin Day |\n"
    "|---|---|---|---|---|\n"
    "| Day 1 | Oct 18, 2025 | 01-arrival | Home | - |\n\n"
    "### Week 1 (the story week)\n\n"
    "| Story Day | Real Date | Chapter | Location | Cabin Day |\n"
    "|---|---|---|---|---|\n"
    "| Day 5 | Oct 22, 2025 | 05-cabin | Cabin | Day 1 |\n"
    "| Day 6 | Oct 23, 2025 | 06-fire | Cabin | Day 2 |\n"
)


class TestParsePlotTimelineFirelightShape:
    def test_act_week_headings_and_bullet_anchor_parsed(self, tmp_path: Path):
        book = make_book(tmp_path, [])
        write_timeline_md(book, FIRELIGHT_SHAPED_TIMELINE_MD)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 10, 18)
        assert calendar.anchor_story_day == 1
        assert len(calendar.events) == 3
        assert calendar.events[0].chapter_slug == "01-arrival"
        assert calendar.events[0].real_date == date(2025, 10, 18)
        assert calendar.events[1].chapter_slug == "05-cabin"
        assert calendar.events[1].real_date == date(2025, 10, 22)
        assert calendar.events[2].chapter_slug == "06-fire"
        assert calendar.events[2].real_date == date(2025, 10, 23)

    def test_sub_heading_does_not_reset_top_level_section(self, tmp_path: Path):
        # A ### sub-heading must not drop back to "no section" and
        # discard the table that follows it — regression for the
        # `stripped.startswith("##")` bug matching *both* "##" and "###".
        body = (
            "## Event Calendar\n\n"
            "### Week 1\n\n"
            "| Story Day | Real Date | Day of Week | Chapter | Location | "
            "Key Events | Characters |\n"
            "|---|---|---|---|---|---|---|\n"
            "| Day 1 | Dec 25, 2025 | Thursday | 01-x | Home | Arrives | Theo |\n\n"
            "## Anchor Point\n\n"
            "| Story Start | Real Date | Day of Week | Notes |\n"
            "|---|---|---|---|\n"
            "| Day 1 | Dec 25, 2025 | Thursday | Begin |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert len(calendar.events) == 1
        assert calendar.events[0].chapter_slug == "01-x"

    def test_bullet_anchor_year_inferred_from_matching_story_day_event(self, tmp_path: Path):
        # Anchor bullet has no year — must be inferred from the event
        # sharing the same story day, not left as an unresolved None.
        body = (
            "## Anchor Point\n\n"
            "- Story Day 1 = Friday, October 18\n\n"
            "## Act 1\n\n"
            "| Story Day | Real Date | Chapter |\n"
            "|---|---|---|\n"
            "| Day 1 | Oct 18, 2025 | 01-x |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 10, 18)

    def test_bullet_anchor_with_explicit_year_used_directly(self, tmp_path: Path):
        body = "## Anchor Point\n\n- Story Day 1 = Friday, October 18, 2025\n"
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 10, 18)
        assert calendar.anchor_story_day == 1

    def test_table_anchor_row_still_wins_over_bullet_anchor(self, tmp_path: Path):
        # If a table anchor row is present, it takes precedence over any
        # bullet text — bullets are a fallback, not an override.
        body = (
            "## Anchor Point\n\n"
            "| Story Start | Real Date | Day of Week | Notes |\n"
            "|---|---|---|---|\n"
            "| Day 1 | Dec 1, 2025 | Monday | Begin |\n\n"
            "- Story Day 1 = Friday, October 18, 2099\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 12, 1)

    def test_bullet_anchor_without_weekday_still_parsed(self, tmp_path: Path):
        # Weekday is a common but not mandatory part of the phrasing —
        # dropping it must not silently fail like the bug this fixes.
        body = "## Anchor Point\n\n- Story Day 1 = October 18, 2025\n"
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 10, 18)

    def test_story_day_column_not_shadowed_by_unrelated_day_column(self, tmp_path: Path):
        # A "Cabin Day" column appearing before "Story Day" in the header
        # must not be mistaken for the story-day column.
        body = (
            "## Anchor Point\n\n"
            "- Story Day 1 = Friday, October 18, 2025\n\n"
            "## Act 1\n\n"
            "| Real Date | Cabin Day | Story Day | Chapter |\n"
            "|---|---|---|---|\n"
            "| Oct 18, 2025 | - | Day 1 | 01-x |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.events[0].story_day == 1

    def test_bullet_anchor_year_inferred_from_earliest_event_not_file_order(self, tmp_path: Path):
        # No event shares the anchor's story day, so the year must come
        # from the chronologically earliest event, not whichever event
        # happens to appear first in the file.
        body = (
            "## Anchor Point\n\n"
            "- Story Day 1 = Friday, October 18\n\n"
            "## Act 1\n\n"
            "| Story Day | Real Date | Chapter |\n"
            "|---|---|---|\n"
            "| Day 9 | Jan 5, 2026 | 09-flashforward |\n"
            "| Day 2 | Oct 19, 2025 | 02-x |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 10, 18)

    def test_anchor_table_column_order_not_hardcoded(self, tmp_path: Path):
        # Real Date before Story Start — must still resolve via header
        # names rather than the canonical column positions.
        body = (
            "## Anchor Point\n\n"
            "| Real Date | Story Start | Notes |\n"
            "|---|---|---|\n"
            "| Dec 1, 2025 | Day 1 | Begin |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 12, 1)
        assert calendar.anchor_story_day == 1

    def test_prose_mentioning_a_rejected_anchor_does_not_shadow_the_real_bullet(
        self, tmp_path: Path
    ):
        # Only actual list items are scanned for the anchor bullet — a
        # prose sentence discussing a rejected date must not win.
        body = (
            "## Anchor Point\n\n"
            "Originally we considered Story Day 1 = Monday, September 1, "
            "but rejected it.\n"
            "- Story Day 1 = Friday, October 18, 2025\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 10, 18)

    def test_bullet_anchor_with_year_preferred_over_earlier_yearless_bullet(
        self, tmp_path: Path
    ):
        # A later, more precise bullet (with an explicit year) wins over
        # an earlier vaguer one — not simple first-match-in-file-order.
        body = (
            "## Anchor Point\n\n"
            "- Story Day 1 = Friday, October 18\n"
            "- Precisely: Story Day 1 = October 18, 2025\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 10, 18)

    def test_anchor_table_with_chapter_column_still_classified_as_anchor(
        self, tmp_path: Path
    ):
        # A "story start" column must win over an incidental "chapter"
        # column in the same table — the more specific signal decides.
        body = (
            "## Anchor Point\n\n"
            "| Story Start | Real Date | Day of Week | First Chapter |\n"
            "|---|---|---|---|\n"
            "| Day 1 | Dec 1, 2025 | Monday | 01-x |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 12, 1)

    def test_bold_anchor_table_header_still_classified(self, tmp_path: Path):
        body = (
            "## Anchor Point\n\n"
            "| **Story Start** | **Real Date** | **Day of Week** | **Notes** |\n"
            "|---|---|---|---|\n"
            "| Day 1 | Dec 1, 2025 | Monday | Begin |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 12, 1)

    def test_foreign_date_chapter_table_not_ingested_as_events(self, tmp_path: Path):
        # A revision log has a date + chapter column but no story-day
        # column — it must not be mistaken for the Event Calendar.
        body = (
            "## Anchor Point\n\n"
            "- Story Day 1 = Friday, October 18, 2025\n\n"
            "## Revision Log\n\n"
            "| Date | Chapter | Change |\n"
            "|---|---|---|\n"
            "| 2026-03-04 | 01-x | Rewrote scene 2 |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.events == []

    def test_fenced_example_table_not_ingested_as_events(self, tmp_path: Path):
        # A documentation example embedded in a fenced code block must
        # not be read as live timeline data.
        body = (
            "## Anchor Point\n\n"
            "- Story Day 1 = Friday, October 18, 2025\n\n"
            "## Example\n\n"
            "```markdown\n"
            "| Story Day | Real Date | Chapter |\n"
            "|---|---|---|\n"
            "| Day 1 | Jan 1, 1999 | 00-example |\n"
            "```\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.events == []

    def test_bullet_anchor_daynum_does_not_swallow_year_digits(self, tmp_path: Path):
        # "October 2025" has no day-of-month — must not misread "20" as
        # the day and "25" as a truncated year.
        body = "## Anchor Point\n\n- Story Day 1 = October 2025\n"
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        assert parse_plot_timeline(book) is None

    def test_anchor_year_inference_uses_earliest_matching_event_not_file_order(
        self, tmp_path: Path
    ):
        # Two events share the anchor's story day; the earlier real date
        # must win, not whichever row appears first in the file.
        body = (
            "## Anchor Point\n\n"
            "- Story Day 1 = Friday, October 18\n\n"
            "## Act 1\n\n"
            "| Story Day | Real Date | Chapter |\n"
            "|---|---|---|\n"
            "| Day 1 | Oct 18, 2099 | 01-flashforward |\n"
            "| Day 1 | Oct 18, 2025 | 01-x |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 10, 18)

    def test_table_anchor_wins_over_bullet_anchor_regardless_of_order(self, tmp_path: Path):
        # Bullet appears BEFORE the table this time — the table row must
        # still win, not just "whichever comes first in the file".
        body = (
            "## Anchor Point\n\n"
            "- Story Day 1 = Friday, October 18, 2099\n\n"
            "| Story Start | Real Date | Day of Week | Notes |\n"
            "|---|---|---|---|\n"
            "| Day 1 | Dec 1, 2025 | Monday | Begin |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date == date(2025, 12, 1)


# ---------------------------------------------------------------------------
# parse_plot_timeline — Issue #509: year-less, weekday-tagged timelines
# ---------------------------------------------------------------------------

# Mirrors the real series/blood-and-binary/firelight/plot/timeline.md shape:
# no year anywhere (not even in the anchor bullet), "Day | Date | Chapter |
# Events" headers instead of "Story Day"/"Real Date", a Cabin Day table with
# bold, merged weekday+date cells, and later tables where the Date column is
# empty and the weekday+date is merged into the Day cell instead. Also
# exercises the Dec -> Jan year wrap.
YEARLESS_TIMELINE_MD = (
    "# Story Timeline\n\n"
    "## Anchor Point\n"
    "- **Story Day 1 = Friday, October 18** (late October, as established)\n\n"
    "## Act 1: The Nerd and the Stranger\n\n"
    "### Week 0 (lead-up)\n"
    "| Day | Date | Chapter | Events |\n"
    "|-----|------|---------|--------|\n"
    "| Mon | Oct 14 | 01-lead-up | Theo at work. |\n\n"
    "### Week 1 (the story week)\n\n"
    "| Day | Date | Cabin Day | Chapter | Events |\n"
    "|-----|------|-----------|---------|--------|\n"
    "| **Fri** | **Oct 18** | — | 02-arrival | Theo drives to the campsite. |\n"
    "| **Sat** | **Oct 19** | **Day 1** | 03-storm | Storm hits, Theo falls. |\n\n"
    "### Weeks 3-6\n\n"
    "| Day | Date | Chapter | Events |\n"
    "|-----|------|---------|--------|\n"
    "| Sat Nov 16 | | 10-confrontation | Kevin confrontation. |\n\n"
    "## Act 3: Fire and Ash\n\n"
    "| Day | Date | Chapter | Events |\n"
    "|-----|------|---------|--------|\n"
    "| ~Jan 3 | | 32-funeral | Sera's funeral. |\n"
)


class TestParsePlotTimelineYearless509:
    def test_real_firelight_shape_builds_a_calendar(self, tmp_path: Path):
        book = make_book(tmp_path, [])
        write_timeline_md(book, YEARLESS_TIMELINE_MD)
        calendar = parse_plot_timeline(book)
        assert calendar is not None

    def test_anchor_resolved_without_any_year_in_the_document(self, tmp_path: Path):
        book = make_book(tmp_path, [])
        write_timeline_md(book, YEARLESS_TIMELINE_MD)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_date.month == 10
        assert calendar.anchor_date.day == 18
        assert calendar.anchor_story_day == 1

    def test_events_extracted_from_both_date_and_merged_day_cells(self, tmp_path: Path):
        # "Oct 14" comes from a plain Date cell; "Oct 19"/"Nov 16"/"Jan 3"
        # come from a Date cell using bold markers or a merged weekday+date
        # Day cell (Date cell empty) — Issue #509.
        book = make_book(tmp_path, [])
        write_timeline_md(book, YEARLESS_TIMELINE_MD)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        by_chapter = {e.chapter_slug: e for e in calendar.events}
        assert set(by_chapter) == {
            "01-lead-up",
            "02-arrival",
            "03-storm",
            "10-confrontation",
            "32-funeral",
        }
        assert (by_chapter["01-lead-up"].real_date.month, by_chapter["01-lead-up"].real_date.day) == (10, 14)
        assert (by_chapter["02-arrival"].real_date.month, by_chapter["02-arrival"].real_date.day) == (10, 18)
        assert (by_chapter["03-storm"].real_date.month, by_chapter["03-storm"].real_date.day) == (10, 19)
        assert (by_chapter["10-confrontation"].real_date.month, by_chapter["10-confrontation"].real_date.day) == (
            11,
            16,
        )
        assert (by_chapter["32-funeral"].real_date.month, by_chapter["32-funeral"].real_date.day) == (1, 3)

    def test_year_wraps_forward_across_a_december_to_january_transition(self, tmp_path: Path):
        # No event has an explicit year, but the Jan event must still
        # resolve to a *later* year than the Oct/Nov events — otherwise
        # every downstream day-diff (drift detection) would be wrong.
        book = make_book(tmp_path, [])
        write_timeline_md(book, YEARLESS_TIMELINE_MD)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        by_chapter = {e.chapter_slug: e for e in calendar.events}
        assert by_chapter["32-funeral"].real_date.year > by_chapter["10-confrontation"].real_date.year
        assert by_chapter["32-funeral"].real_date > by_chapter["10-confrontation"].real_date

    def test_story_day_backfilled_from_date_offset_when_column_absent(self, tmp_path: Path):
        # None of these tables have a Story Day column at all — story_day
        # must be derived from the date's offset to the anchor, not left
        # at a bogus 0.
        book = make_book(tmp_path, [])
        write_timeline_md(book, YEARLESS_TIMELINE_MD)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        by_chapter = {e.chapter_slug: e for e in calendar.events}
        # Anchor = Oct 18 = story day 1 -> Oct 19 = story day 2.
        assert by_chapter["03-storm"].story_day == 2

    def test_story_day_zero_bullet_normalized_consistently_for_backfill_and_anchor(
        self, tmp_path: Path
    ):
        # A "Story Day 0" bullet is falsy — the backfill offset for
        # events with no Story Day column of their own must use the
        # same normalized value (0 -> 1) as the returned calendar's
        # anchor_story_day, not the raw pre-normalization 0.
        body = (
            "## Anchor Point\n"
            "- Story Day 0 = Friday, October 18\n\n"
            "## Act 1\n\n"
            "| Day | Date | Chapter | Events |\n"
            "|-----|------|---------|--------|\n"
            "| Sat | Oct 19 | 01-x | Next day. |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.anchor_story_day == 1
        assert calendar.events[0].story_day == 2

    def test_day_cell_range_used_when_date_cell_holds_a_duration_not_a_date(
        self, tmp_path: Path
    ):
        # A real recurring shape in firelight/plot/timeline.md: the Date
        # cell holds a plain-English duration ("~2 weeks") instead of a
        # date, with the actual date living in the Day cell as a range
        # ("Nov 1-14") — the fallback must still extract Nov 1 from the
        # Day cell rather than give up because the Date cell isn't a date.
        body = (
            "## Anchor Point\n"
            "- Story Day 1 = Friday, October 18\n\n"
            "## Act 1\n\n"
            "| Day | Date | Chapter | Events |\n"
            "|-----|------|---------|--------|\n"
            "| Nov 1-14 | ~2 weeks | 09-orbit | Kael and Theo orbit each other. |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert len(calendar.events) == 1
        assert calendar.events[0].real_date.month == 11
        assert calendar.events[0].real_date.day == 1

    def test_small_out_of_order_table_does_not_trigger_a_spurious_year_bump(
        self, tmp_path: Path
    ):
        # A lead-up table listed textually *after* the anchor bullet but
        # chronologically *before* it, one month earlier — must not be
        # mistaken for a Dec -> Jan wrap (the month only drops by 1, far
        # short of a real wrap) and bumped into a later synthetic year.
        body = (
            "## Anchor Point\n"
            "- Story Day 1 = Friday, November 18\n\n"
            "## Act 1\n\n"
            "| Day | Date | Chapter | Events |\n"
            "|-----|------|---------|--------|\n"
            "| Mon | Oct 14 | 00-lead-up | Gear shopping. |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        event = calendar.events[0]
        assert event.real_date.year == calendar.anchor_date.year
        # The backward step happened but wasn't a real wrap — recorded
        # for callers to gauge confidence, not silently absorbed.
        assert calendar.out_of_order_steps == 1
        assert event.real_date.month == 10

    def test_revision_log_style_table_still_not_ingested_as_events(self, tmp_path: Path):
        # A Date+Chapter table without any Day column (e.g. a revision
        # log) must still be excluded even under the year-less fallback.
        body = (
            "## Anchor Point\n"
            "- Story Day 1 = October 18\n\n"
            "## Revision Log\n\n"
            "| Date | Chapter | Change |\n"
            "|---|---|---|\n"
            "| Mar 4 | 01-x | Rewrote scene 2 |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.events == []

    def test_real_date_display_never_asserts_a_fabricated_year(self, tmp_path: Path):
        book = make_book(tmp_path, [])
        write_timeline_md(book, YEARLESS_TIMELINE_MD)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        event = next(e for e in calendar.events if e.chapter_slug == "02-arrival")
        d = event.to_dict()
        assert d["real_date_display"] == "Oct 18"
        assert "real_date" in d  # ISO date still present for internal use

    def test_synthetic_year_flag_set_when_a_year_had_to_be_synthesized(self, tmp_path: Path):
        book = make_book(tmp_path, [])
        write_timeline_md(book, YEARLESS_TIMELINE_MD)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        assert calendar.synthetic_year is True

    def test_event_row_with_its_own_explicit_year_is_not_overwritten(self, tmp_path: Path):
        # Only the anchor bullet is year-less — the event rows state
        # their own years, which must be honored as-is rather than
        # discarded in favor of the synthetic counter (a book need not
        # be year-less everywhere just because the anchor bullet is).
        body = (
            "## Anchor Point\n"
            "- Story Day 1 = Friday, October 18\n\n"
            "## Act 1\n\n"
            "| Day | Date | Chapter | Events |\n"
            "|-----|------|---------|--------|\n"
            "| Fri | Oct 18, 2025 | 02-arrival | Arrival. |\n"
            "| Sat | Jan 3, 2026 | 32-funeral | Funeral. |\n"
        )
        book = make_book(tmp_path, [])
        write_timeline_md(book, body)
        calendar = parse_plot_timeline(book)
        assert calendar is not None
        by_chapter = {e.chapter_slug: e for e in calendar.events}
        assert by_chapter["02-arrival"].real_date == date(2025, 10, 18)
        assert by_chapter["32-funeral"].real_date == date(2026, 1, 3)

    def test_drift_detection_reprojects_a_synthetic_event_year(self, tmp_path: Path):
        # Issue #509 H1: a synthetic event year (e.g. year 1) must not
        # be diffed directly against a chapter README's real-year
        # anchor — that would report a ~700000-day drift for what's
        # actually a same-day match. Mirrors the shape of the earlier
        # fixtures in this file (dir-slug chapter names), which is
        # exactly what triggered the false positive before the fix.
        book = make_book(
            tmp_path,
            [
                {
                    "slug": "02-arrival",
                    "readme": (
                        "# Chapter 2\n\n## Chapter Timeline\n"
                        "**Start:** Fri Oct 18 ~09:00\n**End:** Fri Oct 18 ~22:00\n"
                    ),
                    "draft": "Theo remembered yesterday, when everything was still normal.\n",
                },
            ],
        )
        write_timeline_md(book, YEARLESS_TIMELINE_MD)
        result = validate_timeline(book)
        assert result["calendar_built"] is True
        for finding in result["findings"]:
            assert finding["drift_days"] < 30

    def test_extract_month_day_rejects_month_and_year_without_a_day(self):
        # M1 hardening: "Oct 2025" (year, no day-of-month) must not be
        # misread as day 20 of an unstated year — same guard as
        # _ANCHOR_BULLET_RE's (?!\d) lookahead (Issue #508).
        assert _extract_month_day("Oct 2025") is None
        assert _extract_month_day("October 2025") is None

    def test_extract_month_day_does_not_match_inside_unrelated_words(self):
        # "Marathon 5" / "Decided 3 times" must not be misread as
        # March 5 / December 3 via a bare \w* month tail.
        assert _extract_month_day("Marathon 5") is None
        assert _extract_month_day("Decided 3 times") is None
        assert _extract_month_day("Mayor 12") is None

    def test_extract_month_day_captures_an_explicit_year(self):
        assert _extract_month_day("Oct 18, 2025") == (10, 18, 2025)
        assert _extract_month_day("Oct 18") == (10, 18, None)


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
        draft = "Line one.\nLine two with yesterday in it.\nLine three.\n"
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
            start=TimePoint(day_of_week="Thu", month="Dec", day=25, time="08:00"),
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
            "# Chapter 22\n\n## Chapter Timeline\n\n**Start:** Wed Dec 24 ~18:00\n**End:** Wed Dec 24 ~22:00\n"
        )
        chapter_draft = "Theo paced.\nHe had not slept since yesterday.\nThe hallway felt long.\n"
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
