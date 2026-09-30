"""Tests for the chapter-humanizer MCP tools: scan_chapter_ai_tells and
check_replacement_text."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    root.mkdir()
    return root


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))


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
def server_module(mock_config):
    import server as server_mod

    return server_mod


def _write_chapter(content_root: Path, draft: str, *, chapter: str = "01-start") -> Path:
    book = content_root / "projects" / "test-book"
    (book / "chapters" / chapter).mkdir(parents=True)
    (book / "README.md").write_text("---\ntitle: T\nslug: test-book\n---\n", encoding="utf-8")
    (book / "chapters" / chapter / "draft.md").write_text(draft, encoding="utf-8")
    return book


class TestScanChapterAiTells:
    def test_returns_hits_with_line_numbers(self, server_module, content_root) -> None:
        _write_chapter(content_root, "Rain fell.\nThe words landed between them.\n")
        result = json.loads(server_module.scan_chapter_ai_tells("test-book", "01-start"))
        assert result["book_slug"] == "test-book"
        assert result["chapter_slug"] == "01-start"
        assert [h["line"] for h in result["hits"] if h["category"] == "shape"] == [2]

    def test_includes_metrics_and_counts(self, server_module, content_root) -> None:
        _write_chapter(content_root, "Rain fell. He waited.\n")
        result = json.loads(server_module.scan_chapter_ai_tells("test-book", "01-start"))
        assert "chapter" in result["metrics"]
        assert result["counts"] == {}

    def test_missing_chapter_returns_error(self, server_module, content_root) -> None:
        _write_chapter(content_root, "Text.\n")
        result = json.loads(server_module.scan_chapter_ai_tells("test-book", "99-nope"))
        assert "error" in result

    def test_missing_book_returns_error(self, server_module) -> None:
        result = json.loads(server_module.scan_chapter_ai_tells("ghost-book", "01-start"))
        assert "error" in result

    def test_bad_slug_returns_error_json_not_exception(self, server_module) -> None:
        result = json.loads(server_module.scan_chapter_ai_tells("../etc", "01-start"))
        assert "error" in result

    @pytest.mark.parametrize("chapter", ["../..", "../../etc", "a/b", ".."])
    def test_chapter_slug_path_traversal_is_rejected(self, server_module, content_root, chapter) -> None:
        _write_chapter(content_root, "Text.\n")
        result = json.loads(server_module.scan_chapter_ai_tells("test-book", chapter))
        assert "error" in result

    @pytest.mark.parametrize("limit", [0, -1, -0.5])
    def test_non_positive_dash_limit_is_rejected(self, server_module, content_root, limit) -> None:
        _write_chapter(content_root, "One — two.\n")
        result = json.loads(server_module.scan_chapter_ai_tells("test-book", "01-start", em_dash_per_1k_limit=limit))
        assert "error" in result
        assert "em_dash_per_1k_limit" in result["error"]

    def test_reports_how_many_patterns_were_loaded(self, server_module, content_root) -> None:
        _write_chapter(content_root, "Text.\n")
        result = json.loads(server_module.scan_chapter_ai_tells("test-book", "01-start"))
        loaded = result["sources_loaded"]
        assert loaded["shapes"] > 0 and loaded["tells"] > 0
        assert loaded["author"] == 0
        assert result["warnings"] == []

    def test_unknown_author_produces_a_warning_not_a_silent_clean_scan(self, server_module, content_root) -> None:
        _write_chapter(content_root, "Text.\n")
        result = json.loads(server_module.scan_chapter_ai_tells("test-book", "01-start", author_slug="nobody"))
        assert result["sources_loaded"]["author"] == 0
        assert any("nobody" in w for w in result["warnings"])

    def test_dash_limit_argument_overrides_default(self, server_module, content_root) -> None:
        _write_chapter(content_root, "One — two.\n")
        strict = json.loads(server_module.scan_chapter_ai_tells("test-book", "01-start", em_dash_per_1k_limit=0.5))
        lax = json.loads(server_module.scan_chapter_ai_tells("test-book", "01-start", em_dash_per_1k_limit=900))
        assert [f["kind"] for f in strict["flags"] if f["kind"] == "dash_density"] == ["dash_density"]
        assert [f for f in lax["flags"] if f["kind"] == "dash_density"] == []
        assert strict["dash_limit"] == 0.5

    def test_author_profile_limit_is_used_when_no_argument(self, server_module, content_root) -> None:
        _write_chapter(content_root, "One — two.\n")
        author_dir = content_root / "authors" / "ethan"
        author_dir.mkdir(parents=True)
        (author_dir / "profile.md").write_text("---\nname: Ethan\nem_dash_per_1k_limit: 900\n---\n", encoding="utf-8")
        result = json.loads(server_module.scan_chapter_ai_tells("test-book", "01-start", author_slug="ethan"))
        assert result["dash_limit"] == 900
        assert [f for f in result["flags"] if f["kind"] == "dash_density"] == []

    def test_argument_beats_author_profile(self, server_module, content_root) -> None:
        _write_chapter(content_root, "One — two.\n")
        author_dir = content_root / "authors" / "ethan"
        author_dir.mkdir(parents=True)
        (author_dir / "profile.md").write_text("---\nem_dash_per_1k_limit: 900\n---\n", encoding="utf-8")
        result = json.loads(
            server_module.scan_chapter_ai_tells("test-book", "01-start", author_slug="ethan", em_dash_per_1k_limit=0.5)
        )
        assert result["dash_limit"] == 0.5

    def test_unknown_author_slug_does_not_break_scan(self, server_module, content_root) -> None:
        _write_chapter(content_root, "The words landed.\n")
        result = json.loads(server_module.scan_chapter_ai_tells("test-book", "01-start", author_slug="nobody"))
        assert result["counts"]["shape"] == 1

    def test_invalid_author_slug_returns_error(self, server_module, content_root) -> None:
        _write_chapter(content_root, "Text.\n")
        result = json.loads(server_module.scan_chapter_ai_tells("test-book", "01-start", author_slug="../x"))
        assert "error" in result


class TestCheckReplacementText:
    def test_clean_text(self, server_module, content_root) -> None:
        _write_chapter(content_root, "Text.\n")
        result = json.loads(server_module.check_replacement_text("test-book", "His throat tightened."))
        assert result["clean"] is True

    def test_flagged_text(self, server_module, content_root) -> None:
        _write_chapter(content_root, "Text.\n")
        result = json.loads(server_module.check_replacement_text("test-book", "The silence held."))
        assert result["clean"] is False
        assert result["hits"][0]["category"] == "shape"

    def test_unknown_author_warns_instead_of_reporting_a_silent_clean_result(self, server_module, content_root) -> None:
        _write_chapter(content_root, "Text.\n")
        result = json.loads(server_module.check_replacement_text("test-book", "Plain.", author_slug="nobody"))
        assert result["clean"] is True
        assert result["sources_loaded"]["author"] == 0
        assert any("nobody" in w for w in result["warnings"])

    def test_missing_book_returns_error(self, server_module) -> None:
        result = json.loads(server_module.check_replacement_text("ghost-book", "Text."))
        assert "error" in result

    def test_bad_slug_returns_error_json(self, server_module) -> None:
        result = json.loads(server_module.check_replacement_text("../etc", "Text."))
        assert "error" in result


def test_non_utf8_draft_returns_error_json_not_exception(server_module, content_root) -> None:
    book = _write_chapter(content_root, "placeholder\n")
    (book / "chapters" / "01-start" / "draft.md").write_bytes(b"Caf\xe9 au lait.\n")
    result = json.loads(server_module.scan_chapter_ai_tells("test-book", "01-start"))
    assert "error" in result
    assert "UTF-8" in result["error"]
