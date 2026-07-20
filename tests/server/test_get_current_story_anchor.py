"""Tests for the ``get_current_story_anchor`` MCP tool's session fallback.

Issue #378 wires three skills (chapter-writer, chapter-writer-memoir,
rolling-planner) to call ``update_session(last_chapter=...)`` so this tool's
documented fallback ("when chapter_slug is empty, uses the session's
last_chapter") actually has something to read.

That fallback previously read the file-backed state cache's ``session`` key
(``_cache.get()["session"]``), which is a permanently-empty placeholder
(see ``tools/state/indexer.py::build_state``) — completely disconnected
from the SQLite-backed session store ``update_session()`` writes to
(Issue #280). The fallback was dead code in practice: ``update_session()``
calls could never make it resolve. Fixed alongside #378 so the session
pointer these skills now write is actually the one this tool reads.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures (mirrored from tests/server/test_start_chapter_draft.py)
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
def isolated_session_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the global sessions DB at a fresh tmp_path for this test.

    Mirrors tests/server/test_update_session_tool.py's fixture of the same
    name — session storage (Issue #280) lives in its own SQLite file
    independent of the content-root state cache, so it needs its own
    isolation.
    """
    import tools.db.connection as conn_mod

    monkeypatch.setattr(conn_mod, "DB_DIR", tmp_path / "db")


def _write_book_with_chapter(content_root: Path, book_slug: str, chapter_slug: str) -> None:
    project = content_root / "projects" / book_slug
    project.mkdir(parents=True, exist_ok=True)
    (project / "README.md").write_text(
        f'---\ntitle: "Test Book"\nslug: "{book_slug}"\nstatus: "Drafting"\n---\n# Test Book\n',
        encoding="utf-8",
    )
    ch_dir = project / "chapters" / chapter_slug
    ch_dir.mkdir(parents=True)
    (ch_dir / "README.md").write_text(
        f"# {chapter_slug}\n\n"
        "## Chapter Timeline\n\n"
        "**Start:** Tue Dec 24 ~19:30 (library window seat)\n"
        "**End:** Wed Dec 25 ~07:00 (trailhead, engine cut)\n",
        encoding="utf-8",
    )


class TestGetCurrentStoryAnchorSessionFallback:
    def test_resolves_chapter_from_session_when_omitted(self, server_module, content_root: Path, isolated_session_db):
        _write_book_with_chapter(content_root, "test-book", "01-the-start")
        server_module.update_session(last_chapter="01-the-start")

        result = json.loads(server_module.get_current_story_anchor(book_slug="test-book"))

        assert "error" not in result
        assert result["current_chapter"]["chapter_slug"] == "01-the-start"

    def test_explicit_chapter_slug_overrides_session(self, server_module, content_root: Path, isolated_session_db):
        _write_book_with_chapter(content_root, "test-book", "01-the-start")
        _write_book_with_chapter(content_root, "test-book", "02-the-turn")
        server_module.update_session(last_chapter="01-the-start")

        result = json.loads(
            server_module.get_current_story_anchor(book_slug="test-book", chapter_slug="02-the-turn")
        )

        assert "error" not in result
        assert result["current_chapter"]["chapter_slug"] == "02-the-turn"

    def test_returns_documented_error_when_no_chapter_slug_and_no_session(
        self, server_module, content_root: Path, isolated_session_db
    ):
        _write_book_with_chapter(content_root, "test-book", "01-the-start")

        result = json.loads(server_module.get_current_story_anchor(book_slug="test-book"))

        assert "error" in result
        assert "last_chapter" in result["error"]

    def test_stale_session_pointer_from_different_book_resolves_no_chapter_not_error(
        self, server_module, content_root: Path, isolated_session_db
    ):
        # The session fallback resolves last_chapter within whatever book_slug
        # the caller passes explicitly — it does not cross-check last_book.
        # Document the existing (non-crashing) behavior: a chapter slug that
        # doesn't exist under the given book resolves to an anchor with no
        # current_chapter, not a hard error — callers must not assume a
        # populated last_chapter always means a valid chapter for this book.
        _write_book_with_chapter(content_root, "book-a", "01-a")
        _write_book_with_chapter(content_root, "book-b", "01-b")
        server_module.update_session(last_book="book-a", last_chapter="01-a")

        result = json.loads(server_module.get_current_story_anchor(book_slug="book-b"))

        assert "error" not in result
        assert result["current_chapter"] is None
