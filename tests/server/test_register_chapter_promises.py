"""Server-level tests for ``register_chapter_promises`` and
``get_chapter_promises`` MCP tools (Issue #150).

The unit-level merge/parse logic is covered in
``tests/state/test_promises.py``. These tests cover only the MCP
tool integration: argument validation, error envelopes, and the
JSON contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures (mirrored from test_start_chapter_draft.py)
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


def _write_chapter(content_root: Path, book: str, chapter: str) -> Path:
    project = content_root / "projects" / book
    project.mkdir(parents=True, exist_ok=True)
    (project / "README.md").write_text(
        f'---\ntitle: "Test"\nslug: "{book}"\n---\n# Test\n',
        encoding="utf-8",
    )
    (project / "chapters").mkdir(exist_ok=True)
    ch_dir = project / "chapters" / chapter
    ch_dir.mkdir(parents=True)
    (ch_dir / "README.md").write_text(
        f"# {chapter}\n\n## Outline\n\nOutline body.\n\n## Notes\n\nNotes.\n",
        encoding="utf-8",
    )
    return ch_dir


# ---------------------------------------------------------------------------
# register_chapter_promises
# ---------------------------------------------------------------------------


class TestRegisterChapterPromises:
    def test_writes_section_for_chapter_without_one(self, server_module, content_root: Path):
        _write_chapter(content_root, "book-a", "05-meeting")

        result = json.loads(
            server_module.register_chapter_promises(
                "book-a",
                "05-meeting",
                [
                    {
                        "description": "The locked drawer",
                        "target": "14-letter",
                        "status": "active",
                    }
                ],
            )
        )

        assert result["success"] is True
        assert result["added"] == 1
        assert result["updated"] == 0

        readme_text = (content_root / "projects" / "book-a" / "chapters" / "05-meeting" / "README.md").read_text(
            encoding="utf-8"
        )
        assert "## Promises" in readme_text
        assert "| The locked drawer | 14-letter | active |" in readme_text

    def test_status_defaults_to_active_when_omitted(self, server_module, content_root: Path):
        _write_chapter(content_root, "book-b", "01-start")
        result = json.loads(
            server_module.register_chapter_promises(
                "book-b",
                "01-start",
                [{"description": "X", "target": "unfired"}],
            )
        )
        assert result["success"] is True
        readme = (content_root / "projects" / "book-b" / "chapters" / "01-start" / "README.md").read_text(
            encoding="utf-8"
        )
        assert "| X | unfired | active |" in readme

    def test_returns_error_for_missing_chapter(self, server_module, content_root: Path):
        _write_chapter(content_root, "book-c", "01-real")
        result = json.loads(
            server_module.register_chapter_promises("book-c", "99-fake", [{"description": "X", "target": "unfired"}])
        )
        assert "error" in result

    def test_returns_error_for_invalid_status(self, server_module, content_root: Path):
        _write_chapter(content_root, "book-d", "01-start")
        result = json.loads(
            server_module.register_chapter_promises(
                "book-d",
                "01-start",
                [{"description": "X", "target": "unfired", "status": "in-progress"}],
            )
        )
        assert "error" in result
        assert "status" in result["error"]

    def test_returns_error_for_empty_description(self, server_module, content_root: Path):
        _write_chapter(content_root, "book-e", "01-start")
        result = json.loads(
            server_module.register_chapter_promises(
                "book-e",
                "01-start",
                [{"description": "  ", "target": "unfired"}],
            )
        )
        assert "error" in result
        assert "description" in result["error"]

    def test_idempotent_second_call(self, server_module, content_root: Path):
        _write_chapter(content_root, "book-f", "01-start")
        promises = [{"description": "Y", "target": "unfired", "status": "active"}]

        first = json.loads(server_module.register_chapter_promises("book-f", "01-start", promises))
        second = json.loads(server_module.register_chapter_promises("book-f", "01-start", promises))

        assert first["added"] == 1
        assert second["added"] == 0
        assert second["unchanged"] == 1


# ---------------------------------------------------------------------------
# get_chapter_promises
# ---------------------------------------------------------------------------


class TestGetChapterPromises:
    def test_returns_empty_for_chapter_without_section(self, server_module, content_root: Path):
        _write_chapter(content_root, "book-g", "01-start")
        result = json.loads(server_module.get_chapter_promises("book-g", "01-start"))
        assert result["promises"] == []

    def test_roundtrip_register_then_get(self, server_module, content_root: Path):
        _write_chapter(content_root, "book-h", "01-start")
        server_module.register_chapter_promises(
            "book-h",
            "01-start",
            [
                {"description": "Drawer", "target": "14-letter", "status": "active"},
                {"description": "Rifle", "target": "unfired", "status": "active"},
            ],
        )
        result = json.loads(server_module.get_chapter_promises("book-h", "01-start"))
        assert len(result["promises"]) == 2
        assert result["promises"][0]["description"] == "Drawer"
        assert result["promises"][1]["status"] == "active"
