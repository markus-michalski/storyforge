"""Tests for StoryForge path utilities."""

from pathlib import Path

import pytest

from tools.shared.paths import (
    slugify,
    resolve_project_path,
    resolve_chapter_path,
    resolve_character_path,
    resolve_author_path,
    resolve_series_path,
    resolve_person_path,
    resolve_world_dir,
    find_projects,
    find_chapters,
)


class TestSlugify:
    def test_simple(self):
        assert slugify("My Book Title") == "my-book-title"

    def test_special_characters(self):
        assert slugify("Hello, World! It's a Test.") == "hello-world-its-a-test"

    def test_multiple_spaces(self):
        assert slugify("Too   Many   Spaces") == "too-many-spaces"

    def test_underscores(self):
        assert slugify("snake_case_title") == "snake-case-title"

    def test_already_slug(self):
        assert slugify("already-a-slug") == "already-a-slug"

    def test_leading_trailing(self):
        assert slugify("  trimmed  ") == "trimmed"

    def test_unicode(self):
        assert slugify("Über die Brücke") == "über-die-brücke"


class TestResolvePaths:
    def test_project_path(self):
        config = {"paths": {"content_root": "/home/user/books"}}
        result = resolve_project_path(config, "my-book")
        assert result == Path("/home/user/books/projects/my-book")

    def test_chapter_path(self):
        config = {"paths": {"content_root": "/home/user/books"}}
        result = resolve_chapter_path(config, "my-book", "01-intro")
        assert result == Path("/home/user/books/projects/my-book/chapters/01-intro")

    def test_character_path(self):
        config = {"paths": {"content_root": "/home/user/books"}}
        result = resolve_character_path(config, "my-book", "alex")
        assert result == Path("/home/user/books/projects/my-book/characters/alex.md")

    def test_author_path(self):
        config = {"paths": {"authors_root": "/home/user/.storyforge/authors"}}
        result = resolve_author_path(config, "dark-narrator")
        assert result == Path("/home/user/.storyforge/authors/dark-narrator")

    def test_series_path(self):
        config = {"paths": {"content_root": "/home/user/books"}}
        result = resolve_series_path(config, "my-series")
        assert result == Path("/home/user/books/series/my-series")


class TestFindProjects:
    def test_find_projects(self, tmp_path):
        config = {"paths": {"content_root": str(tmp_path)}}

        # Create project structure
        proj = tmp_path / "projects" / "book-one"
        proj.mkdir(parents=True)
        (proj / "README.md").write_text("---\ntitle: Book One\n---\n")

        # Create non-project directory (no README)
        (tmp_path / "projects" / "not-a-project").mkdir()

        result = find_projects(config)
        assert len(result) == 1
        assert result[0].name == "book-one"

    def test_find_projects_empty(self, tmp_path):
        config = {"paths": {"content_root": str(tmp_path)}}
        result = find_projects(config)
        assert result == []

    def test_find_chapters(self, tmp_path):
        config = {"paths": {"content_root": str(tmp_path)}}

        # Create chapter structure
        ch1 = tmp_path / "projects" / "my-book" / "chapters" / "01-intro"
        ch1.mkdir(parents=True)
        (ch1 / "README.md").write_text("---\ntitle: Intro\n---\n")

        ch2 = tmp_path / "projects" / "my-book" / "chapters" / "02-rising"
        ch2.mkdir(parents=True)
        (ch2 / "README.md").write_text("---\ntitle: Rising\n---\n")

        result = find_chapters(config, "my-book")
        assert len(result) == 2
        assert result[0].name == "01-intro"
        assert result[1].name == "02-rising"


# ---------------------------------------------------------------------------
# Audit H2 — Slug validation prevents path traversal
# ---------------------------------------------------------------------------


class TestSlugValidation:
    """Resolvers must reject slugs that contain path separators, '..',
    null bytes, or that start with '.'. These would let an attacker escape
    content_root or authors_root via the MCP boundary."""

    CONFIG_CONTENT = {"paths": {"content_root": "/home/user/books"}}
    CONFIG_AUTHORS = {"paths": {"authors_root": "/home/user/.storyforge/authors"}}

    @pytest.mark.parametrize(
        "evil_slug",
        [
            "../etc/passwd",
            "..",
            "../escape",
            "foo/bar",
            "foo\\bar",
            ".hidden",
            ".",
            "with\x00null",
            "/absolute",
        ],
    )
    def test_resolve_project_rejects_unsafe_slug(self, evil_slug):
        with pytest.raises(ValueError, match="must not"):
            resolve_project_path(self.CONFIG_CONTENT, evil_slug)

    def test_resolve_chapter_rejects_traversal_in_book_slug(self):
        with pytest.raises(ValueError):
            resolve_chapter_path(self.CONFIG_CONTENT, "../escape", "01-intro")

    def test_resolve_chapter_rejects_traversal_in_chapter_slug(self):
        with pytest.raises(ValueError):
            resolve_chapter_path(self.CONFIG_CONTENT, "valid-book", "../escape")

    def test_resolve_character_rejects_traversal(self):
        with pytest.raises(ValueError):
            resolve_character_path(self.CONFIG_CONTENT, "valid-book", "../alex")

    def test_resolve_person_rejects_traversal(self):
        with pytest.raises(ValueError):
            resolve_person_path(
                self.CONFIG_CONTENT, "valid-book", "../jane", book_category="memoir"
            )

    def test_resolve_series_rejects_traversal(self):
        with pytest.raises(ValueError):
            resolve_series_path(self.CONFIG_CONTENT, "../escape")

    def test_resolve_author_rejects_traversal(self):
        with pytest.raises(ValueError):
            resolve_author_path(self.CONFIG_AUTHORS, "../escape")

    def test_valid_slugs_still_resolve(self):
        # Control: legitimate slugs must continue working unchanged
        result = resolve_project_path(self.CONFIG_CONTENT, "my-book-23")
        assert result == Path("/home/user/books/projects/my-book-23")

        result = resolve_chapter_path(self.CONFIG_CONTENT, "blood-and-binary", "20-bruises")
        assert result == Path(
            "/home/user/books/projects/blood-and-binary/chapters/20-bruises"
        )

    def test_empty_slug_does_not_crash(self):
        # Empty slug isn't a traversal and shouldn't raise — caller may use
        # it as a "no chapter" marker; only unsafe content is rejected.
        result = resolve_project_path(self.CONFIG_CONTENT, "")
        assert result == Path("/home/user/books/projects")


class TestPathContainment:
    """resolve_world_dir must not return a path outside the project_dir
    even if a malicious symlink points elsewhere — it iterates only known
    candidate names, so this test pins that contract."""

    def test_resolve_world_dir_only_returns_known_candidates(self, tmp_path: Path):
        project = tmp_path / "projects" / "my-book"
        (project / "world").mkdir(parents=True)
        result = resolve_world_dir(project)
        assert result is not None
        assert result.is_relative_to(project)
