"""Tests for ``create_character_tracker`` MCP tool (Issue #237).

Verifies that the tool scaffolds a series character tracker from
parameters: correct frontmatter, h3-shape Evolution sections for all
bands in ``recurs_in`` plus one ``(geplant)`` section for the next
band, and an initial Updates Log entry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import routers._app as _app
from routers.series import create_character_tracker


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


def _make_series(content_root: Path, slug: str) -> Path:
    series_dir = content_root / "series" / slug
    (series_dir / "characters").mkdir(parents=True)
    (series_dir / "world").mkdir()
    readme = f"---\ntitle: {slug}\nslug: {slug}\n---\n\n# {slug}\n"
    (series_dir / "README.md").write_text(readme, encoding="utf-8")
    return series_dir


class TestCreateCharacterTrackerBasics:
    def test_creates_tracker_file(self, mock_config, content_root: Path):
        _make_series(content_root, "my-series")
        result = json.loads(
            create_character_tracker(
                series_slug="my-series",
                name="Kael Dawnfire",
                slug="kael",
                role="protagonist",
                recurs_in=["B1", "B2"],
            )
        )
        assert result.get("error") is None
        assert result["success"] is True
        tracker_path = content_root / "series" / "my-series" / "characters" / "kael.md"
        assert tracker_path.exists()
        assert result["path"] == str(tracker_path)

    def test_returns_slug_in_response(self, mock_config, content_root: Path):
        _make_series(content_root, "my-series")
        result = json.loads(
            create_character_tracker(
                series_slug="my-series",
                name="Kael",
                slug="kael",
                role="protagonist",
                recurs_in=["B1"],
            )
        )
        assert result["slug"] == "kael"

    def test_creates_characters_dir_when_missing(self, mock_config, content_root: Path):
        # Series exists but characters/ was removed after creation.
        series_dir = content_root / "series" / "my-series"
        series_dir.mkdir(parents=True)
        (series_dir / "README.md").write_text("---\nslug: my-series\n---\n", encoding="utf-8")
        # No characters/ dir.

        result = json.loads(
            create_character_tracker(
                series_slug="my-series",
                name="Viktor",
                slug="viktor",
                role="antagonist",
                recurs_in=["B1"],
            )
        )
        assert result.get("error") is None
        tracker_path = content_root / "series" / "my-series" / "characters" / "viktor.md"
        assert tracker_path.exists()


class TestCreateCharacterTrackerFrontmatter:
    def _parse_frontmatter(self, path: Path) -> dict:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        end = text.index("---\n", 4)
        return yaml.safe_load(text[4:end])

    def test_frontmatter_has_required_fields(self, mock_config, content_root: Path):
        _make_series(content_root, "my-series")
        create_character_tracker(
            series_slug="my-series",
            name="Kael Dawnfire",
            slug="kael",
            role="protagonist",
            recurs_in=["B1", "B2"],
            species="vampire",
        )
        tracker_path = content_root / "series" / "my-series" / "characters" / "kael.md"
        meta = self._parse_frontmatter(tracker_path)
        assert meta["name"] == "Kael Dawnfire"
        assert meta["slug"] == "kael"
        assert meta["role"] == "protagonist"
        assert meta["species"] == "vampire"
        assert meta["status"] == "Profile"
        assert meta["recurs_in"] == ["B1", "B2"]
        assert meta["tracker_type"] == "thin"

    def test_default_tracker_type_is_thin(self, mock_config, content_root: Path):
        _make_series(content_root, "my-series")
        create_character_tracker(
            series_slug="my-series",
            name="Minor",
            slug="minor",
            role="supporting",
            recurs_in=["B1"],
        )
        tracker_path = content_root / "series" / "my-series" / "characters" / "minor.md"
        meta = self._parse_frontmatter(tracker_path)
        assert meta["tracker_type"] == "thin"

    def test_full_tracker_type_written_when_set(self, mock_config, content_root: Path):
        _make_series(content_root, "my-series")
        create_character_tracker(
            series_slug="my-series",
            name="Central",
            slug="central",
            role="protagonist",
            recurs_in=["B1", "B2", "B3"],
            tracker_type="full",
        )
        tracker_path = content_root / "series" / "my-series" / "characters" / "central.md"
        meta = self._parse_frontmatter(tracker_path)
        assert meta["tracker_type"] == "full"

    def test_book_slug_written_when_different_from_slug(self, mock_config, content_root: Path):
        _make_series(content_root, "my-series")
        create_character_tracker(
            series_slug="my-series",
            name="King Caelan",
            slug="king-caelan",
            role="supporting",
            recurs_in=["B1", "B2", "B3"],
            book_slug="caelan",
        )
        tracker_path = content_root / "series" / "my-series" / "characters" / "king-caelan.md"
        meta = self._parse_frontmatter(tracker_path)
        assert meta["book_slug"] == "caelan"

    def test_book_slug_omitted_when_not_provided(self, mock_config, content_root: Path):
        _make_series(content_root, "my-series")
        create_character_tracker(
            series_slug="my-series",
            name="Kael",
            slug="kael",
            role="protagonist",
            recurs_in=["B1"],
        )
        tracker_path = content_root / "series" / "my-series" / "characters" / "kael.md"
        meta = self._parse_frontmatter(tracker_path)
        assert "book_slug" not in meta

    def test_empty_species_omitted_from_frontmatter(self, mock_config, content_root: Path):
        _make_series(content_root, "my-series")
        create_character_tracker(
            series_slug="my-series",
            name="Kael",
            slug="kael",
            role="protagonist",
            recurs_in=["B1"],
            species="",
        )
        tracker_path = content_root / "series" / "my-series" / "characters" / "kael.md"
        meta = self._parse_frontmatter(tracker_path)
        assert "species" not in meta


class TestCreateCharacterTrackerEvolutionSections:
    def test_single_band_generates_start_ende_and_planned_next(
        self, mock_config, content_root: Path
    ):
        _make_series(content_root, "my-series")
        create_character_tracker(
            series_slug="my-series",
            name="Kael",
            slug="kael",
            role="protagonist",
            recurs_in=["B1"],
        )
        text = (
            content_root / "series" / "my-series" / "characters" / "kael.md"
        ).read_text(encoding="utf-8")
        assert "### B1 Start" in text
        assert "### B1 Ende" in text
        assert "### B2" in text
        assert "geplant" in text.lower() or "(geplant)" in text

    def test_multiple_bands_generate_start_ende_for_each(
        self, mock_config, content_root: Path
    ):
        _make_series(content_root, "my-series")
        create_character_tracker(
            series_slug="my-series",
            name="Viktor",
            slug="viktor",
            role="antagonist",
            recurs_in=["B1", "B2", "B3"],
        )
        text = (
            content_root / "series" / "my-series" / "characters" / "viktor.md"
        ).read_text(encoding="utf-8")
        for band in ("B1", "B2", "B3"):
            assert f"### {band} Start" in text
            assert f"### {band} Ende" in text
        # B4 (geplant) for the next planned band.
        assert "### B4" in text

    def test_evolution_sections_parseable_by_loader(
        self, mock_config, content_root: Path
    ):
        from tools.state.loaders.series import parse_evolution_sections

        _make_series(content_root, "my-series")
        create_character_tracker(
            series_slug="my-series",
            name="Kael",
            slug="kael",
            role="protagonist",
            recurs_in=["B1", "B2"],
        )
        tracker_path = (
            content_root / "series" / "my-series" / "characters" / "kael.md"
        )
        sections = parse_evolution_sections(tracker_path)
        assert "B1" in sections
        assert "B2" in sections
        assert sections["B1"]["shape"] == "h3"
        assert sections["B2"]["shape"] == "h3"

    def test_ende_placeholder_not_parsed_as_existing_content(
        self, mock_config, content_root: Path
    ):
        """Issue #394: a freshly-scaffolded, never-harvested tracker's
        ``Ende``/``Start``/``(geplant)`` slots must parse as empty — the
        instructional placeholder prose (\"Filled by the harvest tool at
        end-of-book...\") is not real harvested content."""
        from tools.state.loaders.series import parse_evolution_sections

        _make_series(content_root, "my-series")
        create_character_tracker(
            series_slug="my-series",
            name="Kael",
            slug="kael",
            role="protagonist",
            recurs_in=["B1"],
        )
        tracker_path = (
            content_root / "series" / "my-series" / "characters" / "kael.md"
        )
        sections = parse_evolution_sections(tracker_path)
        assert sections["B1"]["start"] == ""
        assert sections["B1"]["ende"] == ""
        assert sections["B2"]["geplant"] == ""

    def test_all_placeholder_hint_variants_parse_as_empty(
        self, mock_config, content_root: Path
    ):
        """Issue #394: `_build_tracker_content()` emits two distinct hint
        phrasings — the i==0 band's ("Filled at planning time." /
        "Filled by the harvest tool...") and every subsequent band's
        ("Filled by the bootstrap tool from {prev} Ende." / "Filled by
        the harvest tool at end-of-book."). A two-band tracker exercises
        both variants plus the next-band geplant hint in one scaffold."""
        from tools.state.loaders.series import parse_evolution_sections

        _make_series(content_root, "my-series")
        create_character_tracker(
            series_slug="my-series",
            name="Kael",
            slug="kael",
            role="protagonist",
            recurs_in=["B1", "B2"],
        )
        tracker_path = (
            content_root / "series" / "my-series" / "characters" / "kael.md"
        )
        sections = parse_evolution_sections(tracker_path)
        assert sections["B1"]["start"] == ""
        assert sections["B1"]["ende"] == ""
        assert sections["B2"]["start"] == ""
        assert sections["B2"]["ende"] == ""
        assert sections["B3"]["geplant"] == ""


class TestCreateCharacterTrackerUpdatesLog:
    def test_updates_log_has_initial_entry(self, mock_config, content_root: Path):
        _make_series(content_root, "my-series")
        create_character_tracker(
            series_slug="my-series",
            name="Kael",
            slug="kael",
            role="protagonist",
            recurs_in=["B1"],
        )
        from tools.state.loaders.series import parse_updates_log

        tracker_path = (
            content_root / "series" / "my-series" / "characters" / "kael.md"
        )
        entries = parse_updates_log(tracker_path)
        assert len(entries) == 1
        assert "series-planner" in entries[0].lower() or "scaffolded" in entries[0].lower()


class TestCreateCharacterTrackerValidation:
    def test_error_when_series_not_found(self, mock_config, content_root: Path):
        result = json.loads(
            create_character_tracker(
                series_slug="ghost-series",
                name="Kael",
                slug="kael",
                role="protagonist",
                recurs_in=["B1"],
            )
        )
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_error_when_tracker_already_exists(self, mock_config, content_root: Path):
        _make_series(content_root, "my-series")
        create_character_tracker(
            series_slug="my-series",
            name="Kael",
            slug="kael",
            role="protagonist",
            recurs_in=["B1"],
        )
        result = json.loads(
            create_character_tracker(
                series_slug="my-series",
                name="Kael",
                slug="kael",
                role="protagonist",
                recurs_in=["B1"],
            )
        )
        assert "error" in result
        assert "already exists" in result["error"].lower()

    def test_error_on_invalid_band_in_recurs_in(self, mock_config, content_root: Path):
        _make_series(content_root, "my-series")
        result = json.loads(
            create_character_tracker(
                series_slug="my-series",
                name="Kael",
                slug="kael",
                role="protagonist",
                recurs_in=["Book1"],
            )
        )
        assert "error" in result
        assert "band" in result["error"].lower() or "recurs_in" in result["error"].lower()

    def test_error_on_duplicate_bands_in_recurs_in(self, mock_config, content_root: Path):
        _make_series(content_root, "my-series")
        result = json.loads(
            create_character_tracker(
                series_slug="my-series",
                name="Kael",
                slug="kael",
                role="protagonist",
                recurs_in=["B1", "B2", "B1"],
            )
        )
        assert "error" in result
        assert "duplicate" in result["error"].lower()

    def test_error_on_empty_recurs_in(self, mock_config, content_root: Path):
        _make_series(content_root, "my-series")
        result = json.loads(
            create_character_tracker(
                series_slug="my-series",
                name="Kael",
                slug="kael",
                role="protagonist",
                recurs_in=[],
            )
        )
        assert "error" in result
        assert "recurs_in" in result["error"].lower()

    def test_error_on_invalid_tracker_type(self, mock_config, content_root: Path):
        _make_series(content_root, "my-series")
        result = json.loads(
            create_character_tracker(
                series_slug="my-series",
                name="Kael",
                slug="kael",
                role="protagonist",
                recurs_in=["B1"],
                tracker_type="mega",
            )
        )
        assert "error" in result
        assert "tracker_type" in result["error"].lower()
