"""Tests for series-tracker loaders (Issue #194).

Covers the resolver that maps a series-character-tracker file to its
book-level character slug. Series-trackers can carry slugs that differ
from their book-level equivalents (e.g. ``king-caelan`` tracker maps to
``caelan`` book file). The optional ``book_slug:`` frontmatter field
declares the explicit mapping; when absent, the tracker slug IS the
book slug (zero-config legacy behavior).
"""

from __future__ import annotations

from pathlib import Path

from tools.state.loaders.series import (
    find_series_trackers,
    parse_series_tracker,
    resolve_book_slug_for_series_tracker,
)


def _write_tracker(chars_dir: Path, slug: str, frontmatter: str) -> Path:
    path = chars_dir / f"{slug}.md"
    path.write_text(
        f"---\n{frontmatter}\n---\n\n# {slug}\n",
        encoding="utf-8",
    )
    return path


class TestResolveBookSlug:
    def test_uses_explicit_book_slug_when_present(self) -> None:
        tracker = {"slug": "king-caelan", "book_slug": "caelan"}
        assert resolve_book_slug_for_series_tracker(tracker) == "caelan"

    def test_falls_back_to_tracker_slug_when_book_slug_absent(self) -> None:
        tracker = {"slug": "theo-wilkons"}
        assert resolve_book_slug_for_series_tracker(tracker) == "theo-wilkons"

    def test_falls_back_when_book_slug_is_none(self) -> None:
        tracker = {"slug": "kael", "book_slug": None}
        assert resolve_book_slug_for_series_tracker(tracker) == "kael"

    def test_falls_back_when_book_slug_is_empty_string(self) -> None:
        # Empty string is falsy → treat as absent, fall back to tracker slug.
        tracker = {"slug": "kael", "book_slug": ""}
        assert resolve_book_slug_for_series_tracker(tracker) == "kael"

    def test_returns_empty_string_when_both_missing(self) -> None:
        # Defensive: malformed tracker without slug should not blow up.
        assert resolve_book_slug_for_series_tracker({}) == ""


class TestParseSeriesTracker:
    def test_parses_full_tracker_with_book_slug(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        chars_dir.mkdir()
        path = _write_tracker(
            chars_dir,
            "king-caelan",
            "name: King Caelan\n"
            "slug: king-caelan\n"
            "book_slug: caelan\n"
            "role: supporting\n"
            "species: vampire\n"
            "status: Profile\n"
            "recurs_in: [B1, B2, B3]\n"
            "tracker_type: thin",
        )
        tracker = parse_series_tracker(path)
        assert tracker["slug"] == "king-caelan"
        assert tracker["name"] == "King Caelan"
        assert tracker["book_slug"] == "caelan"
        assert tracker["role"] == "supporting"
        assert tracker["species"] == "vampire"
        assert tracker["status"] == "Profile"
        assert tracker["recurs_in"] == ["B1", "B2", "B3"]
        assert tracker["tracker_type"] == "thin"

    def test_parses_tracker_without_book_slug(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        chars_dir.mkdir()
        path = _write_tracker(
            chars_dir,
            "kael",
            "name: Kael\n"
            "slug: kael\n"
            "role: love-interest\n"
            "species: vampire\n"
            "status: Profile\n"
            "recurs_in: [B1, B2, B3]\n"
            "tracker_type: thin",
        )
        tracker = parse_series_tracker(path)
        assert tracker["slug"] == "kael"
        assert tracker["book_slug"] is None
        assert tracker["role"] == "love-interest"

    def test_resolver_chains_with_parser(self, tmp_path: Path) -> None:
        # End-to-end: parse a real tracker file, hand to resolver.
        chars_dir = tmp_path / "characters"
        chars_dir.mkdir()
        path = _write_tracker(
            chars_dir,
            "queen-miriel",
            "name: Queen Miriel\n"
            "slug: queen-miriel\n"
            "book_slug: miriel\n"
            "role: supporting\n"
            "status: Profile\n"
            "recurs_in: [B1, B2]",
        )
        tracker = parse_series_tracker(path)
        assert resolve_book_slug_for_series_tracker(tracker) == "miriel"

    def test_falls_back_to_path_stem_when_slug_missing(self, tmp_path: Path) -> None:
        # Frontmatter without slug field — tracker's ``slug`` defaults to
        # the file stem so downstream resolver still has a value to work with.
        chars_dir = tmp_path / "characters"
        chars_dir.mkdir()
        path = _write_tracker(
            chars_dir,
            "viktor",
            "name: Viktor\nrole: supporting\nstatus: Profile",
        )
        tracker = parse_series_tracker(path)
        assert tracker["slug"] == "viktor"
        assert tracker["book_slug"] is None

    def test_handles_missing_recurs_in_gracefully(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        chars_dir.mkdir()
        path = _write_tracker(
            chars_dir,
            "minor-char",
            "name: Minor Char\nslug: minor-char\nrole: minor\nstatus: Concept",
        )
        tracker = parse_series_tracker(path)
        assert tracker["recurs_in"] == []
        assert tracker["tracker_type"] == "thin"


class TestFindSeriesTrackers:
    def test_returns_all_md_files_excluding_index(self, tmp_path: Path) -> None:
        series_dir = tmp_path / "blood-and-binary"
        chars_dir = series_dir / "characters"
        chars_dir.mkdir(parents=True)
        _write_tracker(chars_dir, "kael", "slug: kael")
        _write_tracker(chars_dir, "theo-wilkons", "slug: theo-wilkons")
        _write_tracker(chars_dir, "king-caelan", "slug: king-caelan\nbook_slug: caelan")
        (chars_dir / "INDEX.md").write_text("# Index\n", encoding="utf-8")

        trackers = find_series_trackers(series_dir)
        names = sorted(p.name for p in trackers)
        assert names == ["kael.md", "king-caelan.md", "theo-wilkons.md"]

    def test_returns_empty_when_characters_dir_missing(self, tmp_path: Path) -> None:
        series_dir = tmp_path / "lonely-series"
        series_dir.mkdir()
        assert find_series_trackers(series_dir) == []

    def test_returns_empty_when_series_dir_missing(self, tmp_path: Path) -> None:
        assert find_series_trackers(tmp_path / "does-not-exist") == []

    def test_ignores_non_md_files(self, tmp_path: Path) -> None:
        series_dir = tmp_path / "series"
        chars_dir = series_dir / "characters"
        chars_dir.mkdir(parents=True)
        _write_tracker(chars_dir, "kael", "slug: kael")
        (chars_dir / "notes.txt").write_text("scratch", encoding="utf-8")
        (chars_dir / ".hidden.md").write_text("---\n---\n", encoding="utf-8")

        trackers = find_series_trackers(series_dir)
        # Hidden dotfiles are returned by glob("*.md") — current behavior;
        # we only assert the txt file is filtered. INDEX is the explicit
        # filter case, dotfiles are author's responsibility.
        names = {p.name for p in trackers}
        assert "notes.txt" not in names
        assert "kael.md" in names
