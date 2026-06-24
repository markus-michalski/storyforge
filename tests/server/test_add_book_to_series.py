"""Tests for add_book_to_series() — Issue #279.

Verifies that the function writes to series.yaml books[] list
and does NOT create a books/ ref-file directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import routers._app as _app
from routers.series import add_book_to_series


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
        "defaults": {"language": "en", "book_type": "novel"},
    }
    monkeypatch.setattr(_app, "load_config", lambda: cfg)
    _app._cache.invalidate()
    return cfg


def _make_series(content_root: Path, series_slug: str, books: list | None = None) -> Path:
    series_dir = content_root / "series" / series_slug
    series_dir.mkdir(parents=True)
    series_data = {
        "name": series_slug,
        "slug": series_slug,
        "total_books": 3,
        "status": "Planning",
        "books": books or [],
    }
    (series_dir / "series.yaml").write_text(
        yaml.dump(series_data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    return series_dir


def _make_book(content_root: Path, book_slug: str, series_slug: str = "") -> Path:
    book_dir = content_root / "projects" / book_slug
    book_dir.mkdir(parents=True)
    readme = (
        f"---\ntitle: Test Book\nslug: {book_slug}\nseries: \"{series_slug}\"\n"
        "series_number: 0\n---\n\n# Test Book\n"
    )
    (book_dir / "README.md").write_text(readme, encoding="utf-8")
    return book_dir


class TestAddBookToSeriesYamlUpdate:
    def test_appends_book_to_series_yaml(self, mock_config, content_root: Path):
        _make_series(content_root, "blood-and-binary")
        _make_book(content_root, "firelight")

        result = json.loads(add_book_to_series("blood-and-binary", "firelight", 1))

        assert result.get("success") is True
        series_yaml = (content_root / "series" / "blood-and-binary" / "series.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(series_yaml)
        assert len(data["books"]) == 1
        assert data["books"][0]["slug"] == "firelight"
        assert data["books"][0]["number"] == 1
        assert data["books"][0]["status"] == "drafting"

    def test_does_not_create_books_subdir(self, mock_config, content_root: Path):
        _make_series(content_root, "blood-and-binary")
        _make_book(content_root, "firelight")

        add_book_to_series("blood-and-binary", "firelight", 1)

        assert not (content_root / "series" / "blood-and-binary" / "books").exists()

    def test_updates_book_readme_frontmatter(self, mock_config, content_root: Path):
        _make_series(content_root, "blood-and-binary")
        _make_book(content_root, "firelight")

        add_book_to_series("blood-and-binary", "firelight", 1)

        readme = (content_root / "projects" / "firelight" / "README.md").read_text(encoding="utf-8")
        assert "blood-and-binary" in readme

    def test_updating_existing_entry_does_not_duplicate(self, mock_config, content_root: Path):
        _make_series(content_root, "blood-and-binary", books=[{"slug": "firelight", "number": 1, "status": "drafting"}])
        _make_book(content_root, "firelight")

        add_book_to_series("blood-and-binary", "firelight", 1)

        series_yaml = (content_root / "series" / "blood-and-binary" / "series.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(series_yaml)
        firelight_entries = [b for b in data["books"] if b["slug"] == "firelight"]
        assert len(firelight_entries) == 1

    def test_custom_status_persisted(self, mock_config, content_root: Path):
        _make_series(content_root, "blood-and-binary")
        _make_book(content_root, "firelight")

        add_book_to_series("blood-and-binary", "firelight", 1, status="revision")

        series_yaml = (content_root / "series" / "blood-and-binary" / "series.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(series_yaml)
        assert data["books"][0]["status"] == "revision"

    def test_series_not_found_returns_error(self, mock_config, content_root: Path):
        _make_book(content_root, "firelight")
        result = json.loads(add_book_to_series("nonexistent", "firelight", 1))
        assert "error" in result

    def test_book_not_found_returns_error(self, mock_config, content_root: Path):
        _make_series(content_root, "blood-and-binary")
        result = json.loads(add_book_to_series("blood-and-binary", "nonexistent-book", 1))
        assert "error" in result

    def test_books_sorted_by_number(self, mock_config, content_root: Path):
        _make_series(content_root, "blood-and-binary", books=[{"slug": "embers", "number": 2, "status": "drafting"}])
        _make_book(content_root, "firelight")

        add_book_to_series("blood-and-binary", "firelight", 1)

        series_yaml = (content_root / "series" / "blood-and-binary" / "series.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(series_yaml)
        numbers = [b["number"] for b in data["books"]]
        assert numbers == sorted(numbers)
