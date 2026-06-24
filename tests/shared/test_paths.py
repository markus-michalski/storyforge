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
    find_series,
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
            resolve_person_path(self.CONFIG_CONTENT, "valid-book", "../jane", book_category="memoir")

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
        assert result == Path("/home/user/books/projects/blood-and-binary/chapters/20-bruises")

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


# ---------------------------------------------------------------------------
# Issue #279 — Series directory layout
# ---------------------------------------------------------------------------


def _make_series_book(content_root: Path, series_slug: str, book_slug: str) -> Path:
    """Create a minimal book dir inside a series directory."""
    book_path = content_root / "series" / series_slug / book_slug
    book_path.mkdir(parents=True)
    (book_path / "README.md").write_text(f"---\ntitle: {book_slug}\n---\n", encoding="utf-8")
    return book_path


class TestFindProjectsSeriesAware:
    """find_projects() must also discover books nested inside series/ dirs."""

    def test_finds_books_inside_series_directories(self, tmp_path: Path):
        config = {"paths": {"content_root": str(tmp_path)}}
        _make_series_book(tmp_path, "blood-and-binary", "firelight")

        result = find_projects(config)
        assert any(p.name == "firelight" for p in result)

    def test_standalone_books_still_found(self, tmp_path: Path):
        config = {"paths": {"content_root": str(tmp_path)}}
        proj = tmp_path / "projects" / "standalone"
        proj.mkdir(parents=True)
        (proj / "README.md").write_text("---\ntitle: Standalone\n---\n", encoding="utf-8")

        result = find_projects(config)
        assert any(p.name == "standalone" for p in result)

    def test_books_from_both_locations_found(self, tmp_path: Path):
        config = {"paths": {"content_root": str(tmp_path)}}
        proj = tmp_path / "projects" / "solo-book"
        proj.mkdir(parents=True)
        (proj / "README.md").write_text("---\ntitle: Solo\n---\n", encoding="utf-8")
        _make_series_book(tmp_path, "my-series", "series-book")

        result = find_projects(config)
        names = [p.name for p in result]
        assert "solo-book" in names
        assert "series-book" in names

    def test_series_dir_itself_not_included(self, tmp_path: Path):
        """The series root dir (series/blood-and-binary/) must not appear in results."""
        config = {"paths": {"content_root": str(tmp_path)}}
        _make_series_book(tmp_path, "blood-and-binary", "firelight")

        result = find_projects(config)
        assert not any(p.name == "blood-and-binary" for p in result)

    def test_bare_series_subdir_without_readme_not_included(self, tmp_path: Path):
        config = {"paths": {"content_root": str(tmp_path)}}
        bare = tmp_path / "series" / "my-series" / "no-readme"
        bare.mkdir(parents=True)

        result = find_projects(config)
        assert result == []


class TestResolveProjectPathSeriesAware:
    """resolve_project_path() must fall back to series/ when book not in projects/."""

    def test_finds_book_in_series_dir(self, tmp_path: Path):
        config = {"paths": {"content_root": str(tmp_path)}}
        book_path = _make_series_book(tmp_path, "blood-and-binary", "firelight")

        result = resolve_project_path(config, "firelight")
        assert result == book_path

    def test_prefers_projects_dir_when_both_exist(self, tmp_path: Path):
        config = {"paths": {"content_root": str(tmp_path)}}
        legacy = tmp_path / "projects" / "ambiguous"
        legacy.mkdir(parents=True)
        _make_series_book(tmp_path, "some-series", "ambiguous")

        result = resolve_project_path(config, "ambiguous")
        assert result == legacy

    def test_falls_back_to_projects_for_new_book(self, tmp_path: Path):
        """When book doesn't exist on disk yet, return the projects/ path."""
        config = {"paths": {"content_root": str(tmp_path)}}
        result = resolve_project_path(config, "brand-new-book")
        assert result == tmp_path / "projects" / "brand-new-book"

    def test_security_slug_validation_still_enforced(self, tmp_path: Path):
        config = {"paths": {"content_root": str(tmp_path)}}
        with pytest.raises(ValueError, match="must not"):
            resolve_project_path(config, "../escape")


class TestFindSeriesYaml:
    """find_series() must recognise series.yaml (new format) and README.md (old format)."""

    def test_detects_series_yaml(self, tmp_path: Path):
        config = {"paths": {"content_root": str(tmp_path)}}
        series_dir = tmp_path / "series" / "new-series"
        series_dir.mkdir(parents=True)
        (series_dir / "series.yaml").write_text(
            "name: New Series\nslug: new-series\ntotal_books: 2\n",
            encoding="utf-8",
        )

        result = find_series(config)
        assert len(result) == 1
        assert result[0].name == "new-series"

    def test_backward_compat_readme_still_found(self, tmp_path: Path):
        config = {"paths": {"content_root": str(tmp_path)}}
        series_dir = tmp_path / "series" / "old-series"
        series_dir.mkdir(parents=True)
        (series_dir / "README.md").write_text("---\ntitle: Old Series\n---\n", encoding="utf-8")

        result = find_series(config)
        assert len(result) == 1
        assert result[0].name == "old-series"

    def test_bare_dir_without_marker_not_found(self, tmp_path: Path):
        config = {"paths": {"content_root": str(tmp_path)}}
        bare = tmp_path / "series" / "no-marker"
        bare.mkdir(parents=True)

        result = find_series(config)
        assert result == []
