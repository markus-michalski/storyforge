"""Tests for the get_character MCP tool (issue #29)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.claudemd import get_character


@pytest.fixture
def config(tmp_path: Path) -> dict:
    content_root = tmp_path / "books"
    book_dir = content_root / "projects" / "my-book" / "characters"
    book_dir.mkdir(parents=True)
    return {"paths": {"content_root": str(content_root)}}


@pytest.fixture
def config_with_character(config: dict, tmp_path: Path) -> dict:
    char_file = tmp_path / "books" / "projects" / "my-book" / "characters" / "jane-doe.md"
    char_file.write_text("# Jane Doe\n\nProtagonist. Sharp wit, hidden grief.\n", encoding="utf-8")
    return config


@pytest.fixture
def config_legacy_layout(config: dict, tmp_path: Path) -> dict:
    """Character stored in legacy folder-per-character layout."""
    legacy_dir = tmp_path / "books" / "projects" / "my-book" / "characters" / "old-hero"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "README.md").write_text("# Old Hero\n\nLegacy character.\n", encoding="utf-8")
    return config


class TestGetCharacter:
    def test_hit_returns_content(self, config_with_character: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_app, "load_config", lambda: config_with_character)
        result = json.loads(get_character("my-book", "jane-doe"))
        assert "content" in result
        assert "Jane Doe" in result["content"]

    def test_miss_bad_book(self, config: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_app, "load_config", lambda: config)
        result = json.loads(get_character("nonexistent-book", "jane-doe"))
        assert "error" in result
        assert "nonexistent-book" in result["error"]

    def test_miss_bad_character(self, config_with_character: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_app, "load_config", lambda: config_with_character)
        result = json.loads(get_character("my-book", "nobody"))
        assert "error" in result
        assert "nobody" in result["error"]

    def test_legacy_layout_fallback(self, config_legacy_layout: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_app, "load_config", lambda: config_legacy_layout)
        result = json.loads(get_character("my-book", "old-hero"))
        assert "content" in result
        assert "Legacy character" in result["content"]
