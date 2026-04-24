"""Tests for author_writing_mode support in parse_author_profile.

Issue #34: StoryForge now tracks how an author plans their writing process
(outliner | plantser | discovery). This is stored as author_writing_mode in
the author profile frontmatter — distinct from the book-level writing_mode
(scene-by-scene | chapter | book) which controls how Claude composes chapters.
"""

from __future__ import annotations

from pathlib import Path

from tools.state.parsers import parse_author_profile, parse_book_readme


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_profile(tmp_path: Path, extra_frontmatter: str = "") -> Path:
    author_dir = tmp_path / "test-author"
    author_dir.mkdir()
    profile = author_dir / "profile.md"
    profile.write_text(
        f'---\nname: "Test Author"\nslug: "test-author"\n'
        f'narrative_voice: "third-limited"\ntense: "past"\n'
        f'{extra_frontmatter}'
        f'---\n\n# Test Author\n',
        encoding="utf-8",
    )
    return profile


# ---------------------------------------------------------------------------
# author_writing_mode field
# ---------------------------------------------------------------------------


class TestAuthorWritingMode:
    def test_returns_outliner_as_default_when_field_missing(self, tmp_path):
        profile = _make_profile(tmp_path)
        result = parse_author_profile(profile)
        assert result["author_writing_mode"] == "outliner"

    def test_reads_outliner_value(self, tmp_path):
        profile = _make_profile(tmp_path, 'author_writing_mode: "outliner"\n')
        result = parse_author_profile(profile)
        assert result["author_writing_mode"] == "outliner"

    def test_reads_plantser_value(self, tmp_path):
        profile = _make_profile(tmp_path, 'author_writing_mode: "plantser"\n')
        result = parse_author_profile(profile)
        assert result["author_writing_mode"] == "plantser"

    def test_reads_discovery_value(self, tmp_path):
        profile = _make_profile(tmp_path, 'author_writing_mode: "discovery"\n')
        result = parse_author_profile(profile)
        assert result["author_writing_mode"] == "discovery"

    def test_does_not_conflict_with_existing_fields(self, tmp_path):
        """author_writing_mode must not overwrite or corrupt other profile fields."""
        profile = _make_profile(tmp_path, 'author_writing_mode: "plantser"\n')
        result = parse_author_profile(profile)
        assert result["narrative_voice"] == "third-limited"
        assert result["tense"] == "past"
        assert result["slug"] == "test-author"
        assert result["name"] == "Test Author"

    def test_field_present_in_returned_dict(self, tmp_path):
        """Regression: author_writing_mode must always be present, never silently absent."""
        profile = _make_profile(tmp_path)
        result = parse_author_profile(profile)
        assert "author_writing_mode" in result


# ---------------------------------------------------------------------------
# Book-level author_writing_mode override (stored in book README frontmatter)
# ---------------------------------------------------------------------------


def _make_book_readme(tmp_path: Path, extra_frontmatter: str = "") -> Path:
    book_dir = tmp_path / "my-book"
    book_dir.mkdir()
    readme = book_dir / "README.md"
    readme.write_text(
        f'---\ntitle: "My Book"\nauthor: "test-author"\n'
        f'genres: ["horror"]\nbook_type: "novel"\nstatus: "Idea"\n'
        f'{extra_frontmatter}'
        f'---\n\n# My Book\n',
        encoding="utf-8",
    )
    return readme


class TestBookAuthorWritingModeOverride:
    def test_defaults_to_empty_string_when_not_set(self, tmp_path):
        """Empty string signals 'inherit from author profile' — not a mode value."""
        readme = _make_book_readme(tmp_path)
        result = parse_book_readme(readme)
        assert result["author_writing_mode"] == ""

    def test_reads_override_when_set(self, tmp_path):
        readme = _make_book_readme(tmp_path, 'author_writing_mode: "discovery"\n')
        result = parse_book_readme(readme)
        assert result["author_writing_mode"] == "discovery"

    def test_field_present_in_returned_dict(self, tmp_path):
        readme = _make_book_readme(tmp_path)
        result = parse_book_readme(readme)
        assert "author_writing_mode" in result
