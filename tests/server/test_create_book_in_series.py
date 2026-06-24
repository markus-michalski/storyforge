"""Tests for create_book_structure(series_slug=...) — Issue #279.

Verifies that create_book_structure() scaffolds the book under
series/{series_slug}/{book_slug}/ when series_slug is provided,
and falls back to projects/ for standalone books.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.creation import create_book_structure


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    root.mkdir()
    return root


@pytest.fixture
def mock_config(content_root: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    cfg = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(content_root / "authors"),
        },
        "defaults": {"language": "en", "book_type": "novel", "book_category": "fiction"},
    }
    monkeypatch.setattr(_app, "load_config", lambda: cfg)
    _app._cache.invalidate()
    return cfg


def _make_series_dir(content_root: Path, series_slug: str) -> Path:
    """Create a minimal series directory (series.yaml + world/ + characters/)."""
    series_dir = content_root / "series" / series_slug
    (series_dir / "world").mkdir(parents=True)
    (series_dir / "characters").mkdir()
    (series_dir / "series.yaml").write_text(
        f"name: {series_slug}\nslug: {series_slug}\ntotal_books: 3\n",
        encoding="utf-8",
    )
    return series_dir


class TestCreateBookInSeries:
    def test_scaffolds_under_series_dir(self, mock_config, content_root: Path):
        _make_series_dir(content_root, "blood-and-binary")
        result = json.loads(
            create_book_structure(
                title="Firelight",
                series_slug="blood-and-binary",
            )
        )

        assert result.get("success") is True
        expected = content_root / "series" / "blood-and-binary" / "firelight"
        assert expected.is_dir(), f"Expected book dir at {expected}"

    def test_not_created_under_projects_when_series_slug_given(self, mock_config, content_root: Path):
        _make_series_dir(content_root, "blood-and-binary")
        create_book_structure(title="Firelight", series_slug="blood-and-binary")

        assert not (content_root / "projects" / "firelight").exists()

    def test_standalone_book_still_goes_to_projects(self, mock_config, content_root: Path):
        result = json.loads(create_book_structure(title="Standalone Novel"))

        assert result.get("success") is True
        assert (content_root / "projects" / "standalone-novel").is_dir()

    def test_series_book_has_full_scaffold(self, mock_config, content_root: Path):
        _make_series_dir(content_root, "blood-and-binary")
        create_book_structure(title="Firelight", series_slug="blood-and-binary")

        book_dir = content_root / "series" / "blood-and-binary" / "firelight"
        assert (book_dir / "README.md").exists()
        assert (book_dir / "plot").is_dir()
        assert (book_dir / "chapters").is_dir()
        assert (book_dir / "characters").is_dir()

    def test_series_book_readme_contains_series_slug(self, mock_config, content_root: Path):
        _make_series_dir(content_root, "blood-and-binary")
        create_book_structure(title="Firelight", series_slug="blood-and-binary")

        readme = (
            content_root / "series" / "blood-and-binary" / "firelight" / "README.md"
        ).read_text(encoding="utf-8")
        assert "blood-and-binary" in readme

    def test_invalid_series_slug_returns_error(self, mock_config, content_root: Path):
        result = json.loads(
            create_book_structure(title="Firelight", series_slug="nonexistent-series")
        )
        assert "error" in result

    def test_duplicate_book_in_series_returns_error(self, mock_config, content_root: Path):
        _make_series_dir(content_root, "blood-and-binary")
        create_book_structure(title="Firelight", series_slug="blood-and-binary")
        result2 = json.loads(
            create_book_structure(title="Firelight", series_slug="blood-and-binary")
        )
        assert "error" in result2

    def test_series_slug_security_validation(self, mock_config, content_root: Path):
        result = json.loads(
            create_book_structure(title="Firelight", series_slug="../escape")
        )
        assert "error" in result
