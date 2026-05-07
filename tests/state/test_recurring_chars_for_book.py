"""Tests for ``recurring_chars_for_book`` helper (Issue #196).

The helper surfaces which series-trackers belong in a given book band
(``B1`` / ``B2`` / ...) so the new-book auto-copy logic and the future
D-2 bootstrap skill know exactly which character files to handle.

Each entry mirrors the output of ``parse_series_tracker`` plus a
``prior_bands`` field — bands in ``recurs_in`` that come before the
target band — used to determine whether the character has a source
file in any prior book.
"""

from __future__ import annotations

from pathlib import Path

from tools.state.loaders.series import recurring_chars_for_book


def _write_tracker(
    chars_dir: Path,
    slug: str,
    *,
    name: str | None = None,
    role: str = "supporting",
    book_slug: str | None = None,
    recurs_in: list[str] | None = None,
) -> Path:
    chars_dir.mkdir(parents=True, exist_ok=True)
    book_slug_line = f"book_slug: {book_slug}\n" if book_slug else ""
    fm = (
        "---\n"
        f"name: {name or slug}\n"
        f"slug: {slug}\n"
        f"{book_slug_line}"
        f"role: {role}\n"
        "status: Profile\n"
        f"recurs_in: {recurs_in or ['B1']}\n"
        "tracker_type: thin\n"
        "---\n\n# Stub\n"
    )
    path = chars_dir / f"{slug}.md"
    path.write_text(fm, encoding="utf-8")
    return path


class TestRecurringCharsForBook:
    def test_returns_only_trackers_recurring_in_band(self, tmp_path: Path) -> None:
        chars = tmp_path / "characters"
        _write_tracker(chars, "kael", recurs_in=["B1", "B2", "B3"])
        _write_tracker(chars, "viktor", recurs_in=["B1", "B2"])
        # Only-B1 char (e.g. dies in B1) — must be excluded for B2 query.
        _write_tracker(chars, "sera", recurs_in=["B1"])

        result = recurring_chars_for_book(tmp_path, "B2")
        slugs = sorted(t["tracker_slug"] for t in result)
        assert slugs == ["kael", "viktor"]

    def test_includes_band_only_chars(self, tmp_path: Path) -> None:
        # A character that first appears in B2 (e.g. Tristan) — recurs_in
        # starts at B2. Must be returned for B2 with empty prior_bands so
        # the caller knows there's no source to copy from.
        chars = tmp_path / "characters"
        _write_tracker(chars, "tristan", recurs_in=["B2", "B3"])
        result = recurring_chars_for_book(tmp_path, "B2")
        assert len(result) == 1
        assert result[0]["tracker_slug"] == "tristan"
        assert result[0]["prior_bands"] == []

    def test_prior_bands_sorted_and_filtered(self, tmp_path: Path) -> None:
        chars = tmp_path / "characters"
        _write_tracker(chars, "kael", recurs_in=["B1", "B2", "B3"])
        result = recurring_chars_for_book(tmp_path, "B3")
        entry = result[0]
        # prior_bands = bands in recurs_in that come BEFORE B3.
        assert entry["prior_bands"] == ["B1", "B2"]

    def test_prior_bands_empty_for_first_appearance(self, tmp_path: Path) -> None:
        chars = tmp_path / "characters"
        _write_tracker(chars, "tristan", recurs_in=["B2", "B3"])
        result = recurring_chars_for_book(tmp_path, "B2")
        assert result[0]["prior_bands"] == []

    def test_returns_empty_when_no_trackers(self, tmp_path: Path) -> None:
        # No characters/ dir at all.
        assert recurring_chars_for_book(tmp_path, "B1") == []

    def test_returns_empty_when_dir_empty(self, tmp_path: Path) -> None:
        (tmp_path / "characters").mkdir()
        assert recurring_chars_for_book(tmp_path, "B1") == []

    def test_excludes_index_md(self, tmp_path: Path) -> None:
        chars = tmp_path / "characters"
        _write_tracker(chars, "kael", recurs_in=["B1", "B2"])
        chars.mkdir(parents=True, exist_ok=True)
        (chars / "INDEX.md").write_text("---\nslug: index\nrecurs_in: [B1, B2]\n---\n", encoding="utf-8")
        result = recurring_chars_for_book(tmp_path, "B2")
        slugs = [t["tracker_slug"] for t in result]
        assert "kael" in slugs
        assert "index" not in slugs

    def test_carries_book_slug_for_resolver(self, tmp_path: Path) -> None:
        # Tracker with book_slug ≠ tracker slug (the #194 case).
        chars = tmp_path / "characters"
        _write_tracker(
            chars,
            "king-caelan",
            book_slug="caelan",
            recurs_in=["B1", "B2", "B3"],
        )
        result = recurring_chars_for_book(tmp_path, "B2")
        assert result[0]["tracker_slug"] == "king-caelan"
        assert result[0]["book_slug"] == "caelan"

    def test_falls_back_to_tracker_slug_when_book_slug_absent(self, tmp_path: Path) -> None:
        chars = tmp_path / "characters"
        _write_tracker(chars, "kael", recurs_in=["B1", "B2"])
        result = recurring_chars_for_book(tmp_path, "B2")
        assert result[0]["tracker_slug"] == "kael"
        assert result[0]["book_slug"] == "kael"

    def test_invalid_band_returns_empty(self, tmp_path: Path) -> None:
        # Non-band string — defensive: returns empty list rather than
        # exception.
        chars = tmp_path / "characters"
        _write_tracker(chars, "kael", recurs_in=["B1", "B2"])
        assert recurring_chars_for_book(tmp_path, "Book1") == []

    def test_results_sorted_by_tracker_slug(self, tmp_path: Path) -> None:
        # Stable ordering helps deterministic skill output.
        chars = tmp_path / "characters"
        _write_tracker(chars, "viktor", recurs_in=["B1", "B2"])
        _write_tracker(chars, "kael", recurs_in=["B1", "B2"])
        _write_tracker(chars, "dominic", recurs_in=["B1", "B2"])
        result = recurring_chars_for_book(tmp_path, "B2")
        slugs = [t["tracker_slug"] for t in result]
        assert slugs == sorted(slugs)
