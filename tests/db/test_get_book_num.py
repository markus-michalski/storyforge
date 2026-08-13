"""Tests for get_book_num() — Issue #579.

A book scaffolded into a series via create_book_structure(series_slug=...)
gets series_number: 0 written to its README (see
servers/storyforge-server/routers/creation.py) until add_book_to_series()
assigns the real number. get_book_num() previously collapsed that 0 to 1
silently (`int(0) or 1 == 1`), causing any freshly-scaffolded-but-unlinked
series book to share book_num=1's DB rows (book_rules, character_snapshots,
canon_facts) with an unrelated book. It must now raise instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.db.connection import BookNotLinkedToSeriesError, get_book_num, get_book_series_slug


def _write_readme(book_root: Path, *, series: str = "", series_number: object = 1) -> None:
    book_root.mkdir(parents=True, exist_ok=True)
    lines = ["---", 'title: "Test Book"', f'series: "{series}"']
    if series_number is not None:
        lines.append(f"series_number: {series_number}")
    lines.append("---\n# Test Book\n")
    (book_root / "README.md").write_text("\n".join(lines), encoding="utf-8")


class TestGetBookNum:
    def test_standalone_book_no_series_defaults_to_one(self, tmp_path: Path) -> None:
        book_root = tmp_path / "standalone-book"
        _write_readme(book_root, series="", series_number=0)
        assert get_book_num(book_root) == 1

    def test_linked_series_book_returns_its_number(self, tmp_path: Path) -> None:
        book_root = tmp_path / "book-two"
        _write_readme(book_root, series="my-series", series_number=2)
        assert get_book_num(book_root) == 2

    def test_first_book_in_series_number_one_is_fine(self, tmp_path: Path) -> None:
        book_root = tmp_path / "book-one"
        _write_readme(book_root, series="my-series", series_number=1)
        assert get_book_num(book_root) == 1

    def test_unlinked_series_book_raises(self, tmp_path: Path) -> None:
        """The exact #579 scenario: create_book_structure(series_slug=...)
        just ran, add_book_to_series() has not — series is set, number is
        still the scaffold default of 0."""
        book_root = tmp_path / "unlinked-book"
        _write_readme(book_root, series="my-series", series_number=0)
        with pytest.raises(BookNotLinkedToSeriesError):
            get_book_num(book_root)

    def test_error_message_names_the_series_and_the_fix(self, tmp_path: Path) -> None:
        book_root = tmp_path / "unlinked-book"
        _write_readme(book_root, series="blood-and-binary", series_number=0)
        with pytest.raises(BookNotLinkedToSeriesError, match="blood-and-binary"):
            get_book_num(book_root)

    def test_missing_series_number_field_defaults_to_one_even_with_series_set(
        self, tmp_path: Path
    ) -> None:
        """A book with series set but no series_number key at all (never
        written, vs. explicitly 0) is a different, pre-existing case (#558)
        — not the #579 scaffold-default trap. Keep defaulting to 1 here;
        only an explicit 0 is the unlinked-book signal."""
        book_root = tmp_path / "legacy-book"
        _write_readme(book_root, series="my-series", series_number=None)
        assert get_book_num(book_root) == 1

    def test_missing_readme_defaults_to_one(self, tmp_path: Path) -> None:
        book_root = tmp_path / "no-readme-book"
        book_root.mkdir(parents=True)
        assert get_book_num(book_root) == 1

    def test_malformed_series_number_defaults_to_one(self, tmp_path: Path) -> None:
        book_root = tmp_path / "malformed-book"
        _write_readme(book_root, series="my-series", series_number="not-a-number")
        assert get_book_num(book_root) == 1

    def test_book_not_linked_to_series_error_is_a_value_error(self) -> None:
        """Subclassing ValueError keeps existing broad `except ValueError`/
        `except Exception` handlers degrading gracefully where that's
        already documented behavior (see Issue #523's SlugValidationError
        precedent for the same pattern)."""
        assert issubclass(BookNotLinkedToSeriesError, ValueError)

    def test_negative_series_number_also_raises(self, tmp_path: Path) -> None:
        """Not just the exact scaffold-default 0 — any series_number below
        1 is equally not a real book number and must not silently key DB
        rows (code review finding L-1)."""
        book_root = tmp_path / "negative-book"
        _write_readme(book_root, series="my-series", series_number=-1)
        with pytest.raises(BookNotLinkedToSeriesError):
            get_book_num(book_root)

    def test_whitespace_only_series_treated_as_no_series(self, tmp_path: Path) -> None:
        book_root = tmp_path / "whitespace-series-book"
        _write_readme(book_root, series="   ", series_number=0)
        assert get_book_num(book_root) == 1

    def test_quoted_zero_string_series_number_still_raises(self, tmp_path: Path) -> None:
        """YAML frontmatter can round-trip series_number as a quoted string
        (e.g. hand-edited or from a lossy migration) — must behave the same
        as the int 0, not silently pass the `series_number == 0` check by
        virtue of being the string "0" instead."""
        book_root = tmp_path / "quoted-zero-book"
        book_root.mkdir(parents=True)
        (book_root / "README.md").write_text(
            '---\ntitle: "Test"\nseries: "my-series"\nseries_number: "0"\n---\n',
            encoding="utf-8",
        )
        with pytest.raises(BookNotLinkedToSeriesError):
            get_book_num(book_root)

    def test_null_series_value_treated_as_no_series(self, tmp_path: Path) -> None:
        """Issue #584: `series:` with no value (YAML null, parses to Python
        None) must not coerce to the literal string "None" — that string is
        truthy and would (a) make this function's own `if series and num <
        1` guard fire incorrectly, and (b) make get_db_slug_for_book()
        resolve to a real ~/.storyforge/db/None.db file elsewhere."""
        book_root = tmp_path / "null-series-book"
        book_root.mkdir(parents=True)
        (book_root / "README.md").write_text(
            '---\ntitle: "Test"\nseries:\nseries_number: 0\n---\n',
            encoding="utf-8",
        )
        assert get_book_num(book_root) == 1

    def test_list_series_value_treated_as_no_series(self, tmp_path: Path) -> None:
        """Issue #584 (L6): a malformed `series: [a, b]` (YAML list, not a
        scalar) must not stringify to "['a', 'b']" and be treated as a real
        series — that would both dodge this function's unlinked-book guard
        and create a bogus DB file keyed on the stringified list elsewhere."""
        book_root = tmp_path / "list-series-book"
        book_root.mkdir(parents=True)
        (book_root / "README.md").write_text(
            '---\ntitle: "Test"\nseries: [a, b]\nseries_number: 0\n---\n',
            encoding="utf-8",
        )
        assert get_book_num(book_root) == 1


class TestGetBookSeriesSlug:
    def test_normal_series_returned(self, tmp_path: Path) -> None:
        book_root = tmp_path / "book"
        _write_readme(book_root, series="my-series", series_number=1)
        assert get_book_series_slug(book_root) == "my-series"

    def test_no_series_returns_empty_string(self, tmp_path: Path) -> None:
        book_root = tmp_path / "book"
        _write_readme(book_root, series="", series_number=1)
        assert get_book_series_slug(book_root) == ""

    def test_null_series_returns_empty_string_not_literal_none(self, tmp_path: Path) -> None:
        """Issue #584: `series:` with no value must not coerce to "None"."""
        book_root = tmp_path / "book"
        book_root.mkdir(parents=True)
        (book_root / "README.md").write_text(
            '---\ntitle: "Test"\nseries:\n---\n',
            encoding="utf-8",
        )
        assert get_book_series_slug(book_root) == ""

    def test_list_series_returns_empty_string_not_stringified_list(self, tmp_path: Path) -> None:
        """Issue #584 (L6): a malformed `series: [a, b]` parses to a Python
        list, not a scalar. str([...]) would produce "['a', 'b']" — non-empty,
        passes slug validation, and creates a bogus DB file for a value that
        was never a real series slug."""
        book_root = tmp_path / "book"
        book_root.mkdir(parents=True)
        (book_root / "README.md").write_text(
            '---\ntitle: "Test"\nseries: [a, b]\n---\n',
            encoding="utf-8",
        )
        assert get_book_series_slug(book_root) == ""
