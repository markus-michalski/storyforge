"""Tests for the Snowflake Method scene list MCP tools.

Covers: create_scene_list() and update_scene()
Issue: #40
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


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
    from tools.state import indexer as indexer_mod

    fake_state_path = content_root / "_cache" / "state.json"

    with (
        patch.object(server_mod, "load_config", return_value=fake_config),
        patch.object(server_mod, "get_content_root", return_value=content_root),
        patch.object(indexer_mod, "load_config", return_value=fake_config),
        patch.object(indexer_mod, "STATE_PATH", fake_state_path),
        patch.object(indexer_mod, "CACHE_DIR", fake_state_path.parent),
    ):
        server_mod._cache.invalidate()
        yield fake_config


@pytest.fixture
def server_module(mock_config):  # noqa: F811
    import server as server_mod
    return server_mod


@pytest.fixture
def book_dir(content_root: Path) -> Path:
    """Create a minimal book scaffold for testing."""
    book = content_root / "projects" / "test-book"
    (book / "plot").mkdir(parents=True)
    (book / "README.md").write_text(
        "---\ntitle: Test Book\nslug: test-book\nstatus: Concept\n---\n# Test Book\n",
        encoding="utf-8",
    )
    return book


# ---------------------------------------------------------------------------
# create_scene_list tests
# ---------------------------------------------------------------------------


class TestCreateSceneList:
    def test_creates_scenes_file(self, server_module, book_dir):
        scenes = [
            {"number": 1, "chapter": "Ch. 01", "pov": "Elena", "summary": "Opens at the market", "est_words": 1200, "status": "Planned"},
            {"number": 2, "chapter": "Ch. 01", "pov": "Elena", "summary": "Confrontation with merchant", "est_words": 900, "status": "Planned"},
        ]
        result = json.loads(server_module.create_scene_list("test-book", scenes))

        assert result["success"] is True
        assert result["scene_count"] == 2
        scenes_path = book_dir / "plot" / "scenes.md"
        assert scenes_path.exists()

    def test_file_contains_all_scenes(self, server_module, book_dir):
        scenes = [
            {"number": 1, "chapter": "Ch. 01", "pov": "Elena", "summary": "Opens at the market", "est_words": 1200, "status": "Planned"},
            {"number": 2, "chapter": "Ch. 02", "pov": "Marcus", "summary": "Battle at the gate", "est_words": 2000, "status": "Planned"},
        ]
        server_module.create_scene_list("test-book", scenes)

        content = (book_dir / "plot" / "scenes.md").read_text(encoding="utf-8")
        assert "| 1 | Ch. 01 | Elena | Opens at the market | 1200 | Planned |" in content
        assert "| 2 | Ch. 02 | Marcus | Battle at the gate | 2000 | Planned |" in content

    def test_file_contains_header_and_footer(self, server_module, book_dir):
        server_module.create_scene_list("test-book", [
            {"number": 1, "chapter": "Ch. 01", "pov": "Elena", "summary": "Intro scene", "est_words": 800, "status": "Planned"},
        ])
        content = (book_dir / "plot" / "scenes.md").read_text(encoding="utf-8")
        assert "# Scene List: Test Book" in content
        assert "## Scene Index" in content
        assert "## Status Key" in content
        assert "Planned" in content
        assert "Written" in content

    def test_book_not_found_returns_error(self, server_module, content_root):
        result = json.loads(server_module.create_scene_list("nonexistent-book", []))
        assert "error" in result

    def test_overwrites_existing_scenes_file(self, server_module, book_dir):
        (book_dir / "plot" / "scenes.md").write_text("old content", encoding="utf-8")
        scenes = [{"number": 1, "chapter": "Ch. 01", "pov": "Elena", "summary": "New scene", "est_words": 500, "status": "Planned"}]
        server_module.create_scene_list("test-book", scenes)
        content = (book_dir / "plot" / "scenes.md").read_text(encoding="utf-8")
        assert "old content" not in content
        assert "New scene" in content

    def test_empty_scene_list(self, server_module, book_dir):
        result = json.loads(server_module.create_scene_list("test-book", []))
        assert result["success"] is True
        assert result["scene_count"] == 0
        content = (book_dir / "plot" / "scenes.md").read_text(encoding="utf-8")
        assert "## Scene Index" in content

    def test_uses_book_title_from_readme(self, server_module, book_dir):
        server_module.create_scene_list("test-book", [])
        content = (book_dir / "plot" / "scenes.md").read_text(encoding="utf-8")
        assert "Test Book" in content


# ---------------------------------------------------------------------------
# update_scene tests
# ---------------------------------------------------------------------------


class TestUpdateScene:
    @pytest.fixture
    def book_with_scenes(self, server_module, book_dir):
        scenes = [
            {"number": 1, "chapter": "Ch. 01", "pov": "Elena", "summary": "Opens at the market", "est_words": 1200, "status": "Planned"},
            {"number": 2, "chapter": "Ch. 01", "pov": "Marcus", "summary": "Confrontation scene", "est_words": 900, "status": "Planned"},
            {"number": 3, "chapter": "Ch. 02", "pov": "Elena", "summary": "Discovery in the vault", "est_words": 1500, "status": "Planned"},
        ]
        server_module.create_scene_list("test-book", scenes)
        return book_dir

    def test_update_status(self, server_module, book_with_scenes):
        result = json.loads(server_module.update_scene("test-book", 1, status="Written"))
        assert result["success"] is True
        content = (book_with_scenes / "plot" / "scenes.md").read_text(encoding="utf-8")
        assert "| 1 | Ch. 01 | Elena | Opens at the market | 1200 | Written |" in content

    def test_update_pov(self, server_module, book_with_scenes):
        server_module.update_scene("test-book", 2, pov="Sara")
        content = (book_with_scenes / "plot" / "scenes.md").read_text(encoding="utf-8")
        assert "| 2 | Ch. 01 | Sara | Confrontation scene | 900 | Planned |" in content

    def test_update_summary(self, server_module, book_with_scenes):
        server_module.update_scene("test-book", 3, summary="Elena finds the hidden map")
        content = (book_with_scenes / "plot" / "scenes.md").read_text(encoding="utf-8")
        assert "Elena finds the hidden map" in content

    def test_update_chapter_assignment(self, server_module, book_with_scenes):
        server_module.update_scene("test-book", 3, chapter="Ch. 03")
        content = (book_with_scenes / "plot" / "scenes.md").read_text(encoding="utf-8")
        assert "| 3 | Ch. 03 |" in content

    def test_update_est_words(self, server_module, book_with_scenes):
        server_module.update_scene("test-book", 1, est_words="1500")
        content = (book_with_scenes / "plot" / "scenes.md").read_text(encoding="utf-8")
        assert "| 1 | Ch. 01 | Elena | Opens at the market | 1500 | Planned |" in content

    def test_omitted_fields_preserved(self, server_module, book_with_scenes):
        server_module.update_scene("test-book", 2, status="Revised")
        content = (book_with_scenes / "plot" / "scenes.md").read_text(encoding="utf-8")
        assert "Confrontation scene" in content
        assert "Marcus" in content
        assert "900" in content

    def test_scene_not_found_returns_error(self, server_module, book_with_scenes):
        result = json.loads(server_module.update_scene("test-book", 99, status="Written"))
        assert "error" in result
        assert "99" in result["error"]

    def test_no_scenes_file_returns_error(self, server_module, book_dir):
        result = json.loads(server_module.update_scene("test-book", 1, status="Written"))
        assert "error" in result

    def test_other_scenes_unchanged_after_update(self, server_module, book_with_scenes):
        server_module.update_scene("test-book", 2, status="Written")
        content = (book_with_scenes / "plot" / "scenes.md").read_text(encoding="utf-8")
        assert "| 1 | Ch. 01 | Elena | Opens at the market | 1200 | Planned |" in content
        assert "| 3 | Ch. 02 | Elena | Discovery in the vault | 1500 | Planned |" in content
