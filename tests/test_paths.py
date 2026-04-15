"""Tests for StoryForge path utilities."""

from pathlib import Path
from tools.shared.paths import (
    slugify,
    resolve_project_path,
    resolve_chapter_path,
    resolve_character_path,
    resolve_author_path,
    resolve_series_path,
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
