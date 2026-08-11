"""Tests for StoryForge path utilities."""

import json
import logging
from pathlib import Path

import pytest

from tools.shared.paths import (
    SlugValidationError,
    catch_slug_value_error,
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
            "C:evil",
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


class TestCatchSlugValueError:
    """Issue #523: MCP tool functions call resolve_*_path() helpers, which
    raise SlugValidationError via _validate_slug() on a null byte, '..', a
    path separator, or a leading dot. Most call sites across this server
    don't catch it, so a bad slug propagates as a raw, unhandled server
    exception instead of this codebase's standard {"error": ...} JSON
    contract (the same gap #521 covers for resolve_path()'s book_slug
    specifically). catch_slug_value_error() is the shared fix: a decorator
    applied to every affected MCP tool function that converts an escaping
    error into that JSON contract, once, instead of an individual
    try/except per call site. See
    tests/server/test_catch_slug_value_error_coverage.py for the sweep that
    keeps that set complete."""

    def test_passes_through_normal_return_value(self):
        @catch_slug_value_error
        def tool(x: str) -> str:
            return json.dumps({"ok": x})

        assert json.loads(tool("fine")) == {"ok": "fine"}

    def test_converts_value_error_to_json_error(self):
        @catch_slug_value_error
        def tool(slug: str) -> str:
            resolve_project_path({"paths": {"content_root": "/tmp/does-not-matter"}}, slug)
            return json.dumps({"success": True})

        result = json.loads(tool("bad\x00slug"))
        assert "error" in result
        assert "bad" in result["error"]

    def test_does_not_swallow_other_exceptions(self):
        @catch_slug_value_error
        def tool() -> str:
            raise RuntimeError("unrelated failure")

        with pytest.raises(RuntimeError):
            tool()

    def test_does_not_swallow_unrelated_value_error(self):
        """Code review finding M-1: the decorator must catch only
        SlugValidationError, not bare ValueError — otherwise an internal
        invariant check (e.g. "mode must be auto/bullet/h3") or an unrelated
        parsing failure inside the wrapped function gets silently reported
        as if it were a slug-validation error, discarding the real cause."""

        @catch_slug_value_error
        def tool() -> str:
            raise ValueError("mode must be auto/bullet/h3 — got 'x'")

        with pytest.raises(ValueError, match="mode must be"):
            tool()

    def test_preserves_function_metadata(self):
        @catch_slug_value_error
        def tool(book_slug: str, chapter_slug: str = "") -> str:
            """Docstring."""
            return json.dumps({})

        assert tool.__name__ == "tool"
        assert tool.__doc__ == "Docstring."

    def test_sets_introspection_marker(self):
        @catch_slug_value_error
        def tool() -> str:
            return json.dumps({})

        assert tool._catches_slug_value_error is True

    def test_rejects_async_function_at_decoration_time(self):
        """Code review finding L-5: the sync wrapper would return an
        unawaited coroutine object, silently no-oping on async functions —
        worse than no decorator, since it looks applied but never runs."""
        with pytest.raises(TypeError, match="async"):

            @catch_slug_value_error
            async def tool() -> str:
                return json.dumps({})

    def test_logs_rejected_slug_server_side(self, caplog):
        """Issue #533: a rejected traversal attempt is a security-relevant
        event. The decorator already returns a clean {"error": ...} JSON
        response to the caller — but nothing recorded the attempt server-side,
        so an operator scanning logs for traversal attempts would find
        nothing."""

        @catch_slug_value_error
        def tool(slug: str) -> str:
            resolve_project_path({"paths": {"content_root": "/tmp/does-not-matter"}}, slug)
            return json.dumps({"success": True})

        with caplog.at_level(logging.WARNING, logger="tools.shared.paths"):
            tool("../escape")

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings, "expected a WARNING-level log record for the rejected slug"
        assert any("../escape" in record.getMessage() for record in warnings)

    def test_logs_without_the_decorator_present(self, caplog):
        """Code review finding on #533 (M-3): logging used to live in the
        catch_slug_value_error decorator, so a SlugValidationError raised by
        a plain helper with no decorator in between (e.g.
        tools.timeline_anchor.get_story_anchor, which calls
        _validate_slug() directly and is only wrapped by the decorator two
        call-frames up, at its MCP caller) never got logged if that helper
        were ever called directly (as it is throughout the test suite, and
        as any future non-MCP caller would). Logging now happens inside
        _validate_slug() itself, so it fires regardless of what — if
        anything — wraps the caller."""
        with caplog.at_level(logging.WARNING, logger="tools.shared.paths"):
            with pytest.raises(SlugValidationError):
                resolve_project_path({"paths": {"content_root": "/tmp/does-not-matter"}}, "../escape")

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings, "expected a WARNING-level log record even with no decorator involved"

    def test_does_not_double_log_through_the_decorator(self, caplog):
        """The decorator no longer logs independently — logging happens once,
        at the _validate_slug() raise site, not a second time when the
        decorator catches the propagated exception."""

        @catch_slug_value_error
        def tool(slug: str) -> str:
            resolve_project_path({"paths": {"content_root": "/tmp/does-not-matter"}}, slug)
            return json.dumps({"success": True})

        with caplog.at_level(logging.WARNING, logger="tools.shared.paths"):
            tool("../escape")

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1, f"expected exactly one log record, got {len(warnings)}"

    def test_logged_slug_is_escaped_against_log_injection(self, caplog):
        """Code review finding on #533 (M-4): the rejected slug reaches the
        log line verbatim. _validate_slug() only blocks '/', '\\\\', '\\x00',
        ':', '..', and a leading '.' — not embedded newlines. A slug like
        '../\\nWARNING:tools.shared.paths:rejected slug: harmless' would, if
        logged with %s, forge a second, fake log line. Logging with %r
        (repr) escapes the newline instead of emitting it literally — the
        whole rejected value stays on one physical log line."""
        evil = "../\nFORGED LOG LINE"
        with caplog.at_level(logging.WARNING, logger="tools.shared.paths"):
            with pytest.raises(SlugValidationError):
                resolve_project_path({"paths": {"content_root": "/tmp/does-not-matter"}}, evil)

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert "\n" not in message, f"rejected slug's embedded newline was not escaped: {message!r}"
        assert "FORGED LOG LINE" in message
