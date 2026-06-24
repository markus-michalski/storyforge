"""Tests for add_canon_fact() MCP tool — Issue #280."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.canon import add_canon_fact


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    root.mkdir()
    return root


@pytest.fixture
def db_dir(tmp_path: Path) -> Path:
    d = tmp_path / "db"
    d.mkdir()
    return d


@pytest.fixture
def mock_env(content_root: Path, db_dir: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    cfg = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(content_root / "authors"),
        },
        "defaults": {"language": "en"},
    }
    monkeypatch.setattr(_app, "load_config", lambda: cfg)
    monkeypatch.setattr("tools.db.connection.DB_DIR", db_dir)
    _app._cache.invalidate()
    return cfg


def _make_book(content_root: Path, book_slug: str, series: str = "") -> Path:
    book_dir = content_root / "projects" / book_slug
    book_dir.mkdir(parents=True)
    readme = (
        f"---\ntitle: Test\nslug: {book_slug}\nseries: \"{series}\"\n"
        "series_number: 1\n---\n\n# Test\n"
    )
    (book_dir / "README.md").write_text(readme, encoding="utf-8")
    return book_dir


class TestAddCanonFact:
    def test_basic_fact_insertion(self, mock_env, content_root: Path):
        _make_book(content_root, "firelight")
        result = json.loads(
            add_canon_fact(
                book_slug="firelight",
                chapter_num=5,
                subject="Lucien",
                fact="Has silver eyes",
            )
        )
        assert result.get("success") is True

    def test_missing_book_returns_error(self, mock_env, content_root: Path):
        result = json.loads(
            add_canon_fact(book_slug="nonexistent", chapter_num=1, subject="X", fact="Y")
        )
        assert "error" in result

    def test_returns_fact_metadata(self, mock_env, content_root: Path):
        _make_book(content_root, "firelight")
        result = json.loads(
            add_canon_fact(
                book_slug="firelight",
                chapter_num=5,
                subject="Lucien",
                fact="Has silver eyes",
            )
        )
        assert result["subject"] == "Lucien"
        assert result["fact"] == "Has silver eyes"
        assert result["chapter_num"] == 5

    def test_duplicate_fact_is_idempotent(self, mock_env, content_root: Path):
        _make_book(content_root, "firelight")
        add_canon_fact(book_slug="firelight", chapter_num=5, subject="X", fact="Y")
        result = json.loads(
            add_canon_fact(book_slug="firelight", chapter_num=5, subject="X", fact="Y")
        )
        assert "error" not in result

    def test_revision_fact_accepted(self, mock_env, content_root: Path):
        _make_book(content_root, "firelight")
        result = json.loads(
            add_canon_fact(
                book_slug="firelight",
                chapter_num=8,
                subject="Mine",
                fact="Is abandoned",
                is_revision=True,
                old_value="Is active",
            )
        )
        assert result.get("success") is True

    def test_series_book_uses_series_db(self, mock_env, content_root: Path, db_dir: Path):
        book_dir = content_root / "series" / "blood-and-binary" / "firelight"
        book_dir.mkdir(parents=True)
        readme = (
            "---\ntitle: Firelight\nslug: firelight\nseries: \"blood-and-binary\"\n"
            "series_number: 1\n---\n\n# Firelight\n"
        )
        (book_dir / "README.md").write_text(readme, encoding="utf-8")

        add_canon_fact(book_slug="firelight", chapter_num=1, subject="X", fact="Y")

        assert (db_dir / "blood-and-binary.db").exists()
        assert not (db_dir / "firelight.db").exists()
