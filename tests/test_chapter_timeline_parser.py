"""Tests for ``tools.state.chapter_timeline_parser`` — Issue #77.

Loads the last N chapters of a book (review-status or later) as a
structured timeline grid, so chapter-writer can anchor against three
real intra-day grids instead of remembered times.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.state.chapter_timeline_parser import (
    ChapterScene,
    get_recent_chapter_timelines,
    parse_chapter_timeline_grid,
    parse_scenes,
)
from tools.timeline_anchor import TimePoint


# ---------------------------------------------------------------------------
# parse_scenes — extract scene rows from chapter README body
# ---------------------------------------------------------------------------


CH21_BODY = (
    "## Chapter Timeline\n\n"
    "**Start:** Tue Dec 24 ~14:45 (greenhouse)\n"
    "**End:** Tue Dec 24 ~17:30 (library window seat, post-meeting)\n\n"
    "### Szene 1 — Christmas Eve (~14:45 → ~15:50)\n\n"
    "| Time | Event | Notes |\n"
    "|------|-------|-------|\n"
    "| ~14:45 | Theo arrives | greenhouse |\n\n"
    "### Szene 2 — The Library (~15:50 → ~16:00)\n\n"
    "Some prose.\n\n"
    "### Szene 3 — The Meeting (~16:00 → ~16:50)\n"
)

CH19_BODY = (
    "## Chapter Timeline\n\n"
    "**Date:** Tuesday, December 17 (day after Ch 18 arrival)\n\n"
    "### Szene 1 — The Kitchen, Again (~08:30 → ~08:55)\n\n"
    "| Time | Event |\n"
    "|------|-------|\n"
    "| ~08:30 | Theo wakes |\n\n"
    "### Szene 2 — Who She Was (~08:55 → ~09:45)\n"
)


class TestParseScenes:
    def test_parses_three_scenes_with_times(self):
        scenes = parse_scenes(CH21_BODY)
        assert len(scenes) == 3
        assert scenes[0] == ChapterScene(
            name="Christmas Eve", start_time="14:45", end_time="15:50",
        )
        assert scenes[1] == ChapterScene(
            name="The Library", start_time="15:50", end_time="16:00",
        )
        assert scenes[2] == ChapterScene(
            name="The Meeting", start_time="16:00", end_time="16:50",
        )

    def test_parses_two_scenes(self):
        scenes = parse_scenes(CH19_BODY)
        assert len(scenes) == 2
        assert scenes[0].name == "The Kitchen, Again"
        assert scenes[1].name == "Who She Was"

    def test_no_scene_headers_returns_empty(self):
        text = (
            "## Chapter Timeline\n\n"
            "**Start:** Tue Dec 24 ~14:45\n"
            "**End:** Tue Dec 24 ~17:30\n"
        )
        assert parse_scenes(text) == []

    def test_accepts_english_scene_keyword(self):
        text = "### Scene 1 — Opening (~08:00 → ~09:00)\n"
        scenes = parse_scenes(text)
        assert len(scenes) == 1
        assert scenes[0].name == "Opening"

    def test_malformed_scene_header_without_times_degrades(self):
        text = "### Szene 1 — Something Important\n"
        scenes = parse_scenes(text)
        # Malformed scenes that lack times should not crash — either
        # skip or capture the name with None times. We accept either,
        # but the parser must not throw.
        assert isinstance(scenes, list)


# ---------------------------------------------------------------------------
# parse_chapter_timeline_grid — full chapter directory loader
# ---------------------------------------------------------------------------


def _make_chapter(
    chapters_root: Path,
    slug: str,
    body: str,
    *,
    status: str = "review",
    title: str | None = None,
    number: int | None = None,
) -> Path:
    chapter = chapters_root / slug
    chapter.mkdir(parents=True)
    extracted_number = int(slug.split("-", 1)[0])
    frontmatter = "---\n"
    if title is not None:
        frontmatter += f"title: \"{title}\"\n"
    frontmatter += f"number: {number if number is not None else extracted_number}\n"
    frontmatter += f"status: {status}\n"
    frontmatter += "---\n\n"
    (chapter / "README.md").write_text(frontmatter + body, encoding="utf-8")
    return chapter


class TestParseChapterTimelineGrid:
    def test_loads_full_grid(self, tmp_path):
        ch = _make_chapter(
            tmp_path, "21-i-forbid-it", CH21_BODY,
            status="review", title="I Forbid It",
        )
        grid = parse_chapter_timeline_grid(ch)
        assert grid is not None
        assert grid.number == 21
        assert grid.slug == "21-i-forbid-it"
        assert grid.title == "I Forbid It"
        assert grid.status == "review"
        assert grid.start == TimePoint("Tue", "Dec", 24, "14:45")
        assert grid.end == TimePoint("Tue", "Dec", 24, "17:30")
        assert len(grid.scenes) == 3

    def test_returns_none_for_missing_readme(self, tmp_path):
        empty = tmp_path / "01-empty"
        empty.mkdir()
        assert parse_chapter_timeline_grid(empty) is None

    def test_chapter_with_only_date_marker_still_parses_scenes(self, tmp_path):
        ch = _make_chapter(
            tmp_path, "19-seras-ghost", CH19_BODY,
            status="review", title="Sera's Ghost",
        )
        grid = parse_chapter_timeline_grid(ch)
        assert grid is not None
        assert grid.number == 19
        assert len(grid.scenes) == 2
        # No **Start:**/**End:** markers, so anchor start/end are None;
        # the scenes carry the intra-day times.
        assert grid.start is None
        assert grid.end is None

    def test_serializes_to_dict(self, tmp_path):
        ch = _make_chapter(
            tmp_path, "21-i-forbid-it", CH21_BODY,
            status="review", title="I Forbid It",
        )
        grid = parse_chapter_timeline_grid(ch)
        assert grid is not None
        payload = grid.to_dict()
        assert payload["number"] == 21
        assert payload["slug"] == "21-i-forbid-it"
        assert payload["title"] == "I Forbid It"
        assert payload["status"] == "review"
        assert payload["start"] == {
            "day_of_week": "Tue", "month": "Dec", "day": 24, "time": "14:45",
        }
        assert payload["scenes"][0] == {
            "name": "Christmas Eve", "start_time": "14:45", "end_time": "15:50",
        }

    def test_grid_is_json_serializable(self, tmp_path):
        ch = _make_chapter(
            tmp_path, "21-i-forbid-it", CH21_BODY, status="review",
        )
        grid = parse_chapter_timeline_grid(ch)
        assert grid is not None
        # Must round-trip via json — no datetime, no Path objects in payload.
        json.dumps(grid.to_dict())


# ---------------------------------------------------------------------------
# get_recent_chapter_timelines — book-level orchestrator
# ---------------------------------------------------------------------------


def _make_book(tmp_path: Path) -> Path:
    book = tmp_path / "book"
    (book / "chapters").mkdir(parents=True)
    return book


class TestGetRecentChapterTimelines:
    def test_returns_three_most_recent_review_chapters(self, tmp_path):
        book = _make_book(tmp_path)
        chapters = book / "chapters"
        for n in range(19, 23):  # 19, 20, 21, 22
            _make_chapter(
                chapters, f"{n:02d}-ch{n}", CH21_BODY,
                status="review", title=f"Chapter {n}", number=n,
            )

        result = get_recent_chapter_timelines(book, n=3)
        assert len(result) == 3
        # Most-recent-first or chronological? Issue example shows 19, 20, 21
        # in chronological order. We follow that.
        assert [g.number for g in result] == [20, 21, 22]

    def test_returns_fewer_when_book_has_fewer_review_chapters(self, tmp_path):
        book = _make_book(tmp_path)
        chapters = book / "chapters"
        _make_chapter(
            chapters, "01-only", CH21_BODY,
            status="review", title="Only One", number=1,
        )

        result = get_recent_chapter_timelines(book, n=3)
        assert len(result) == 1
        assert result[0].number == 1

    def test_returns_empty_for_book_with_no_chapters_dir(self, tmp_path):
        book = tmp_path / "empty-book"
        book.mkdir()
        assert get_recent_chapter_timelines(book, n=3) == []

    def test_returns_empty_for_book_with_no_review_chapters(self, tmp_path):
        book = _make_book(tmp_path)
        chapters = book / "chapters"
        _make_chapter(
            chapters, "01-draft-only", CH21_BODY,
            status="draft", title="Just A Draft", number=1,
        )
        _make_chapter(
            chapters, "02-outline", CH21_BODY,
            status="outline", title="Just An Outline", number=2,
        )

        result = get_recent_chapter_timelines(book, n=3)
        assert result == []

    def test_skips_drafts_and_outlines_in_mixed_status_book(self, tmp_path):
        book = _make_book(tmp_path)
        chapters = book / "chapters"
        # 1, 2 = review (eligible), 3 = draft (skip), 4 = outline (skip),
        # 5, 6 = final (eligible). Last 3 eligible = 2, 5, 6.
        _make_chapter(chapters, "01-rev1", CH21_BODY, status="review", number=1)
        _make_chapter(chapters, "02-rev2", CH21_BODY, status="review", number=2)
        _make_chapter(chapters, "03-draft", CH21_BODY, status="draft", number=3)
        _make_chapter(chapters, "04-out", CH21_BODY, status="outline", number=4)
        _make_chapter(chapters, "05-fin1", CH21_BODY, status="final", number=5)
        _make_chapter(chapters, "06-fin2", CH21_BODY, status="final", number=6)

        result = get_recent_chapter_timelines(book, n=3)
        assert [g.number for g in result] == [2, 5, 6]

    def test_includes_polished_and_final_as_eligible(self, tmp_path):
        book = _make_book(tmp_path)
        chapters = book / "chapters"
        _make_chapter(chapters, "01-rev", CH21_BODY, status="review", number=1)
        _make_chapter(chapters, "02-pol", CH21_BODY, status="polished", number=2)
        _make_chapter(chapters, "03-fin", CH21_BODY, status="final", number=3)

        result = get_recent_chapter_timelines(book, n=3)
        # parse_chapter_readme normalizes statuses: "review" passes
        # through (no canonical form), "polished" → "Polished",
        # "final" → "Final".
        assert [g.status for g in result] == ["review", "Polished", "Final"]

    def test_chapter_with_malformed_timeline_table_is_skipped_gracefully(
        self, tmp_path
    ):
        book = _make_book(tmp_path)
        chapters = book / "chapters"
        _make_chapter(chapters, "01-good", CH21_BODY, status="review", number=1)
        # Malformed: review status, but no Chapter Timeline section at all.
        _make_chapter(
            chapters, "02-no-timeline",
            "# Chapter 2\n\nProse without timeline.\n",
            status="review", number=2,
        )
        _make_chapter(chapters, "03-good", CH21_BODY, status="review", number=3)

        result = get_recent_chapter_timelines(book, n=3)
        # Malformed chapter still appears — it's review-status — but
        # with empty scenes / None anchors. Graceful degrade, no crash.
        assert len(result) == 3
        bad = next(g for g in result if g.number == 2)
        assert bad.start is None
        assert bad.end is None
        assert bad.scenes == []

    def test_default_n_is_three(self, tmp_path):
        book = _make_book(tmp_path)
        chapters = book / "chapters"
        for n in range(1, 6):
            _make_chapter(
                chapters, f"{n:02d}-ch{n}", CH21_BODY,
                status="review", number=n,
            )
        result = get_recent_chapter_timelines(book)
        assert len(result) == 3
        assert [g.number for g in result] == [3, 4, 5]

    def test_book_level_dict_structure(self, tmp_path):
        book = _make_book(tmp_path)
        chapters = book / "chapters"
        _make_chapter(chapters, "01-only", CH21_BODY, status="review", number=1)

        grids = get_recent_chapter_timelines(book, n=3)
        # Wrap into the documented JSON shape: {"chapters": [...]}
        payload = {"chapters": [g.to_dict() for g in grids]}
        json.dumps(payload)  # must round-trip
        assert payload["chapters"][0]["slug"] == "01-only"
