"""Tests for scaffold-convention tolerance.

Covers two related bugs:

* Issue #16 — chapter status lives in `chapter.yaml` next to README.md, but the
  parser only reads README frontmatter and silently defaults to "Outline".
* Issue #17 — the MCP hardcodes `world/` everywhere, so books scaffolded with
  `worldbuilding/` (or `world-building/`) are silently invisible to
  `resolve_path`, `validate_book_structure`, and skill prerequisites.

Both bugs share a root cause: the MCP assumed a single canonical layout. The
fix adds tolerant detection (chapter.yaml fallback, world-dir alias table)
without forcing a migration.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.state.indexer import _scan_chapters
from tools.state.parsers import parse_chapter_readme


# ---------------------------------------------------------------------------
# Fixtures
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
        "defaults": {"language": "en", "book_type": "novel"},
    }

    import routers._app as server_mod

    with (
        patch.object(server_mod, "load_config", return_value=fake_config),
        patch.object(server_mod, "get_content_root", return_value=content_root),
    ):
        server_mod._cache.invalidate()
        yield fake_config


@pytest.fixture
def server_module(mock_config):  # noqa: F811
    import server as server_mod

    return server_mod


def _write_book_skeleton(content_root: Path, slug: str = "test-book") -> Path:
    """Create the minimum structure needed by validate_book_structure."""
    project = content_root / "projects" / slug
    project.mkdir(parents=True)
    (project / "README.md").write_text(
        f'---\ntitle: "Test Book"\nslug: "{slug}"\nstatus: "Drafting"\n---\n# Test\n',
        encoding="utf-8",
    )
    (project / "synopsis.md").write_text("# Synopsis\n", encoding="utf-8")
    (project / "plot").mkdir()
    (project / "plot" / "outline.md").write_text("# Outline\n", encoding="utf-8")
    (project / "characters").mkdir()
    (project / "characters" / "INDEX.md").write_text("# Chars\n", encoding="utf-8")
    return project


# ---------------------------------------------------------------------------
# Issue #16 — chapter.yaml fallback in parse_chapter_readme
# ---------------------------------------------------------------------------


class TestChapterYamlFallback:
    """parse_chapter_readme must consult chapter.yaml when README has no frontmatter."""

    def test_chapter_yaml_supplies_status_when_readme_has_none(self, tmp_path: Path):
        # README.md without any frontmatter (the bug scenario)
        ch_dir = tmp_path / "01-invisible"
        ch_dir.mkdir()
        (ch_dir / "README.md").write_text(
            "# Chapter 1\n\nPlain markdown body, no frontmatter at all.\n",
            encoding="utf-8",
        )
        (ch_dir / "chapter.yaml").write_text(
            'title: "Invisible"\nstatus: review\nwords: 4047\npov: "Theo Wilkons"\nact: 1\n',
            encoding="utf-8",
        )

        result = parse_chapter_readme(ch_dir / "README.md")

        # Status from chapter.yaml — normalized to canonical form ("review" → "Revision")
        assert result["status"] != "Outline", "Bug #16: status must come from chapter.yaml, not the README default"
        assert result["title"] == "Invisible"

    def test_chapter_yaml_takes_precedence_over_readme_default(self, tmp_path: Path):
        # Both files exist; chapter.yaml wins (Option A from issue #16)
        ch_dir = tmp_path / "02-conflict"
        ch_dir.mkdir()
        (ch_dir / "README.md").write_text(
            '---\ntitle: "Stale Title"\nstatus: "Outline"\n---\n# Body\n',
            encoding="utf-8",
        )
        (ch_dir / "chapter.yaml").write_text(
            'title: "Fresh Title"\nstatus: "Draft"\n',
            encoding="utf-8",
        )

        result = parse_chapter_readme(ch_dir / "README.md")

        assert result["title"] == "Fresh Title"
        assert result["status"] == "Draft"

    def test_readme_frontmatter_still_works_when_no_chapter_yaml(self, tmp_path: Path):
        # Backward compatibility: existing books without chapter.yaml unchanged.
        ch_dir = tmp_path / "03-classic"
        ch_dir.mkdir()
        (ch_dir / "README.md").write_text(
            '---\ntitle: "Classic"\nstatus: "Final"\nnumber: 3\n---\n# Body\n',
            encoding="utf-8",
        )

        result = parse_chapter_readme(ch_dir / "README.md")

        assert result["title"] == "Classic"
        assert result["status"] == "Final"
        assert result["number"] == 3

    def test_no_metadata_anywhere_falls_back_to_outline(self, tmp_path: Path):
        # Edge: neither file has metadata — keep the historical default.
        ch_dir = tmp_path / "04-empty"
        ch_dir.mkdir()
        (ch_dir / "README.md").write_text("# Body only\n", encoding="utf-8")

        result = parse_chapter_readme(ch_dir / "README.md")

        assert result["status"] == "Outline"

    def test_indexer_picks_up_chapter_yaml_status(self, tmp_path: Path):
        # End-to-end: the indexer reflects chapter.yaml status in scanned data.
        chapters_dir = tmp_path / "chapters"
        ch_dir = chapters_dir / "01-invisible"
        ch_dir.mkdir(parents=True)
        (ch_dir / "README.md").write_text("# Chapter 1\n\nPlain prose.\n", encoding="utf-8")
        (ch_dir / "chapter.yaml").write_text('title: "Invisible"\nstatus: review\n', encoding="utf-8")

        result = _scan_chapters(chapters_dir)

        assert "01-invisible" in result
        assert result["01-invisible"]["status"] != "Outline"


class TestCreateChapterWritesBoth:
    """create_chapter must also write chapter.yaml so future reads stay consistent."""

    def test_create_chapter_writes_chapter_yaml_alongside_readme(self, server_module, content_root: Path):
        _write_book_skeleton(content_root)

        result = json.loads(
            server_module.create_chapter(
                book_slug="test-book",
                title="Opening",
                number=1,
                pov_character="Alex",
                summary="The hero arrives.",
            )
        )

        assert result.get("success") is True
        ch_dir = content_root / "projects" / "test-book" / "chapters" / "01-opening"
        assert (ch_dir / "README.md").exists()
        assert (ch_dir / "chapter.yaml").exists(), "Bug #16 fix: chapter.yaml must be created alongside README.md"

        import yaml

        meta = yaml.safe_load((ch_dir / "chapter.yaml").read_text(encoding="utf-8"))
        assert meta["title"] == "Opening"
        assert meta["status"] == "Outline"
        assert meta["number"] == 1


# ---------------------------------------------------------------------------
# Issue #17 — world/ vs worldbuilding/ alias
# ---------------------------------------------------------------------------


class TestResolveWorldDir:
    """The world-dir helper must accept multiple sensible directory names."""

    def test_returns_world_when_present(self, tmp_path: Path):
        from tools.shared.paths import resolve_world_dir

        (tmp_path / "world").mkdir()
        assert resolve_world_dir(tmp_path) == tmp_path / "world"

    def test_falls_back_to_worldbuilding(self, tmp_path: Path):
        from tools.shared.paths import resolve_world_dir

        (tmp_path / "worldbuilding").mkdir()
        assert resolve_world_dir(tmp_path) == tmp_path / "worldbuilding"

    def test_falls_back_to_world_building_with_dash(self, tmp_path: Path):
        from tools.shared.paths import resolve_world_dir

        (tmp_path / "world-building").mkdir()
        assert resolve_world_dir(tmp_path) == tmp_path / "world-building"

    def test_canonical_world_wins_when_multiple_exist(self, tmp_path: Path):
        from tools.shared.paths import resolve_world_dir

        (tmp_path / "world").mkdir()
        (tmp_path / "worldbuilding").mkdir()
        assert resolve_world_dir(tmp_path) == tmp_path / "world"

    def test_returns_none_when_no_world_dir_exists(self, tmp_path: Path):
        from tools.shared.paths import resolve_world_dir

        assert resolve_world_dir(tmp_path) is None


class TestResolvePathWorldAlias:
    """server.resolve_path(component='world') must accept worldbuilding/."""

    def test_resolves_to_worldbuilding_when_only_alias_exists(self, server_module, content_root: Path):
        project = _write_book_skeleton(content_root, slug="alt-book")
        # Remove the canonical scaffold-created world/ if any (none in skeleton helper)
        # and add the alias instead.
        (project / "worldbuilding").mkdir()
        (project / "worldbuilding" / "setting.md").write_text("# Setting\n", encoding="utf-8")

        result = json.loads(server_module.resolve_path("alt-book", component="world"))

        assert result["exists"] is True, "Bug #17 fix: resolve_path('world') must find worldbuilding/ as fallback"
        assert result["path"].endswith("worldbuilding")

    def test_resolves_to_world_when_canonical_exists(self, server_module, content_root: Path):
        project = _write_book_skeleton(content_root, slug="canon-book")
        (project / "world").mkdir()
        (project / "world" / "setting.md").write_text("# Setting\n", encoding="utf-8")

        result = json.loads(server_module.resolve_path("canon-book", component="world"))

        assert result["exists"] is True
        assert result["path"].endswith("world")


class TestValidateBookStructureWorldAlias:
    """validate_book_structure must accept any recognized world-dir name."""

    def test_validates_with_worldbuilding(self, server_module, content_root: Path):
        project = _write_book_skeleton(content_root, slug="alt-book")
        (project / "worldbuilding").mkdir()
        (project / "worldbuilding" / "setting.md").write_text("# Setting\n", encoding="utf-8")

        result = json.loads(server_module.validate_book_structure("alt-book"))

        world_check = next(
            (c for c in result["checks"] if c["check"].endswith("setting.md")),
            None,
        )
        assert world_check is not None, "validate_book_structure must include a world-setting check"
        assert world_check["status"] == "PASS", "Bug #17 fix: world-setting check must accept worldbuilding/ as alias"

    def test_validates_with_canonical_world(self, server_module, content_root: Path):
        project = _write_book_skeleton(content_root, slug="canon-book")
        (project / "world").mkdir()
        (project / "world" / "setting.md").write_text("# Setting\n", encoding="utf-8")

        result = json.loads(server_module.validate_book_structure("canon-book"))

        world_check = next(
            (c for c in result["checks"] if c["check"].endswith("setting.md")),
            None,
        )
        assert world_check is not None
        assert world_check["status"] == "PASS"
