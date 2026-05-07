"""Tests for series-evolution brief helpers (Issue #205, D-3 of #195).

The chapter-writing brief enrichment needs two helpers:

- ``find_tracker_for_book_character`` — reverse lookup via #194's
  resolver. Given a book-level character slug, find the matching
  series-tracker file (tracker slug may differ — e.g. ``king-caelan``
  tracker maps to ``caelan`` book file).
- ``build_series_evolution_for_character`` — assembles the
  ``series_evolution`` payload that the brief surfaces to the
  chapter-writer per present character.

Graceful degrade: returns ``None`` when no series link exists, no
matching tracker exists, or section parsing yields nothing useful.
"""

from __future__ import annotations

from pathlib import Path

from tools.state.loaders.series import (
    build_series_evolution_for_character,
    find_tracker_for_book_character,
)


def _make_tracker(
    chars_dir: Path,
    slug: str,
    *,
    book_slug: str | None = None,
    name: str | None = None,
    role: str = "supporting",
    recurs_in: list[str] | None = None,
    body: str = "",
) -> Path:
    chars_dir.mkdir(parents=True, exist_ok=True)
    book_slug_line = f"book_slug: {book_slug}\n" if book_slug else ""
    fm = (
        "---\n"
        f"name: {name or slug}\n"
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


class TestFindTrackerForBookCharacter:
    def test_finds_tracker_with_matching_slug(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        _make_tracker(chars_dir, "kael")
        result = find_tracker_for_book_character(tmp_path, "kael")
        assert result is not None
        assert result.name == "kael.md"

    def test_finds_tracker_via_book_slug_field(self, tmp_path: Path) -> None:
        # Tracker slug ≠ book slug — the #194 case.
        chars_dir = tmp_path / "characters"
        _make_tracker(chars_dir, "king-caelan", book_slug="caelan")
        result = find_tracker_for_book_character(tmp_path, "caelan")
        assert result is not None
        assert result.name == "king-caelan.md"

    def test_returns_none_when_no_match(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        _make_tracker(chars_dir, "kael")
        assert find_tracker_for_book_character(tmp_path, "ghost") is None

    def test_returns_none_when_chars_dir_missing(self, tmp_path: Path) -> None:
        assert find_tracker_for_book_character(tmp_path, "kael") is None

    def test_first_match_wins_when_duplicates(self, tmp_path: Path) -> None:
        # Two trackers both resolving to "caelan" — defensively picks
        # the first (sorted) match. Authors should not produce this case
        # but the helper must not throw.
        chars_dir = tmp_path / "characters"
        _make_tracker(chars_dir, "king-caelan", book_slug="caelan")
        _make_tracker(chars_dir, "lord-caelan", book_slug="caelan")
        result = find_tracker_for_book_character(tmp_path, "caelan")
        assert result is not None
        assert result.name == "king-caelan.md"  # sorted alphabetically


class TestBuildSeriesEvolutionForCharacter:
    def test_full_payload_with_prev_and_current(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        _make_tracker(
            chars_dir,
            "kael",
            recurs_in=["B1", "B2", "B3"],
            body=(
                "## Evolution per Band\n\n"
                "### B1 Firelight\n"
                "- **Start:** Cabin-Einsiedler.\n"
                "- **Ende:** Mit Theo zusammen, Sera tot.\n\n"
                "### B2 Moonrise (geplant)\n"
                "- Trauernder Bruder.\n"
                "- Macht-Asymmetrie kippt.\n\n"
                "## Beziehungen ueber die Bande\n\n"
                "- **Theo:** Liebe -> Macht-Asymmetrie -> Gleichgewicht.\n"
                "- **Caelan:** Vater-Konflikt.\n"
            ),
        )
        payload = build_series_evolution_for_character(tmp_path, "kael", current_band="B2", prev_band="B1")
        assert payload is not None
        assert payload["tracker_slug"] == "kael"
        assert payload["current_book_phase"] == "B2 Moonrise (geplant)"
        assert "Mit Theo zusammen" in payload["previous_book_end"]
        assert "Trauernder Bruder" in payload["current_book_plan"]
        assert "**Theo:**" in payload["relationships_evolution"]

    def test_first_book_no_prev_band(self, tmp_path: Path) -> None:
        # B1 chapters have no previous_book_end — empty string.
        # current_book_plan priority is geplant > ende > start; for a
        # B1 tracker with both Start and Ende, the Ende (end-target)
        # is the more useful "where this is heading" payload.
        chars_dir = tmp_path / "characters"
        _make_tracker(
            chars_dir,
            "kael",
            recurs_in=["B1", "B2"],
            body=(
                "## Evolution per Band\n\n"
                "### B1 Firelight\n"
                "- **Start:** Cabin-Einsiedler.\n"
                "- **Ende:** Mit Theo zusammen.\n"
            ),
        )
        payload = build_series_evolution_for_character(tmp_path, "kael", current_band="B1", prev_band=None)
        assert payload is not None
        assert payload["previous_book_end"] == ""
        # Ende wins when no geplant — "Mit Theo zusammen" is the target
        # the chapter is heading toward.
        assert "Mit Theo zusammen" in payload["current_book_plan"]

    def test_first_book_falls_back_to_start_when_only_start(self, tmp_path: Path) -> None:
        # B1 with only Start (early drafting before any Ende drafted)
        # falls back to start text as last resort.
        chars_dir = tmp_path / "characters"
        _make_tracker(
            chars_dir,
            "kael",
            body=("## Evolution per Band\n\n### B1 Firelight\n- **Start:** Cabin-Einsiedler.\n"),
        )
        payload = build_series_evolution_for_character(tmp_path, "kael", current_band="B1", prev_band=None)
        assert payload is not None
        assert "Cabin-Einsiedler" in payload["current_book_plan"]

    def test_resolves_via_book_slug_field(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        _make_tracker(
            chars_dir,
            "king-caelan",
            book_slug="caelan",
            recurs_in=["B1", "B2"],
            body=("## Evolution per Band\n\n### B1\n- **Ende:** Sera trauert.\n\n### B2 (geplant)\n- B2 plan.\n"),
        )
        payload = build_series_evolution_for_character(tmp_path, "caelan", current_band="B2", prev_band="B1")
        assert payload is not None
        assert payload["tracker_slug"] == "king-caelan"
        assert "Sera trauert" in payload["previous_book_end"]

    def test_returns_none_when_no_tracker(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        _make_tracker(chars_dir, "kael")
        # Looking up a char that has no tracker.
        result = build_series_evolution_for_character(tmp_path, "ghost-char", current_band="B2", prev_band="B1")
        assert result is None

    def test_returns_none_when_chars_dir_missing(self, tmp_path: Path) -> None:
        result = build_series_evolution_for_character(tmp_path, "kael", current_band="B2", prev_band="B1")
        assert result is None

    def test_returns_none_when_band_has_no_data(self, tmp_path: Path) -> None:
        # Tracker exists but has no Evolution per Band content for
        # the requested band — graceful degrade.
        chars_dir = tmp_path / "characters"
        _make_tracker(chars_dir, "kael", body="## Snapshot\n\nEssence text.\n")
        result = build_series_evolution_for_character(tmp_path, "kael", current_band="B2", prev_band="B1")
        assert result is None

    def test_relationships_empty_when_section_missing(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        _make_tracker(
            chars_dir,
            "kael",
            body=("## Evolution per Band\n\n### B1\n- **Ende:** End.\n"),
        )
        payload = build_series_evolution_for_character(tmp_path, "kael", current_band="B1", prev_band=None)
        assert payload is not None
        assert payload["relationships_evolution"] == ""

    def test_falls_back_to_ende_when_geplant_empty(self, tmp_path: Path) -> None:
        # Edge: current band has Ende but no geplant. current_book_plan
        # falls back to whatever's there — the tracker's narrative text
        # for this band, in priority order: geplant > ende > start.
        chars_dir = tmp_path / "characters"
        _make_tracker(
            chars_dir,
            "kael",
            body=("## Evolution per Band\n\n### B2\n- **Ende:** B2 end state.\n"),
        )
        payload = build_series_evolution_for_character(tmp_path, "kael", current_band="B2", prev_band=None)
        assert payload is not None
        assert "B2 end state" in payload["current_book_plan"]
