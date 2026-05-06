"""Tests for the MCP tool sweep (Issue #175).

Verifies that:
- The four deprecated tools emit a DeprecationWarning on every call.
- Deprecated tools still return usable data (backward-compat, removal in v2.0).
- Each deprecated tool's JSON response carries a ``_deprecated`` field with a
  rationale string so the model knows not to rely on it.
- CLAUDE.md documents list_craft_references, validate_timeline_consistency,
  and get_review_handle_config as user-callable utilities.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

import routers._app as _app
from routers.chapters import get_chapter
from routers.claudemd import get_character, update_book_claudemd_facts
from routers.series import get_series

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
CLAUDEMD = PLUGIN_ROOT / "CLAUDE.md"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config_books(tmp_path: Path) -> dict:
    content_root = tmp_path / "books"
    (content_root / "projects").mkdir(parents=True)
    return {"paths": {"content_root": str(content_root)}}


@pytest.fixture
def config_with_book(config_books: dict, tmp_path: Path) -> dict:
    book_dir = tmp_path / "books" / "projects" / "test-book"
    book_dir.mkdir(parents=True)
    (book_dir / "README.md").write_text(
        "---\ntitle: Test Book\nstatus: Drafting\n---\n", encoding="utf-8"
    )
    return config_books


@pytest.fixture
def config_with_chapter(config_with_book: dict, tmp_path: Path) -> dict:
    ch_dir = tmp_path / "books" / "projects" / "test-book" / "chapters" / "ch01"
    ch_dir.mkdir(parents=True)
    (ch_dir / "README.md").write_text("---\ntitle: Chapter 1\n---\n", encoding="utf-8")
    return config_with_book


@pytest.fixture
def config_with_character(config_with_book: dict, tmp_path: Path) -> dict:
    char_dir = tmp_path / "books" / "projects" / "test-book" / "characters"
    char_dir.mkdir(parents=True)
    (char_dir / "hero.md").write_text("# Hero\n\nProtagonist.\n", encoding="utf-8")
    return config_with_book


@pytest.fixture
def config_with_series(tmp_path: Path) -> dict:
    content_root = tmp_path / "books"
    series_dir = content_root / "series" / "my-series"
    series_dir.mkdir(parents=True)
    return {"paths": {"content_root": str(content_root)}}


@pytest.fixture
def config_with_claudemd(config_with_book: dict, tmp_path: Path) -> dict:
    book_dir = tmp_path / "books" / "projects" / "test-book"
    (book_dir / "CLAUDE.md").write_text(
        "## Book Facts\npov: first\ntense: past\n", encoding="utf-8"
    )
    return config_with_book


# ---------------------------------------------------------------------------
# get_chapter — deprecated
# ---------------------------------------------------------------------------


class TestGetChapterDeprecated:
    def test_emits_deprecation_warning(self, config_with_chapter: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_app, "load_config", lambda: config_with_chapter)
        # Rebuild cache so the chapter appears in state
        from routers.state import rebuild_state
        rebuild_state()
        with pytest.warns(DeprecationWarning, match="get_book_full"):
            get_chapter("test-book", "ch01")

    def test_still_returns_data_or_graceful_error(
        self, config_with_chapter: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_app, "load_config", lambda: config_with_chapter)
        from routers.state import rebuild_state
        rebuild_state()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = json.loads(get_chapter("test-book", "ch01"))
        assert "_deprecated" in result

    def test_response_carries_deprecated_field(
        self, config_with_chapter: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_app, "load_config", lambda: config_with_chapter)
        from routers.state import rebuild_state
        rebuild_state()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = json.loads(get_chapter("test-book", "ch01"))
        assert isinstance(result["_deprecated"], str)
        assert len(result["_deprecated"]) > 0


# ---------------------------------------------------------------------------
# get_character — deprecated
# ---------------------------------------------------------------------------


class TestGetCharacterDeprecated:
    def test_emits_deprecation_warning(
        self, config_with_character: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_app, "load_config", lambda: config_with_character)
        with pytest.warns(DeprecationWarning, match="get_book_full"):
            get_character("test-book", "hero")

    def test_response_carries_deprecated_field(
        self, config_with_character: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_app, "load_config", lambda: config_with_character)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = json.loads(get_character("test-book", "hero"))
        assert "_deprecated" in result


# ---------------------------------------------------------------------------
# get_series — deprecated
# ---------------------------------------------------------------------------


class TestGetSeriesDeprecated:
    def test_emits_deprecation_warning(
        self, config_with_series: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_app, "load_config", lambda: config_with_series)
        from routers.state import rebuild_state
        rebuild_state()
        with pytest.warns(DeprecationWarning, match="series"):
            get_series("unknown-series")

    def test_response_carries_deprecated_field(
        self, config_with_series: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_app, "load_config", lambda: config_with_series)
        from routers.state import rebuild_state
        rebuild_state()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = json.loads(get_series("unknown-series"))
        assert "_deprecated" in result


# ---------------------------------------------------------------------------
# update_book_claudemd_facts — deprecated
# ---------------------------------------------------------------------------


class TestUpdateBookClaudemdFactsDeprecated:
    def test_emits_deprecation_warning(
        self, config_with_claudemd: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_app, "load_config", lambda: config_with_claudemd)
        with pytest.warns(DeprecationWarning, match="PreCompact"):
            update_book_claudemd_facts("test-book", pov="third")

    def test_response_carries_deprecated_field(
        self, config_with_claudemd: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_app, "load_config", lambda: config_with_claudemd)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = json.loads(update_book_claudemd_facts("test-book", pov="third"))
        assert "_deprecated" in result


# ---------------------------------------------------------------------------
# CLAUDE.md — user-callable utilities documented
# ---------------------------------------------------------------------------


class TestUserCallableUtilitiesDocumented:
    def test_claudemd_has_user_callable_section(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "User-Callable MCP Tools" in text or "user-callable" in text.lower(), (
            "CLAUDE.md must document user-callable MCP tools"
        )

    def test_list_craft_references_documented(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "list_craft_references" in text

    def test_validate_timeline_consistency_documented(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "validate_timeline_consistency" in text

    def test_get_review_handle_config_documented(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "get_review_handle_config" in text
