"""Tests for list_book_rules/lint_book_rules on an unlinked series book — Issue #579.

A book scaffolded into a series (series set) but never passed to
add_book_to_series() has series_number=0 in its README. get_book_num()
raises BookNotLinkedToSeriesError for that state (colliding with book 1's
DB rows otherwise) — both MCP tools must convert that into their standard
{"error": ...} contract instead of crashing to the MCP framework's generic
ToolError fallback.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.claudemd import init_book_claudemd, lint_book_rules, list_book_rules


@pytest.fixture
def mock_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    content_root = tmp_path / "books"
    cfg = {
        "paths": {"content_root": str(content_root)},
        "defaults": {"language": "en", "book_type": "novel"},
    }
    monkeypatch.setattr(_app, "load_config", lambda: cfg)
    _app._cache.invalidate()

    import tools.db.connection as _conn
    monkeypatch.setattr(_conn, "DB_DIR", tmp_path / "db")

    return cfg


@pytest.fixture
def unlinked_series_book(mock_config: dict) -> str:
    content_root = Path(mock_config["paths"]["content_root"])
    book_dir = content_root / "projects" / "unlinked-book"
    book_dir.mkdir(parents=True)
    (book_dir / "README.md").write_text(
        '---\ntitle: "Unlinked Book"\nseries: "my-series"\nseries_number: 0\n---\n',
        encoding="utf-8",
    )
    init_book_claudemd("unlinked-book", "Unlinked Book")
    return "unlinked-book"


def test_list_book_rules_returns_clear_error(unlinked_series_book: str):
    result = json.loads(list_book_rules(unlinked_series_book))
    assert "error" in result
    assert "my-series" in result["error"]


def test_lint_book_rules_returns_clear_error(unlinked_series_book: str):
    result = json.loads(lint_book_rules(unlinked_series_book))
    assert "error" in result
    assert "my-series" in result["error"]
