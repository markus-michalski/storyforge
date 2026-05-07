"""Tests for ``read_tracker_for_bootstrap`` MCP tool (Issue #203, D-2 of #195).

The bootstrap skill calls this once per recurring tracker to get the
data it needs for snapshot synthesis: the previous book's Ende narrative
(what D-1 wrote), the new book's planned narrative, the prev book
character file's existing snapshot for comparison, and identity fields.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.series import read_tracker_for_bootstrap


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
    book_slug: str | None = None,
    role: str = "supporting",
    recurs_in: list[str] | None = None,
    body: str = "",
) -> Path:
    chars_dir = content_root / "series" / series / "characters"
    chars_dir.mkdir(parents=True, exist_ok=True)
    book_slug_line = f"book_slug: {book_slug}\n" if book_slug else ""
    fm = (
        "---\n"
        f"name: {slug.title()}\n"
        f"slug: {slug}\n"
        f"{book_slug_line}"
        f"role: {role}\n"
        "status: Profile\n"
        f"recurs_in: {recurs_in or ['B1', 'B2']}\n"
        "tracker_type: thin\n"
        "---\n\n"
    )
    path = chars_dir / f"{slug}.md"
    path.write_text(fm + body, encoding="utf-8")
    return path


def _make_book_char(
    content_root: Path,
    book: str,
    slug: str,
    *,
    snapshot: dict | None = None,
    body: str = "Profile",
    layout: str = "characters",
) -> Path:
    char_dir = content_root / "projects" / book / layout
    char_dir.mkdir(parents=True, exist_ok=True)
    snap_lines = ""
    if snapshot:
        for k, v in snapshot.items():
            snap_lines += f"{k}: {v}\n" if isinstance(v, list) else f"{k}: {v!r}\n"
    char_file = char_dir / f"{slug}.md"
    char_file.write_text(
        f"---\nname: {slug}\nrole: protagonist\n{snap_lines}---\n\n{body}\n",
        encoding="utf-8",
    )
    return char_file


class TestReadTrackerForBootstrap:
    def test_returns_prev_ende_and_new_geplant(self, mock_config, content_root: Path):
        _make_tracker(
            content_root,
            "blood-and-binary",
            "kael",
            recurs_in=["B1", "B2", "B3"],
            body=(
                "## Evolution per Band\n\n"
                "### B1 Firelight\n"
                "- **Start:** Cabin-Einsiedler.\n"
                "- **Ende:** Mit Theo zusammen, Sera tot, zurueck am Hof.\n\n"
                "### B2 Moonrise (geplant)\n"
                "- Trauernder Bruder.\n"
                "- Macht-Asymmetrie kippt.\n"
            ),
        )

        result = json.loads(read_tracker_for_bootstrap("blood-and-binary", "kael", prev_band="B1", new_band="B2"))
        assert result.get("error") is None
        assert result["tracker_slug"] == "kael"
        assert result["book_slug"] == "kael"
        assert "Mit Theo zusammen" in result["prev_band"]["ende"]
        assert "Trauernder Bruder" in result["new_band"]["geplant"]
        # Empty slots are still present in the response — not stripped.
        assert "start" in result["prev_band"]
        assert "ende" in result["new_band"]

    def test_resolves_book_slug_via_194(self, mock_config, content_root: Path):
        _make_tracker(
            content_root,
            "blood-and-binary",
            "king-caelan",
            book_slug="caelan",
            recurs_in=["B1", "B2", "B3"],
            body=("## Evolution per Band\n\n### B1 Firelight\n- **Ende:** Sera trauert.\n"),
        )
        result = json.loads(read_tracker_for_bootstrap("blood-and-binary", "king-caelan", "B1", "B2"))
        assert result["tracker_slug"] == "king-caelan"
        assert result["book_slug"] == "caelan"

    def test_returns_prev_book_snapshot_when_provided(self, mock_config, content_root: Path):
        # When prev_book_slug is provided, also project the prev book's
        # existing snapshot frontmatter — useful for diff display.
        _make_tracker(
            content_root,
            "my-series",
            "kael",
            recurs_in=["B1", "B2"],
            body=("## Evolution per Band\n\n### B1\n- **Ende:** End state.\n"),
        )
        _make_book_char(
            content_root,
            "firelight",
            "kael",
            snapshot={
                "current_inventory": ["silver knife"],
                "current_clothing": ["leather coat"],
                "current_injuries": [],
                "altered_states": [],
                "environmental_limiters": [],
                "as_of_chapter": "30-final",
            },
        )
        result = json.loads(
            read_tracker_for_bootstrap(
                "my-series",
                "kael",
                "B1",
                "B2",
                prev_book_slug="firelight",
            )
        )
        assert result["prev_book_snapshot"]["current_inventory"] == ["silver knife"]
        assert result["prev_book_snapshot"]["as_of_chapter"] == "30-final"

    def test_prev_book_snapshot_omitted_when_no_prev_book(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "kael", recurs_in=["B1", "B2"])
        result = json.loads(read_tracker_for_bootstrap("my-series", "kael", "B1", "B2"))
        # Without prev_book_slug, the field is absent OR explicitly None.
        assert result.get("prev_book_snapshot") in (None, {})

    def test_prev_book_snapshot_handles_missing_char_file(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "tristan", recurs_in=["B2", "B3"])
        # prev_book_slug provided but no char file there (Tristan first
        # appears in B2). Tool returns None / empty — not error.
        result = json.loads(
            read_tracker_for_bootstrap(
                "my-series",
                "tristan",
                "B1",
                "B2",
                prev_book_slug="firelight",
            )
        )
        assert result.get("prev_book_snapshot") in (None, {})

    def test_includes_identity_fields(self, mock_config, content_root: Path):
        _make_tracker(
            content_root,
            "my-series",
            "kael",
            role="love-interest",
            recurs_in=["B1", "B2"],
        )
        result = json.loads(read_tracker_for_bootstrap("my-series", "kael", "B1", "B2"))
        assert result["name"] == "Kael"
        assert result["role"] == "love-interest"

    def test_invalid_band_returns_error(self, mock_config, content_root: Path):
        result = json.loads(read_tracker_for_bootstrap("my-series", "kael", "Book1", "B2"))
        assert "band" in result["error"].lower()

    def test_series_not_found(self, mock_config, content_root: Path):
        result = json.loads(read_tracker_for_bootstrap("ghost-series", "kael", "B1", "B2"))
        assert "not found" in result["error"].lower()

    def test_tracker_not_found(self, mock_config, content_root: Path):
        (content_root / "series" / "my-series" / "characters").mkdir(parents=True)
        result = json.loads(read_tracker_for_bootstrap("my-series", "ghost-char", "B1", "B2"))
        assert "not found" in result["error"].lower()

    def test_handles_missing_evolution_section_gracefully(self, mock_config, content_root: Path):
        # Tracker without Evolution per Band yet — empty bands, no error.
        _make_tracker(
            content_root,
            "my-series",
            "kael",
            recurs_in=["B1", "B2"],
            body="## Snapshot\n\nEssence.\n",
        )
        result = json.loads(read_tracker_for_bootstrap("my-series", "kael", "B1", "B2"))
        assert result["prev_band"]["ende"] == ""
        assert result["new_band"]["geplant"] == ""
