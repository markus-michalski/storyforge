"""Tests for tools.state.continuity_brief — Issue #100.

Verifies that build_continuity_brief() returns the correct structured
payload including canonical_calendar, travel_matrix, canon_log_facts,
character_index, and chapter_timelines for ALL chapters.
"""

from __future__ import annotations

from pathlib import Path

from tools.state.continuity_brief import (
    _build_character_index,
    _get_all_chapter_timelines,
    build_continuity_brief,
)
from tests.test_review_brief import (
    CANON_LOG_SAMPLE,
    TRAVEL_MATRIX_SAMPLE,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_book(tmp_path: Path) -> tuple[Path, str]:
    book_slug = "test-book"
    book = tmp_path / book_slug
    (book / "chapters").mkdir(parents=True)
    (book / "characters").mkdir()
    (book / "plot").mkdir()
    (book / "world").mkdir()
    (book / "README.md").write_text(
        '---\ntitle: "Test Book"\nauthor: ""\n---\n\n# Test Book\n',
        encoding="utf-8",
    )
    return book, book_slug


def _add_chapter(
    book: Path,
    slug: str,
    *,
    number: int,
    status: str = "Draft",
) -> Path:
    chapter = book / "chapters" / slug
    chapter.mkdir(parents=True)
    (chapter / "README.md").write_text(
        f'---\ntitle: "Chapter {number}"\nnumber: {number}\n'
        f'status: "{status}"\n---\n\n# Chapter {number}\n',
        encoding="utf-8",
    )
    (chapter / "draft.md").write_text(
        f"Draft content for chapter {number}.", encoding="utf-8"
    )
    return chapter


def _add_character(
    book: Path,
    slug: str,
    *,
    name: str,
    role: str = "supporting",
) -> None:
    (book / "characters" / f"{slug}.md").write_text(
        f'---\nname: "{name}"\nrole: "{role}"\n---\n\n# {name}\n',
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Unit tests — _build_character_index
# ---------------------------------------------------------------------------


def test_build_character_index_finds_all_characters(tmp_path):
    book, _ = _make_book(tmp_path)
    _add_character(book, "marcus", name="Marcus", role="protagonist")
    _add_character(book, "lena", name="Lena", role="supporting")

    result = _build_character_index(book)
    assert len(result) == 2


def test_build_character_index_correct_fields(tmp_path):
    book, _ = _make_book(tmp_path)
    _add_character(book, "marcus", name="Marcus", role="protagonist")

    result = _build_character_index(book)
    assert result[0]["slug"] == "marcus"
    assert result[0]["name"] == "Marcus"
    assert result[0]["role"] == "protagonist"


def test_build_character_index_skips_index_md(tmp_path):
    book, _ = _make_book(tmp_path)
    _add_character(book, "marcus", name="Marcus", role="protagonist")
    (book / "characters" / "INDEX.md").write_text(
        "# Characters Index\n", encoding="utf-8"
    )

    result = _build_character_index(book)
    slugs = [c["slug"] for c in result]
    assert "INDEX" not in slugs
    assert "marcus" in slugs


def test_build_character_index_empty_chars_dir(tmp_path):
    book, _ = _make_book(tmp_path)
    result = _build_character_index(book)
    assert result == []


def test_build_character_index_missing_chars_dir(tmp_path):
    book, _ = _make_book(tmp_path)
    (book / "characters").rmdir()
    result = _build_character_index(book)
    assert result == []


# ---------------------------------------------------------------------------
# Unit tests — _get_all_chapter_timelines
# ---------------------------------------------------------------------------


def test_get_all_chapter_timelines_includes_all_statuses(tmp_path):
    """Unlike get_recent_chapter_timelines, all statuses must be included."""
    book, _ = _make_book(tmp_path)
    _add_chapter(book, "01-opening", number=1, status="Outline")
    _add_chapter(book, "02-draft", number=2, status="Draft")
    _add_chapter(book, "03-review", number=3, status="Revision")

    result = _get_all_chapter_timelines(book)
    assert len(result) == 3


def test_get_all_chapter_timelines_correct_order(tmp_path):
    book, _ = _make_book(tmp_path)
    _add_chapter(book, "01-opening", number=1)
    _add_chapter(book, "02-conflict", number=2)
    _add_chapter(book, "03-resolution", number=3)

    result = _get_all_chapter_timelines(book)
    numbers = [r["number"] for r in result]
    assert numbers == sorted(numbers)


def test_get_all_chapter_timelines_empty_book(tmp_path):
    book, _ = _make_book(tmp_path)
    result = _get_all_chapter_timelines(book)
    assert result == []


# ---------------------------------------------------------------------------
# Integration tests — build_continuity_brief
# ---------------------------------------------------------------------------


def test_build_continuity_brief_returns_all_expected_keys(tmp_path):
    book, slug = _make_book(tmp_path)

    result = build_continuity_brief(book_root=book, book_slug=slug)

    expected_keys = {
        "book_slug",
        "canonical_calendar",
        "travel_matrix",
        "canon_log_facts",
        "character_index",
        "chapter_timelines",
        "errors",
    }
    assert expected_keys <= set(result.keys())


def test_build_continuity_brief_no_errors_empty_book(tmp_path):
    book, slug = _make_book(tmp_path)

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["errors"] == []


def test_build_continuity_brief_travel_matrix_populated(tmp_path):
    book, slug = _make_book(tmp_path)
    (book / "world" / "setting.md").write_text(TRAVEL_MATRIX_SAMPLE, encoding="utf-8")

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert len(result["travel_matrix"]) == 2


def test_build_continuity_brief_canon_log_facts_populated(tmp_path):
    book, slug = _make_book(tmp_path)
    (book / "plot" / "canon-log.md").write_text(CANON_LOG_SAMPLE, encoding="utf-8")

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert len(result["canon_log_facts"]) == 3


def test_build_continuity_brief_character_index_populated(tmp_path):
    book, slug = _make_book(tmp_path)
    _add_character(book, "marcus", name="Marcus", role="protagonist")
    _add_character(book, "lena", name="Lena")

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert len(result["character_index"]) == 2
    names = {c["name"] for c in result["character_index"]}
    assert names == {"Marcus", "Lena"}


def test_build_continuity_brief_chapter_timelines_all_statuses(tmp_path):
    """Chapter timelines must include ALL chapters regardless of status."""
    book, slug = _make_book(tmp_path)
    _add_chapter(book, "01-opening", number=1, status="Outline")
    _add_chapter(book, "02-draft", number=2, status="Draft")
    _add_chapter(book, "03-done", number=3, status="Revision")

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert len(result["chapter_timelines"]) == 3


def test_build_continuity_brief_missing_optional_files_graceful(tmp_path):
    """No setting.md, no canon-log.md → empty lists, no errors."""
    book, slug = _make_book(tmp_path)

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["canonical_calendar"] == []
    assert result["travel_matrix"] == []
    assert result["canon_log_facts"] == []
    assert result["errors"] == []
