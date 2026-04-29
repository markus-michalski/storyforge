"""Tests for callback_validator.py — verify_callbacks() and parse_callback_register().

TDD Red phase: all tests must fail before implementation exists.

Covers:
- parse_callback_register: empty section, plain name, bold name,
  expected-return annotation, must-not-forget marker, added-date stripping
- _extract_search_terms: phrase and word-level terms
- verify_callbacks: satisfied / deferred / potentially_dropped status paths,
  expected-return deadline, must-not-forget + silence, no chapters
"""

from __future__ import annotations

from pathlib import Path

from tools.analysis.callback_validator import (
    _extract_search_terms,
    parse_callback_register,
    verify_callbacks,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CALLBACKS_EMPTY = """\
# Test Book

## Callback Register

<!-- CALLBACKS:START -->
<!-- CALLBACKS:END -->
"""

CALLBACKS_PLAIN = """\
# Test Book

## Callback Register

<!-- CALLBACKS:START -->
- Gary the cat _(added 2026-01-15)_
<!-- CALLBACKS:END -->
"""

CALLBACKS_BOLD = """\
# Test Book

## Callback Register

<!-- CALLBACKS:START -->
- **Gary the cat** _(added 2026-01-15)_
- **French press** _(added 2026-01-16)_
<!-- CALLBACKS:END -->
"""

CALLBACKS_FULL_ANNOTATIONS = """\
# Test Book

## Callback Register

<!-- CALLBACKS:START -->
- **Theo's vampire history book** — expected return by Ch 18 (palace scene). _(must not be forgotten)_ _(added 2026-01-17)_
- **Szymborska translation** — a translation project from chapter 9. _(added 2026-01-18)_
- **Gary the cat** _(added 2026-01-15)_
<!-- CALLBACKS:END -->
"""

CALLBACKS_MUST_FORGET_ONLY = """\
# Test Book

## Callback Register

<!-- CALLBACKS:START -->
- **the broken compass** _(must not be forgotten)_ _(added 2026-01-10)_
<!-- CALLBACKS:END -->
"""


def _write_book(
    tmp_path: Path,
    claudemd: str,
    chapters: dict[str, str],
) -> Path:
    """Create minimal book structure for tests."""
    book = tmp_path / "my-book"
    book.mkdir()
    (book / "CLAUDE.md").write_text(claudemd, encoding="utf-8")
    chapters_dir = book / "chapters"
    chapters_dir.mkdir()
    for slug, draft_text in chapters.items():
        ch_dir = chapters_dir / slug
        ch_dir.mkdir()
        (ch_dir / "draft.md").write_text(draft_text, encoding="utf-8")
    return book


# ---------------------------------------------------------------------------
# TestParseCallbackRegister
# ---------------------------------------------------------------------------


class TestParseCallbackRegister:
    def test_empty_section_returns_empty_list(self) -> None:
        entries = parse_callback_register(CALLBACKS_EMPTY)
        assert entries == []

    def test_plain_name_parsed(self) -> None:
        entries = parse_callback_register(CALLBACKS_PLAIN)
        assert len(entries) == 1
        assert entries[0].name == "Gary the cat"

    def test_bold_name_parsed(self) -> None:
        entries = parse_callback_register(CALLBACKS_BOLD)
        assert len(entries) == 2
        names = [e.name for e in entries]
        assert "Gary the cat" in names
        assert "French press" in names

    def test_expected_return_ch_parsed(self) -> None:
        entries = parse_callback_register(CALLBACKS_FULL_ANNOTATIONS)
        theo = next(e for e in entries if "Theo" in e.name or "vampire" in e.name)
        assert theo.expected_return_ch == 18

    def test_must_not_forget_parsed(self) -> None:
        entries = parse_callback_register(CALLBACKS_FULL_ANNOTATIONS)
        theo = next(e for e in entries if "vampire" in e.name)
        assert theo.must_not_forget is True

    def test_no_must_not_forget_is_false(self) -> None:
        entries = parse_callback_register(CALLBACKS_FULL_ANNOTATIONS)
        szym = next(e for e in entries if "Szymborska" in e.name)
        assert szym.must_not_forget is False

    def test_added_date_stripped_from_name(self) -> None:
        entries = parse_callback_register(CALLBACKS_PLAIN)
        assert "added" not in entries[0].name
        assert "2026" not in entries[0].name

    def test_no_callbacks_section_returns_empty(self) -> None:
        text = "# Book\n\n## Rules\n- Some rule\n"
        entries = parse_callback_register(text)
        assert entries == []

    def test_must_forget_without_expected_ch(self) -> None:
        entries = parse_callback_register(CALLBACKS_MUST_FORGET_ONLY)
        assert len(entries) == 1
        assert entries[0].must_not_forget is True
        assert entries[0].expected_return_ch is None


# ---------------------------------------------------------------------------
# TestExtractSearchTerms
# ---------------------------------------------------------------------------


class TestExtractSearchTerms:
    def test_single_word_name(self) -> None:
        terms = _extract_search_terms("Gary")
        assert "Gary" in terms

    def test_multi_word_includes_full_phrase(self) -> None:
        terms = _extract_search_terms("French press")
        # Full phrase or significant words present
        assert any("French" in t or "press" in t for t in terms)

    def test_stopwords_excluded(self) -> None:
        terms = _extract_search_terms("the broken compass")
        lowered = [t.lower() for t in terms]
        assert "the" not in lowered

    def test_significant_words_included(self) -> None:
        terms = _extract_search_terms("Theo's vampire history book")
        lowered = [t.lower() for t in terms]
        assert any("theo" in t for t in lowered)
        assert any("vampire" in t for t in lowered)


# ---------------------------------------------------------------------------
# TestVerifyCallbacks
# ---------------------------------------------------------------------------


class TestVerifyCallbacks:
    def test_no_chapters_all_deferred(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CALLBACKS_BOLD, {})
        result = verify_callbacks(book, CALLBACKS_BOLD)
        assert result["callbacks_checked"] == 2
        # With no chapters, callbacks can't be satisfied
        assert len(result["satisfied"]) == 0

    def test_appears_in_multiple_chapters_is_satisfied(self, tmp_path: Path) -> None:
        claudemd = CALLBACKS_BOLD
        chapters = {
            "01-opening": "Gary the cat sat by the fire. A fine morning.",
            "05-middle": "She noticed Gary watching from the windowsill.",
            "10-late": "Gary curled up on the sofa.",
        }
        book = _write_book(tmp_path, claudemd, chapters)
        result = verify_callbacks(book, claudemd)
        gary = next((e for e in result["satisfied"] if "Gary" in e["name"]), None)
        assert gary is not None
        assert gary["appears_in"] == [1, 5, 10]
        assert gary["last_appeared_ch"] == 10

    def test_never_appeared_is_deferred(self, tmp_path: Path) -> None:
        claudemd = CALLBACKS_BOLD
        chapters = {
            "01-opening": "No mention of anything related here.",
            "02-second": "Still nothing relevant in this chapter.",
        }
        book = _write_book(tmp_path, claudemd, chapters)
        result = verify_callbacks(book, claudemd)
        # Both French press and Gary not mentioned
        assert len(result["satisfied"]) == 0
        # At least one is deferred (no expected_ch, no must_not_forget)
        assert len(result["deferred"]) + len(result["potentially_dropped"]) == 2

    def test_expected_return_overdue_is_potentially_dropped(self, tmp_path: Path) -> None:
        claudemd = """\
# Book

## Callback Register

<!-- CALLBACKS:START -->
- **Theo's vampire history book** — expected return by Ch 5. _(added 2026-01-01)_
<!-- CALLBACKS:END -->
"""
        # Texts deliberately do NOT contain "Theo", "vampire", "history", "book"
        chapters = {
            "01-opening": "She walked down the corridor in silence.",
            "06-late": "Rain hammered the windowpane all morning.",
            "10-final": "The story drew to a close without resolution.",
        }
        book = _write_book(tmp_path, claudemd, chapters)
        result = verify_callbacks(book, claudemd)
        assert len(result["potentially_dropped"]) == 1
        dropped = result["potentially_dropped"][0]
        assert "Theo" in dropped["name"] or "vampire" in dropped["name"]
        assert "expected" in dropped["warning"].lower() or "deadline" in dropped["warning"].lower()

    def test_must_not_forget_plus_long_silence_is_potentially_dropped(self, tmp_path: Path) -> None:
        claudemd = """\
# Book

## Callback Register

<!-- CALLBACKS:START -->
- **the broken compass** _(must not be forgotten)_ _(added 2026-01-01)_
<!-- CALLBACKS:END -->
"""
        chapters = {
            "01-opening": "She found the broken compass in the drawer.",
            "02-ch": "No mention here.",
            "03-ch": "Nothing.",
            "04-ch": "Nothing.",
            "05-ch": "Nothing.",
            "06-ch": "Nothing.",
            "07-ch": "Nothing.",
            "08-ch": "Nothing.",
            "09-ch": "Nothing.",
            "10-ch": "Nothing.",
            "12-ch": "The rain had not let up for days.",
        }
        book = _write_book(tmp_path, claudemd, chapters)
        result = verify_callbacks(book, claudemd)
        # 11 chapters of silence after ch 1 — must-not-forget → potentially_dropped
        assert len(result["potentially_dropped"]) == 1
        assert (
            "forgotten" in result["potentially_dropped"][0]["warning"].lower()
            or "silence" in result["potentially_dropped"][0]["warning"].lower()
        )

    def test_book_slug_in_result(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CALLBACKS_EMPTY, {})
        result = verify_callbacks(book, CALLBACKS_EMPTY)
        assert result["book_slug"] == "my-book"

    def test_empty_callbacks_returns_zero_checked(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CALLBACKS_EMPTY, {})
        result = verify_callbacks(book, CALLBACKS_EMPTY)
        assert result["callbacks_checked"] == 0
        assert result["satisfied"] == []
        assert result["deferred"] == []
        assert result["potentially_dropped"] == []

    def test_alias_matching(self, tmp_path: Path) -> None:
        claudemd = """\
# Book

## Callback Register

<!-- CALLBACKS:START -->
- **Gary** _(added 2026-01-01)_
<!-- CALLBACKS:END -->
"""
        # "Gary" should match even when surrounded by prose
        chapters = {
            "03-ch": "She looked at Gary with suspicion.",
        }
        book = _write_book(tmp_path, claudemd, chapters)
        result = verify_callbacks(book, claudemd)
        assert len(result["satisfied"]) == 1 or (len(result["deferred"]) == 0 and result["callbacks_checked"] == 1)
