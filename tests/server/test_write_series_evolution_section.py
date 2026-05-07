"""Tests for ``write_series_evolution_section`` and
``list_series_trackers_for_book`` MCP tools (Issue #200, D-1 of #195).

These tools are the harvest skill's write side: they update the right
band's slot in a series-tracker, append a dated entry to the tracker's
Updates Log, and surface which trackers belong to the current book band.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.series import (
    list_series_trackers_for_book,
    write_series_evolution_section,
)


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


def _make_tracker(
    content_root: Path,
    series: str,
    slug: str,
    *,
    name: str | None = None,
    role: str = "supporting",
    recurs_in: list[str] | None = None,
    book_slug: str | None = None,
    body: str = "",
) -> Path:
    chars_dir = content_root / "series" / series / "characters"
    chars_dir.mkdir(parents=True, exist_ok=True)
    book_slug_line = f"book_slug: {book_slug}\n" if book_slug else ""
    recurs = recurs_in or ["B1"]
    fm = (
        "---\n"
        f"name: {name or slug}\n"
        f"slug: {slug}\n"
        f"{book_slug_line}"
        f"role: {role}\n"
        "status: Profile\n"
        f"recurs_in: {recurs}\n"
        "tracker_type: thin\n"
        "---\n\n"
    )
    path = chars_dir / f"{slug}.md"
    path.write_text(fm + body, encoding="utf-8")
    return path


class TestWriteSeriesEvolutionSection:
    def test_writes_ende_to_existing_band(self, mock_config, content_root: Path):
        tracker = _make_tracker(
            content_root,
            "blood-and-binary",
            "kael",
            recurs_in=["B1", "B2"],
            body=(
                "## Evolution per Band\n\n"
                "### B1 Firelight\n"
                "- **Start:** Cabin-Einsiedler.\n"
                "- **Ende:** old end.\n\n"
                "### B2 Moonrise (geplant)\n"
                "- Trauernder Bruder.\n\n"
                "## Updates Log\n\n"
                "(noch keine Eintraege)\n"
            ),
        )

        result = json.loads(
            write_series_evolution_section(
                "blood-and-binary",
                "kael",
                "B1",
                "ende",
                "Mit Theo zusammen, Sera tot.",
                "Harvested from B1 final state",
                date="2026-05-08",
            )
        )
        assert result.get("error") is None
        assert result["success"] is True

        text = tracker.read_text(encoding="utf-8")
        assert "- **Ende:** Mit Theo zusammen, Sera tot." in text
        assert "old end." not in text
        # Updates log got the dated entry; placeholder removed.
        assert "- 2026-05-08 — Harvested from B1 final state" in text
        assert "(noch keine Eintraege)" not in text
        # B2 untouched.
        assert "### B2 Moonrise (geplant)" in text
        assert "- Trauernder Bruder." in text

    def test_creates_band_when_missing(self, mock_config, content_root: Path):
        tracker = _make_tracker(
            content_root,
            "my-series",
            "viktor",
            recurs_in=["B1", "B2"],
            body="## Evolution per Band\n\n### B1 Firelight\n- **Start:** S.\n- **Ende:** E.\n",
        )
        result = json.loads(
            write_series_evolution_section(
                "my-series",
                "viktor",
                "B2",
                "ende",
                "B2 final state.",
                "Harvested from B2 final state",
                date="2026-05-09",
            )
        )
        assert result["success"] is True
        text = tracker.read_text(encoding="utf-8")
        assert "### B2" in text
        assert "B2 final state." in text

    def test_rejects_invalid_kind(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "kael")
        result = json.loads(
            write_series_evolution_section(
                "my-series",
                "kael",
                "B1",
                "bogus-kind",
                "ignored",
                "ignored",
            )
        )
        assert result.get("success") is None
        assert "kind" in result["error"].lower()

    def test_rejects_invalid_band(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "kael")
        result = json.loads(
            write_series_evolution_section(
                "my-series",
                "kael",
                "Book1",  # not B<N>
                "ende",
                "ignored",
                "ignored",
            )
        )
        assert "band" in result["error"].lower()

    def test_series_not_found(self, mock_config, content_root: Path):
        result = json.loads(
            write_series_evolution_section(
                "ghost-series",
                "kael",
                "B1",
                "ende",
                "...",
                "Harvested",
            )
        )
        assert "not found" in result["error"].lower()

    def test_tracker_not_found(self, mock_config, content_root: Path):
        # Series exists but the tracker file does not.
        (content_root / "series" / "my-series" / "characters").mkdir(parents=True)
        result = json.loads(
            write_series_evolution_section(
                "my-series",
                "ghost-char",
                "B1",
                "ende",
                "...",
                "Harvested",
            )
        )
        assert "not found" in result["error"].lower()


class TestListSeriesTrackersForBook:
    def test_returns_only_trackers_recurring_in_band(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "kael", recurs_in=["B1", "B2", "B3"])
        _make_tracker(content_root, "my-series", "viktor", recurs_in=["B1", "B2"])
        # Tracker that doesn't recur in B1 — must be excluded.
        _make_tracker(content_root, "my-series", "newcomer", recurs_in=["B2", "B3"])

        result = json.loads(list_series_trackers_for_book("my-series", "B1"))
        slugs = sorted(t["tracker_slug"] for t in result["trackers"])
        assert slugs == ["kael", "viktor"]

    def test_resolves_book_slug_via_resolver(self, mock_config, content_root: Path):
        _make_tracker(
            content_root,
            "blood-and-binary",
            "king-caelan",
            book_slug="caelan",
            recurs_in=["B1", "B2", "B3"],
        )
        result = json.loads(list_series_trackers_for_book("blood-and-binary", "B1"))
        entry = result["trackers"][0]
        assert entry["tracker_slug"] == "king-caelan"
        assert entry["book_slug"] == "caelan"

    def test_falls_back_to_tracker_slug_when_book_slug_absent(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "kael", recurs_in=["B1"])
        result = json.loads(list_series_trackers_for_book("my-series", "B1"))
        entry = result["trackers"][0]
        assert entry["tracker_slug"] == "kael"
        assert entry["book_slug"] == "kael"

    def test_surfaces_existing_ende_for_diff(self, mock_config, content_root: Path):
        _make_tracker(
            content_root,
            "my-series",
            "kael",
            recurs_in=["B1"],
            body=("## Evolution per Band\n\n### B1 Firelight\n- **Start:** S.\n- **Ende:** Existing end content.\n"),
        )
        result = json.loads(list_series_trackers_for_book("my-series", "B1"))
        entry = result["trackers"][0]
        assert entry["has_existing_ende"] is True
        assert "Existing end content" in entry["existing_ende"]

    def test_marks_missing_ende(self, mock_config, content_root: Path):
        _make_tracker(
            content_root,
            "my-series",
            "kael",
            recurs_in=["B1"],
            body="## Evolution per Band\n\n### B1 Firelight\n- **Start:** Just start.\n",
        )
        result = json.loads(list_series_trackers_for_book("my-series", "B1"))
        entry = result["trackers"][0]
        assert entry["has_existing_ende"] is False
        assert entry["existing_ende"] == ""

    def test_rejects_invalid_band(self, mock_config, content_root: Path):
        result = json.loads(list_series_trackers_for_book("my-series", "Book1"))
        assert "band" in result["error"].lower()

    def test_series_not_found(self, mock_config, content_root: Path):
        result = json.loads(list_series_trackers_for_book("ghost-series", "B1"))
        assert "not found" in result["error"].lower()

    def test_returns_empty_list_when_no_trackers(self, mock_config, content_root: Path):
        # Series exists but no characters dir / no .md files.
        (content_root / "series" / "my-series").mkdir(parents=True)
        result = json.loads(list_series_trackers_for_book("my-series", "B1"))
        assert result["trackers"] == []
