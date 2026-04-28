"""Unit tests for tools.analysis.manuscript.metadata."""

from __future__ import annotations

from pathlib import Path

from tools.analysis.manuscript.metadata import (
    _read_allowed_repetitions,
    _read_book_category,
    _read_book_genres,
    _read_people_profiles,
    _read_snapshot_threshold,
)


class TestReadBookGenres:
    def test_inline_format(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            '---\ngenres: ["fantasy", "thriller"]\n---\n\n# Book\n',
            encoding="utf-8",
        )
        assert _read_book_genres(tmp_path) == ["fantasy", "thriller"]

    def test_block_format(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "---\ngenres:\n  - horror\n  - mystery\n---\n\n# Book\n",
            encoding="utf-8",
        )
        assert _read_book_genres(tmp_path) == ["horror", "mystery"]

    def test_no_frontmatter_returns_empty(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Book\n", encoding="utf-8")
        assert _read_book_genres(tmp_path) == []


class TestReadBookCategory:
    def test_memoir(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "---\nbook_category: memoir\n---\n\n# Memoir\n",
            encoding="utf-8",
        )
        assert _read_book_category(tmp_path) == "memoir"

    def test_default_fiction(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# No frontmatter\n", encoding="utf-8")
        assert _read_book_category(tmp_path) == "fiction"

    def test_missing_readme(self, tmp_path: Path) -> None:
        assert _read_book_category(tmp_path) == "fiction"


class TestReadPeopleProfiles:
    def test_reads_all_people(self, tmp_path: Path) -> None:
        people_dir = tmp_path / "people"
        people_dir.mkdir()
        (people_dir / "alice.md").write_text(
            "---\nname: Alice\nanonymization: pseudonym\nreal_name: Alicia\n---\n",
            encoding="utf-8",
        )
        (people_dir / "INDEX.md").write_text("ignored", encoding="utf-8")
        people = _read_people_profiles(tmp_path)
        assert len(people) == 1
        assert people[0]["name"] == "Alice"
        assert people[0]["real_name"] == "Alicia"

    def test_no_people_dir_returns_empty(self, tmp_path: Path) -> None:
        assert _read_people_profiles(tmp_path) == []


class TestReadAllowedRepetitions:
    def test_reads_section(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text(
            "## Allowed Repetitions\n- Phrase one\n- Phrase two\n\n## Other\n",
            encoding="utf-8",
        )
        out = _read_allowed_repetitions(tmp_path)
        assert "phrase one" in out
        assert "phrase two" in out

    def test_missing_returns_empty(self, tmp_path: Path) -> None:
        assert _read_allowed_repetitions(tmp_path) == frozenset()


class TestReadSnapshotThreshold:
    def test_reads_from_linter_config(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text(
            "## Linter Config\n- snapshot_threshold: 7\n",
            encoding="utf-8",
        )
        assert _read_snapshot_threshold(tmp_path) == 7

    def test_default_when_missing(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("# Book\n", encoding="utf-8")
        assert _read_snapshot_threshold(tmp_path) == 5

    def test_clamps_to_minimum_two(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text(
            "## Linter Config\n- snapshot_threshold: 0\n",
            encoding="utf-8",
        )
        assert _read_snapshot_threshold(tmp_path) == 2
