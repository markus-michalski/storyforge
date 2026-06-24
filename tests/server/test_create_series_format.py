"""Tests for updated create_series() — series.yaml format (Issue #279).

Verifies that create_series() writes a plain-YAML series.yaml file
instead of a README.md with frontmatter, and no longer creates a
books/ subdirectory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import routers._app as _app
from routers.series import create_series


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


class TestCreateSeriesYamlFormat:
    def test_creates_series_yaml_not_readme(self, mock_config, content_root: Path):
        result = json.loads(create_series(title="Blood & Binary", planned_books=3))

        assert result.get("success") is True
        series_dir = content_root / "series" / result["slug"]
        assert (series_dir / "series.yaml").exists(), "series.yaml must be created"
        assert not (series_dir / "README.md").exists(), "README.md must NOT be created"

    def test_series_yaml_is_valid_plain_yaml(self, mock_config, content_root: Path):
        result = json.loads(create_series(title="Blood & Binary", planned_books=3))
        series_dir = content_root / "series" / result["slug"]

        raw = (series_dir / "series.yaml").read_text(encoding="utf-8")
        parsed = yaml.safe_load(raw)

        assert isinstance(parsed, dict), "series.yaml must be a valid YAML mapping"
        assert "---" not in raw, "series.yaml must be plain YAML, not frontmatter"

    def test_series_yaml_contains_required_fields(self, mock_config, content_root: Path):
        result = json.loads(
            create_series(title="Blood & Binary", genres="lgbtq, dark-fantasy", planned_books=3)
        )
        series_dir = content_root / "series" / result["slug"]
        data = yaml.safe_load((series_dir / "series.yaml").read_text(encoding="utf-8"))

        assert data["name"] == "Blood & Binary"
        assert data["slug"] == result["slug"]
        assert data["total_books"] == 3
        assert "created" in data

    def test_no_books_subdirectory_created(self, mock_config, content_root: Path):
        result = json.loads(create_series(title="Blood & Binary", planned_books=3))
        series_dir = content_root / "series" / result["slug"]

        assert not (series_dir / "books").exists(), "books/ subdirectory must NOT be created"

    def test_world_and_characters_dirs_still_created(self, mock_config, content_root: Path):
        result = json.loads(create_series(title="Blood & Binary", planned_books=3))
        series_dir = content_root / "series" / result["slug"]

        assert (series_dir / "world").is_dir()
        assert (series_dir / "characters").is_dir()

    def test_duplicate_series_still_returns_error(self, mock_config, content_root: Path):
        create_series(title="Blood & Binary", planned_books=3)
        result2 = json.loads(create_series(title="Blood & Binary", planned_books=3))
        assert "error" in result2
