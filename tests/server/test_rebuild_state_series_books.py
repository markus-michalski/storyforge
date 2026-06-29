"""Tests for rebuild_state() book discovery in series/ layout (Issue #279).

After the series-layout migration, books live at
series/{series_slug}/{book_slug}/ instead of projects/{book_slug}/.
The indexer must scan both locations — previously it only scanned projects/.
"""

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


def _make_series_book(content_root: Path, series_slug: str, book_slug: str, status: str = "Drafting") -> Path:
    """Create a minimal book directory inside series/{series_slug}/{book_slug}/."""
    book_dir = content_root / "series" / series_slug / book_slug
    book_dir.mkdir(parents=True)
    (book_dir / "README.md").write_text(
        f'---\ntitle: "Test Book"\nstatus: "{status}"\nauthor: test-author\n'
        f"series: {series_slug}\nseries_number: 1\ntarget_word_count: 90000\n---\n\n# Body\n",
        encoding="utf-8",
    )
    (book_dir / "chapters").mkdir()
    return book_dir


def _make_series_dir(content_root: Path, series_slug: str) -> Path:
    """Create minimal series-level metadata (README.md only)."""
    series_dir = content_root / "series" / series_slug
    series_dir.mkdir(parents=True, exist_ok=True)
    (series_dir / "README.md").write_text(
        f"---\nname: {series_slug}\nslug: {series_slug}\ntotal_books: 3\n---\n",
        encoding="utf-8",
    )
    return series_dir


class TestRebuildStateSeriesBooks:
    def test_list_books_finds_book_in_series_layout(self, server_module, content_root: Path):
        """rebuild_state must index books in series/{name}/{book}/, not only projects/."""
        _make_series_dir(content_root, "blood-and-binary")
        _make_series_book(content_root, "blood-and-binary", "firelight")

        server_module.rebuild_state()

        result = json.loads(server_module.list_books())
        assert result["count"] == 1
        assert result["books"][0]["slug"] == "firelight"

    def test_find_book_matches_book_in_series_layout(self, server_module, content_root: Path):
        """find_book() must return a match for a book living inside series/."""
        _make_series_dir(content_root, "blood-and-binary")
        _make_series_book(content_root, "blood-and-binary", "firelight")

        server_module.rebuild_state()

        result = json.loads(server_module.find_book("firelight"))
        assert result["count"] == 1
        assert result["matches"][0]["slug"] == "firelight"

    def test_standalone_books_in_projects_still_indexed(self, server_module, content_root: Path):
        """Books in projects/ must still be found alongside series books."""
        # standalone book in projects/
        project = content_root / "projects" / "standalone"
        project.mkdir(parents=True)
        (project / "README.md").write_text(
            '---\ntitle: "Standalone"\nstatus: "Idea"\nauthor: test-author\n'
            "target_word_count: 50000\n---\n\n# Body\n",
            encoding="utf-8",
        )
        (project / "chapters").mkdir()

        # book in series/
        _make_series_dir(content_root, "blood-and-binary")
        _make_series_book(content_root, "blood-and-binary", "firelight")

        server_module.rebuild_state()

        result = json.loads(server_module.list_books())
        slugs = {b["slug"] for b in result["books"]}
        assert result["count"] == 2
        assert "standalone" in slugs
        assert "firelight" in slugs

    def test_series_metadata_still_indexed(self, server_module, content_root: Path):
        """Series metadata must remain accessible alongside book discovery."""
        _make_series_dir(content_root, "blood-and-binary")
        _make_series_book(content_root, "blood-and-binary", "firelight")

        server_module.rebuild_state()

        # books found
        result = json.loads(server_module.list_books())
        assert result["count"] == 1

    def test_series_dir_without_book_subdir_does_not_crash(self, server_module, content_root: Path):
        """A series directory with only metadata (no book subdirs) must not fail."""
        _make_series_dir(content_root, "empty-series")

        server_module.rebuild_state()

        result = json.loads(server_module.list_books())
        assert result["count"] == 0

    def test_multiple_books_in_same_series(self, server_module, content_root: Path):
        """Multiple books within one series must all be indexed."""
        _make_series_dir(content_root, "blood-and-binary")
        _make_series_book(content_root, "blood-and-binary", "firelight", status="Drafting")
        _make_series_book(content_root, "blood-and-binary", "lycan", status="Idea")

        server_module.rebuild_state()

        result = json.loads(server_module.list_books())
        slugs = {b["slug"] for b in result["books"]}
        assert result["count"] == 2
        assert "firelight" in slugs
        assert "lycan" in slugs
