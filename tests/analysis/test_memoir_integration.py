"""Integration tests for the memoir workflow — Issue #68.

Verifies that the key Python tools (continuity_brief, review_brief,
memoir_ethics) handle memoir books correctly across the full Phase 2–4
memoir branching and that fiction books remain unaffected.

Tests are grouped by:
  1. Continuity brief — memoir mode (empty Travel Matrix / Canon Log)
  2. Review brief — memoir mode (same)
  3. Memoir ethics — edge cases (no people dir, all-anon, refused)
  4. Fiction regression — all briefs unchanged after Phase 4 memoir work
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.analysis.memoir_ethics import check_consent
from tools.state.continuity_brief import build_continuity_brief
from tools.state.review_brief import build_review_brief


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_TRAVEL_MATRIX = """\
## Travel Matrix

| From | To | Distance | Transport | Travel Time | Notes |
|------|-----|----------|-----------|-------------|-------|
| City | Village | 80 km | Car | 1h 30min | Highway |
"""

_CANON_LOG = """\
## Established Facts

### Character Facts

| Fact | Established In | Status | Notes |
|------|----------------|--------|-------|
| Alex is left-handed | Ch 1 | ACTIVE | |
"""


def _make_memoir_book(tmp_path: Path, *, slug: str = "test-memoir") -> Path:
    book = tmp_path / slug
    (book / "chapters").mkdir(parents=True)
    (book / "people").mkdir()
    (book / "plot").mkdir()
    (book / "README.md").write_text(
        f'---\ntitle: "Test Memoir"\nbook_category: "memoir"\nslug: "{slug}"\n---\n\n# Test Memoir\n',
        encoding="utf-8",
    )
    return book


def _make_fiction_book(tmp_path: Path, *, slug: str = "test-fiction") -> Path:
    book = tmp_path / slug
    (book / "chapters").mkdir(parents=True)
    (book / "characters").mkdir()
    (book / "plot").mkdir()
    (book / "world").mkdir()
    (book / "README.md").write_text(
        '---\ntitle: "Test Fiction"\nbook_category: "fiction"\n---\n\n# Test Fiction\n',
        encoding="utf-8",
    )
    return book


def _add_chapter(book: Path, slug: str, *, number: int) -> None:
    chapter = book / "chapters" / slug
    chapter.mkdir(parents=True)
    (chapter / "README.md").write_text(
        f'---\ntitle: "Chapter {number}"\nnumber: {number}\nstatus: "Draft"\n---\n\n# Chapter {number}\n',
        encoding="utf-8",
    )
    (chapter / "draft.md").write_text(f"Draft content for chapter {number}.", encoding="utf-8")


def _add_person(
    book: Path,
    slug: str,
    *,
    name: str,
    consent_status: str,
    person_category: str = "private-living-person",
) -> None:
    (book / "people" / f"{slug}.md").write_text(
        "---\n"
        f'name: "{name}"\n'
        f'person_category: "{person_category}"\n'
        f'consent_status: "{consent_status}"\n'
        "---\n\n"
        f"# {name}\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Continuity brief — memoir mode
# ---------------------------------------------------------------------------


class TestContinuityBriefMemoirMode:
    """Memoir books produce empty travel_matrix and canon_log_facts."""

    def test_memoir_no_travel_matrix(self, tmp_path: Path):
        """Memoir books have no world/setting.md — travel_matrix must be empty."""
        book = _make_memoir_book(tmp_path)
        _add_chapter(book, "01-childhood", number=1)

        result = build_continuity_brief(book_root=book, book_slug="test-memoir")

        assert result["travel_matrix"] == []

    def test_memoir_no_canon_log_facts(self, tmp_path: Path):
        """Memoir books have no canon-log.md — canon_log_facts must be empty."""
        book = _make_memoir_book(tmp_path)

        result = build_continuity_brief(book_root=book, book_slug="test-memoir")

        assert result["canon_log_facts"] == []

    def test_memoir_character_index_empty_when_using_people_dir(self, tmp_path: Path):
        """People profiles live in people/ — character_index (characters/ only) is empty.

        The continuity-checker skill reads people-log.md directly for memoir;
        character_index is a fiction artifact populated from characters/.
        """
        book = _make_memoir_book(tmp_path)
        _add_person(book, "maria", name="Maria", consent_status="confirmed-consent")

        result = build_continuity_brief(book_root=book, book_slug="test-memoir")

        assert result["character_index"] == []

    def test_memoir_chapter_timelines_work_normally(self, tmp_path: Path):
        """Chapter timelines are category-agnostic."""
        book = _make_memoir_book(tmp_path)
        _add_chapter(book, "01-childhood", number=1)
        _add_chapter(book, "02-school-years", number=2)

        result = build_continuity_brief(book_root=book, book_slug="test-memoir")

        assert len(result["chapter_timelines"]) == 2

    def test_memoir_continuity_brief_no_errors(self, tmp_path: Path):
        """Memoir scaffold (no world/, no canon-log) degrades gracefully."""
        book = _make_memoir_book(tmp_path)

        result = build_continuity_brief(book_root=book, book_slug="test-memoir")

        assert result["errors"] == []


# ---------------------------------------------------------------------------
# Review brief — memoir mode
# ---------------------------------------------------------------------------


class TestReviewBriefMemoirMode:
    """Review brief for memoir books: empty travel_matrix and canon_log_facts."""

    def test_memoir_no_travel_matrix(self, tmp_path: Path):
        book = _make_memoir_book(tmp_path)
        _add_chapter(book, "01-start", number=1)

        result = build_review_brief(book_root=book, book_slug="test-memoir", chapter_slug="01-start")

        assert result["travel_matrix"] == []

    def test_memoir_no_canon_log_facts(self, tmp_path: Path):
        book = _make_memoir_book(tmp_path)
        _add_chapter(book, "01-start", number=1)

        result = build_review_brief(book_root=book, book_slug="test-memoir", chapter_slug="01-start")

        assert result["canon_log_facts"] == []

    def test_memoir_review_brief_no_errors(self, tmp_path: Path):
        book = _make_memoir_book(tmp_path)
        _add_chapter(book, "01-start", number=1)

        result = build_review_brief(book_root=book, book_slug="test-memoir", chapter_slug="01-start")

        assert result["errors"] == []

    def test_memoir_review_brief_has_all_keys(self, tmp_path: Path):
        book = _make_memoir_book(tmp_path)
        _add_chapter(book, "01-start", number=1)

        result = build_review_brief(book_root=book, book_slug="test-memoir", chapter_slug="01-start")

        for key in ("travel_matrix", "canon_log_facts", "tonal_rules", "errors"):
            assert key in result


# ---------------------------------------------------------------------------
# Memoir ethics — edge cases
# ---------------------------------------------------------------------------


class TestMemoirEthicsEdgeCases:
    """Edge cases for check_consent() not covered by test_memoir_ethics.py."""

    def test_no_people_directory_returns_pass(self, tmp_path: Path):
        """No people/ directory → PASS with zero people."""
        book = tmp_path / "bare-memoir"
        book.mkdir()
        (book / "README.md").write_text(
            '---\ntitle: "Bare"\nbook_category: "memoir"\nslug: "bare"\n---\n',
            encoding="utf-8",
        )

        result = check_consent(book)

        assert result["overall"] == "PASS"
        assert result["people"] == []

    def test_empty_people_directory_returns_pass(self, tmp_path: Path):
        """people/ exists but contains no person files → PASS."""
        book = _make_memoir_book(tmp_path)

        result = check_consent(book)

        assert result["overall"] == "PASS"
        assert result["people"] == []

    def test_all_anonymized_or_not_required_returns_pass(self, tmp_path: Path):
        """All anonymized/not-required people → overall PASS."""
        book = _make_memoir_book(tmp_path)
        _add_person(
            book,
            "figure-a",
            name="Figure A",
            consent_status="not-required",
            person_category="anonymized-or-composite",
        )
        _add_person(
            book,
            "figure-b",
            name="Figure B",
            consent_status="not-required",
            person_category="anonymized-or-composite",
        )

        result = check_consent(book)

        assert result["overall"] == "PASS"
        assert result["pass_count"] == 2
        assert result["fail_count"] == 0
        assert result["warn_count"] == 0

    def test_refused_person_fails_overall(self, tmp_path: Path):
        """One refused person makes overall FAIL regardless of other people."""
        book = _make_memoir_book(tmp_path)
        _add_person(book, "friend", name="Friend", consent_status="confirmed-consent")
        _add_person(book, "antagonist", name="Antagonist", consent_status="refused")

        result = check_consent(book)

        assert result["overall"] == "FAIL"
        assert result["fail_count"] == 1
        assert result["pass_count"] == 1

    def test_refused_person_verdict_is_fail(self, tmp_path: Path):
        """The refused person's entry carries verdict=FAIL."""
        book = _make_memoir_book(tmp_path)
        _add_person(book, "subject", name="Subject", consent_status="refused")

        result = check_consent(book)

        person = next(p for p in result["people"] if p["name"] == "Subject")
        assert person["verdict"] == "FAIL"

    def test_fiction_raises_value_error(self, tmp_path: Path):
        """check_consent() must raise ValueError on non-memoir books."""
        book = _make_fiction_book(tmp_path)

        with pytest.raises(ValueError, match="memoir"):
            check_consent(book)


