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


class TestAddBookToSeriesUniquenessGuard:
    """Issue #586: a duplicate series_number silently collides two books'
    book_rules/canon_facts/character_snapshots DB rows — the same failure
    mode #579 fixed for the series_number=0 scaffold case, but triggered by
    a plain typo instead. add_book_to_series() must reject a `number`
    already claimed by a DIFFERENT book in the series, without touching
    disk (neither README nor series.yaml) when it does."""

    def test_rejects_number_already_used_by_a_different_book(self, mock_config, content_root: Path):
        _make_series(
            content_root, "blood-and-binary", books=[{"slug": "embers", "number": 1, "status": "drafting"}]
        )
        _make_book(content_root, "firelight")

        result = json.loads(add_book_to_series("blood-and-binary", "firelight", 1))

        assert "error" in result
        assert "embers" in result["error"]
        assert "series_number 1" in result["error"]

    def test_rejected_call_does_not_write_series_yaml(self, mock_config, content_root: Path):
        _make_series(
            content_root, "blood-and-binary", books=[{"slug": "embers", "number": 1, "status": "drafting"}]
        )
        _make_book(content_root, "firelight")

        add_book_to_series("blood-and-binary", "firelight", 1)

        series_yaml = (content_root / "series" / "blood-and-binary" / "series.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(series_yaml)
        assert len(data["books"]) == 1
        assert data["books"][0]["slug"] == "embers"
        assert data["books"][0]["number"] == 1

    def test_relinking_onto_a_number_held_by_another_book_is_rejected(self, mock_config, content_root: Path):
        """The other conflict shape: the book is ALREADY in books[] (this
        is a re-link, not a first-time add), but the new number it's being
        moved to is held by a different book. Both the `!= book_slug`
        exclusion and the conflict check are simultaneously relevant here —
        the case most likely to silently break if the comprehension is
        reworked (Issue #586 code review, M-3)."""
        _make_series(
            content_root,
            "blood-and-binary",
            books=[
                {"slug": "embers", "number": 1, "status": "drafting"},
                {"slug": "firelight", "number": 2, "status": "drafting"},
            ],
        )
        _make_book(content_root, "firelight")

        result = json.loads(add_book_to_series("blood-and-binary", "firelight", 1))

        assert "error" in result
        assert "embers" in result["error"]

    def test_rejected_call_does_not_write_book_readme(self, mock_config, content_root: Path):
        _make_series(
            content_root, "blood-and-binary", books=[{"slug": "embers", "number": 1, "status": "drafting"}]
        )
        _make_book(content_root, "firelight")

        add_book_to_series("blood-and-binary", "firelight", 1)

        readme = (content_root / "projects" / "firelight" / "README.md").read_text(encoding="utf-8")
        assert "blood-and-binary" not in readme

    def test_relinking_the_same_book_to_a_new_number_is_allowed(self, mock_config, content_root: Path):
        """Not a collision — this is the normal correction path (e.g. fixing
        a wrong number for a book that's already linked)."""
        _make_series(
            content_root, "blood-and-binary", books=[{"slug": "firelight", "number": 1, "status": "drafting"}]
        )
        _make_book(content_root, "firelight")

        result = json.loads(add_book_to_series("blood-and-binary", "firelight", 2))

        assert result.get("success") is True
        series_yaml = (content_root / "series" / "blood-and-binary" / "series.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(series_yaml)
        assert data["books"][0]["number"] == 2

    def test_relinking_the_same_book_to_the_same_number_is_allowed(self, mock_config, content_root: Path):
        """Idempotent re-call (this tool is annotated idempotent_hint=True) —
        must not be treated as a conflict against itself."""
        _make_series(
            content_root, "blood-and-binary", books=[{"slug": "firelight", "number": 1, "status": "drafting"}]
        )
        _make_book(content_root, "firelight")

        result = json.loads(add_book_to_series("blood-and-binary", "firelight", 1, status="revision"))

        assert result.get("success") is True
        series_yaml = (content_root / "series" / "blood-and-binary" / "series.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(series_yaml)
        assert len(data["books"]) == 1
        assert data["books"][0]["status"] == "revision"

    def test_missing_series_yaml_is_rejected_not_silently_skipped(self, mock_config, content_root: Path):
        """Issue #586 code review, M-1: a series directory without
        series.yaml (create_series() always writes one, so this is an
        anomalous state — deleted, corrupted, or hand-created) has no known
        books to check against. Silently proceeding to write only the
        README (the pre-fix behavior) fails OPEN on exactly the collision
        this guard exists to prevent: a second add_book_to_series() call
        for a different book, made after series.yaml reappears empty or
        gets recreated, would see no conflict and collide anyway. Must
        reject instead, and must not touch the README on the way out."""
        series_dir = content_root / "series" / "blood-and-binary"
        series_dir.mkdir(parents=True)
        _make_book(content_root, "firelight")

        result = json.loads(add_book_to_series("blood-and-binary", "firelight", 1))

        assert "error" in result
        readme = (content_root / "projects" / "firelight" / "README.md").read_text(encoding="utf-8")
        assert "blood-and-binary" not in readme

    def test_quoted_number_in_series_yaml_still_detected_as_conflict(self, mock_config, content_root: Path):
        """Issue #586 code review, M-2: series.yaml is hand-editable — a
        quoted `number: "1"` round-trips as a str. A type-strict `==`
        comparison against the int argument would silently miss this as a
        conflict, and the later `sorted(..., key=...)` call would then
        crash on an int/str comparison mid-write, leaving the README
        updated but series.yaml not. Must still be caught."""
        _make_series(content_root, "blood-and-binary")
        series_yaml_path = content_root / "series" / "blood-and-binary" / "series.yaml"
        data = yaml.safe_load(series_yaml_path.read_text(encoding="utf-8"))
        data["books"] = [{"slug": "embers", "number": "1", "status": "drafting"}]
        series_yaml_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
        _make_book(content_root, "firelight")

        result = json.loads(add_book_to_series("blood-and-binary", "firelight", 1))

        assert "error" in result
        readme = (content_root / "projects" / "firelight" / "README.md").read_text(encoding="utf-8")
        assert "blood-and-binary" not in readme

    def test_number_passed_as_numeric_string_is_normalized(self, mock_config, content_root: Path):
        """Issue #586 code review, M-2: direct Python callers (tests,
        scripts/) bypass the MCP boundary's pydantic int validation. A
        string "1" must still conflict with an existing int 1, not be
        treated as a distinct value."""
        _make_series(
            content_root, "blood-and-binary", books=[{"slug": "embers", "number": 1, "status": "drafting"}]
        )
        _make_book(content_root, "firelight")

        result = json.loads(add_book_to_series("blood-and-binary", "firelight", "1"))

        assert "error" in result
        assert "embers" in result["error"]
