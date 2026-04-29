"""Tests for the ``book_category`` field (Issue #54, Path E memoir support).

The field distinguishes broad book categories (`fiction`, `memoir`) and gates
category-specific knowledge under `book_categories/{category}/`. It is
**orthogonal** to the existing ``book_type`` length classification
(short-story/novelette/novella/novel/epic) — both fields coexist.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.state.parsers import parse_book_readme


# ---------------------------------------------------------------------------
# Parser-level tests — backwards compatibility + read-through
# ---------------------------------------------------------------------------


class TestParseBookCategory:
    """parse_book_readme must expose book_category with a fiction default."""

    def test_missing_field_defaults_to_fiction(self, tmp_path: Path):
        # Existing books written before #54 have no book_category — must not break.
        book_dir = tmp_path / "legacy-book"
        book_dir.mkdir()
        (book_dir / "README.md").write_text(
            '---\ntitle: "Legacy Book"\nbook_type: "novel"\n---\n# Legacy\n',
            encoding="utf-8",
        )

        result = parse_book_readme(book_dir / "README.md")

        assert result["book_category"] == "fiction", (
            "Missing book_category must default to 'fiction' for backwards compat"
        )

    def test_explicit_fiction_reads_through(self, tmp_path: Path):
        book_dir = tmp_path / "explicit-fiction"
        book_dir.mkdir()
        (book_dir / "README.md").write_text(
            '---\ntitle: "Test"\nbook_category: "fiction"\n---\n# T\n',
            encoding="utf-8",
        )

        result = parse_book_readme(book_dir / "README.md")
        assert result["book_category"] == "fiction"

    def test_explicit_memoir_reads_through(self, tmp_path: Path):
        book_dir = tmp_path / "memoir-book"
        book_dir.mkdir()
        (book_dir / "README.md").write_text(
            '---\ntitle: "My Memoir"\nbook_category: "memoir"\n---\n# M\n',
            encoding="utf-8",
        )

        result = parse_book_readme(book_dir / "README.md")
        assert result["book_category"] == "memoir"

    def test_book_category_independent_of_book_type(self, tmp_path: Path):
        # book_type = length classification; book_category = fiction/memoir.
        # Both must coexist without interfering.
        book_dir = tmp_path / "memoir-novella"
        book_dir.mkdir()
        (book_dir / "README.md").write_text(
            '---\ntitle: "Short Memoir"\nbook_type: "novella"\nbook_category: "memoir"\n---\n# X\n',
            encoding="utf-8",
        )

        result = parse_book_readme(book_dir / "README.md")
        assert result["book_type"] == "novella"
        assert result["book_category"] == "memoir"


# ---------------------------------------------------------------------------
# create_book_structure tool — schema + validation
# ---------------------------------------------------------------------------


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    root.mkdir()
    return root


@pytest.fixture
def mock_config(content_root: Path):
    fake_config = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(content_root / "authors"),
        },
        "defaults": {
            "language": "en",
            "book_type": "novel",
            "book_category": "fiction",
        },
    }

    import routers._app as server_mod
    from tools.state import indexer as indexer_mod  # noqa: WPS433

    # Patch both server_mod (create_book_structure path) and indexer_mod
    # (cache rebuild path) so the cache scan sees the test content_root.
    with (
        patch.object(server_mod, "load_config", return_value=fake_config),
        patch.object(server_mod, "get_content_root", return_value=content_root),
        patch.object(indexer_mod, "load_config", return_value=fake_config),
    ):
        server_mod._cache.invalidate()
        yield fake_config


@pytest.fixture
def server_module(mock_config):  # noqa: F811
    import server as server_mod

    return server_mod


def _read_book_frontmatter(content_root: Path, slug: str) -> dict:
    import yaml

    readme = content_root / "projects" / slug / "README.md"
    text = readme.read_text(encoding="utf-8")
    # naive frontmatter extraction: text between first two "---" lines
    parts = text.split("---", 2)
    assert len(parts) >= 3, "README must have YAML frontmatter"
    return yaml.safe_load(parts[1]) or {}


class TestCreateBookStructureBookCategory:
    """create_book_structure must accept and persist book_category."""

    def test_default_book_category_is_fiction(self, server_module, content_root: Path):
        # No book_category param → default "fiction" lands in README.
        result = json.loads(server_module.create_book_structure(title="Default Cat Book"))
        assert result.get("success") is True

        meta = _read_book_frontmatter(content_root, "default-cat-book")
        assert meta["book_category"] == "fiction"

    def test_explicit_memoir_category_persisted(self, server_module, content_root: Path):
        result = json.loads(
            server_module.create_book_structure(
                title="My Memoir Project",
                book_category="memoir",
            )
        )
        assert result.get("success") is True

        meta = _read_book_frontmatter(content_root, "my-memoir-project")
        assert meta["book_category"] == "memoir"

    def test_invalid_book_category_rejected(self, server_module, content_root: Path):
        # Phase 1 only supports fiction|memoir. Other non-fiction subtypes
        # (biography, how-to, academic, history) are explicitly out of scope
        # per #49 / #97.
        result = json.loads(
            server_module.create_book_structure(
                title="Biography Attempt",
                book_category="biography",
            )
        )
        assert "error" in result
        assert "book_category" in result["error"].lower()

        # No directory must be created on rejection.
        assert not (content_root / "projects" / "biography-attempt").exists()

    def test_book_category_orthogonal_to_book_type(self, server_module, content_root: Path):
        # Memoir + novella length is a valid combo.
        result = json.loads(
            server_module.create_book_structure(
                title="Short Memoir",
                book_type="novella",
                book_category="memoir",
            )
        )
        assert result.get("success") is True

        meta = _read_book_frontmatter(content_root, "short-memoir")
        assert meta["book_type"] == "novella"
        assert meta["book_category"] == "memoir"


# ---------------------------------------------------------------------------
# list_books projection — book_category surfaces in cache
# ---------------------------------------------------------------------------


class TestListBooksBookCategory:
    """list_books MCP tool must expose book_category in each entry."""

    def test_list_books_includes_book_category(self, server_module, content_root: Path):
        # Create one fiction, one memoir.
        json.loads(server_module.create_book_structure(title="Fiction One"))
        json.loads(server_module.create_book_structure(title="Memoir One", book_category="memoir"))

        # Force cache rebuild so list_books sees fresh state.
        server_module._cache.invalidate()

        result = json.loads(server_module.list_books())
        by_slug = {b["slug"]: b for b in result["books"]}

        assert by_slug["fiction-one"]["book_category"] == "fiction"
        assert by_slug["memoir-one"]["book_category"] == "memoir"


# ---------------------------------------------------------------------------
# Scaffold layout — Issue #63 (Phase 2): fiction vs. memoir directory tree
# ---------------------------------------------------------------------------


class TestScaffoldFictionLayout:
    """Fiction scaffold preserves the historical layout (regression guard)."""

    def test_fiction_creates_characters_and_world(self, server_module, content_root: Path):
        result = json.loads(server_module.create_book_structure(title="Fiction Layout"))
        assert result.get("success") is True

        project = content_root / "projects" / "fiction-layout"
        assert (project / "characters").is_dir()
        assert (project / "characters" / "INDEX.md").is_file()
        assert (project / "world").is_dir()
        assert (project / "world" / "setting.md").is_file()
        assert (project / "world" / "rules.md").is_file()
        assert (project / "world" / "history.md").is_file()
        assert (project / "world" / "glossary.md").is_file()
        assert not (project / "people").exists()

    def test_fiction_plot_files_are_three_act(self, server_module, content_root: Path):
        json.loads(server_module.create_book_structure(title="Fiction Plot"))

        outline = (content_root / "projects" / "fiction-plot" / "plot" / "outline.md").read_text(encoding="utf-8")
        assert "Act 1: Setup" in outline
        assert "Act 2: Confrontation" in outline
        assert "Act 3: Resolution" in outline

        # Fiction keeps acts.md and arcs.md
        plot_dir = content_root / "projects" / "fiction-plot" / "plot"
        assert (plot_dir / "acts.md").is_file()
        assert (plot_dir / "arcs.md").is_file()
        assert not (plot_dir / "structure.md").exists()


class TestScaffoldMemoirLayout:
    """Memoir scaffold swaps characters→people, drops world/, drops plot/arcs."""

    def test_memoir_creates_people_not_characters(self, server_module, content_root: Path):
        result = json.loads(server_module.create_book_structure(title="Memoir Layout", book_category="memoir"))
        assert result.get("success") is True

        project = content_root / "projects" / "memoir-layout"
        assert (project / "people").is_dir()
        assert (project / "people" / "INDEX.md").is_file()
        # No fiction-shaped characters/ scaffolded for memoir.
        assert not (project / "characters").exists()

    def test_memoir_skips_world_directory(self, server_module, content_root: Path):
        # Memoir documents real settings via research, not invented worlds.
        json.loads(server_module.create_book_structure(title="No World Memoir", book_category="memoir"))

        project = content_root / "projects" / "no-world-memoir"
        assert not (project / "world").exists(), "Memoir scaffold must skip world/ entirely (#63 spec)"

    def test_memoir_people_index_mentions_consent(self, server_module, content_root: Path):
        # The INDEX must hint at memoir-specific concerns
        # (consent, anonymization) so users know real-people ethics applies.
        json.loads(server_module.create_book_structure(title="Consent Memoir", book_category="memoir"))

        index = (content_root / "projects" / "consent-memoir" / "people" / "INDEX.md").read_text(encoding="utf-8")
        assert "consent" in index.lower() or "anonymization" in index.lower()
        # Sections should be people-shaped, not character-shaped.
        assert "Protagonists" not in index
        assert "Antagonists" not in index

    def test_memoir_plot_uses_structure_types_not_acts(self, server_module, content_root: Path):
        # Memoir's outline.md must point at structure types
        # (chronological/thematic/braided/vignette), not three-act structure.
        json.loads(server_module.create_book_structure(title="Structure Memoir", book_category="memoir"))

        plot_dir = content_root / "projects" / "structure-memoir" / "plot"
        outline = (plot_dir / "outline.md").read_text(encoding="utf-8")

        assert "Act 1" not in outline
        assert "structure type" in outline.lower() or "chronological" in outline.lower()

        # Memoir adds structure.md, drops arcs.md (no character arcs in memoir)
        # and acts.md (no three-act).
        assert (plot_dir / "structure.md").is_file()
        assert not (plot_dir / "arcs.md").exists()
        assert not (plot_dir / "acts.md").exists()

    def test_memoir_keeps_shared_dirs(self, server_module, content_root: Path):
        # Shared infrastructure (chapters/, research/, cover/, export/, plot/timeline+tone)
        # must remain identical across categories.
        json.loads(server_module.create_book_structure(title="Shared Dirs Memoir", book_category="memoir"))

        project = content_root / "projects" / "shared-dirs-memoir"
        assert (project / "chapters").is_dir()
        assert (project / "research" / "notes").is_dir()
        assert (project / "cover" / "art").is_dir()
        assert (project / "export" / "output").is_dir()
        assert (project / "translations").is_dir()
        assert (project / "plot" / "timeline.md").is_file()
        assert (project / "plot" / "tone.md").is_file()


# ---------------------------------------------------------------------------
# get_book_progress — surface book_category for the dashboard
# ---------------------------------------------------------------------------


class TestGetBookProgressBookCategory:
    """get_book_progress must expose book_category so book-dashboard can render it."""

    def test_progress_includes_book_category_for_fiction(self, server_module, content_root: Path):
        json.loads(server_module.create_book_structure(title="Progress Fiction"))
        server_module._cache.invalidate()

        result = json.loads(server_module.get_book_progress("progress-fiction"))
        assert result["book_category"] == "fiction"

    def test_progress_includes_book_category_for_memoir(self, server_module, content_root: Path):
        json.loads(server_module.create_book_structure(title="Progress Memoir", book_category="memoir"))
        server_module._cache.invalidate()

        result = json.loads(server_module.get_book_progress("progress-memoir"))
        assert result["book_category"] == "memoir"


# ---------------------------------------------------------------------------
# get_book_category_dir tool — Issue #55 path resolution
# ---------------------------------------------------------------------------


class TestGetBookCategoryDir:
    """Skills must be able to resolve book_categories/{category}/ via MCP."""

    def test_resolves_fiction_category(self, server_module):
        result = json.loads(server_module.get_book_category_dir("fiction"))

        assert result["category"] == "fiction"
        assert result["path"].endswith("book_categories/fiction")
        # The fiction scaffold ships with the plugin, so it must exist.
        assert result["exists"] is True

    def test_resolves_memoir_category(self, server_module):
        result = json.loads(server_module.get_book_category_dir("memoir"))

        assert result["category"] == "memoir"
        assert result["path"].endswith("book_categories/memoir")
        assert result["exists"] is True

    def test_rejects_unknown_category(self, server_module):
        result = json.loads(server_module.get_book_category_dir("biography"))

        assert "error" in result
        assert "biography" in result["error"]