# ---------------------------------------------------------------------------
# Fiction regression
# ---------------------------------------------------------------------------


class TestFictionRegressionAfterPhase4:
    """Fiction behavior must be unchanged after all Phase 4 memoir branching work."""

    def test_fiction_continuity_brief_has_travel_matrix(self, tmp_path: Path):
        book = _make_fiction_book(tmp_path)
        (book / "world" / "setting.md").write_text(_TRAVEL_MATRIX, encoding="utf-8")

        result = build_continuity_brief(book_root=book, book_slug="test-fiction")

        assert len(result["travel_matrix"]) == 1
        assert result["travel_matrix"][0]["from"] == "City"

    def test_fiction_continuity_brief_has_canon_log_facts(self, tmp_path: Path):
        book = _make_fiction_book(tmp_path)
        (book / "plot" / "canon-log.md").write_text(_CANON_LOG, encoding="utf-8")

        result = build_continuity_brief(book_root=book, book_slug="test-fiction")

        assert len(result["canon_log_facts"]) == 1

    def test_fiction_review_brief_has_travel_matrix(self, tmp_path: Path):
        book = _make_fiction_book(tmp_path)
        (book / "world" / "setting.md").write_text(_TRAVEL_MATRIX, encoding="utf-8")
        _add_chapter(book, "01-opening", number=1)

        result = build_review_brief(book_root=book, book_slug="test-fiction", chapter_slug="01-opening")

        assert len(result["travel_matrix"]) == 1

    def test_fiction_review_brief_has_canon_log_facts(self, tmp_path: Path):
        book = _make_fiction_book(tmp_path)
        (book / "plot" / "canon-log.md").write_text(_CANON_LOG, encoding="utf-8")
        _add_chapter(book, "01-opening", number=1)

        result = build_review_brief(book_root=book, book_slug="test-fiction", chapter_slug="01-opening")

        assert len(result["canon_log_facts"]) == 1

    def test_fiction_continuity_brief_no_errors(self, tmp_path: Path):
        """Empty fiction book still degrades gracefully."""
        book = _make_fiction_book(tmp_path)

        result = build_continuity_brief(book_root=book, book_slug="test-fiction")

        assert result["errors"] == []
