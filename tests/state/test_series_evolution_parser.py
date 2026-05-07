"""Tests for series-tracker evolution-section parsers (Issue #200, D-1 of #195).

Covers parsing of:
- ``## Evolution per Band`` sections (both bullet-shape and h3-shape)
- ``## Beziehungen ueber die Bande`` (or ``## Beziehungen über die Bände``)
  raw text
- ``## Updates Log`` bulleted entries

The parser is tolerant of both shapes the tracker schema has produced in
the wild:
- **bullet shape:** ``### B1 Firelight`` heading with ``- **Start:**``,
  ``- **Ende:**``, ``- **Plan:**`` keyed bullets in the body. Body may
  also contain freeform bullets (e.g. ``**Ch 21 Szene 2:**``) that are
  preserved as raw text but don't map to a keyed slot.
- **h3 shape:** separate ``### B1 Start`` / ``### B1 Ende`` /
  ``### B1 (geplant)`` H3 headings, body is whatever follows until the
  next H2/H3.
"""

from __future__ import annotations

from pathlib import Path

from tools.state.loaders.series import (
    parse_evolution_sections,
    parse_relationships_section,
    parse_updates_log,
)


def _write_tracker(path: Path, body: str) -> Path:
    path.write_text(
        "---\n"
        "name: Test Char\n"
        "slug: test-char\n"
        "role: supporting\n"
        "status: Profile\n"
        "recurs_in: [B1, B2]\n"
        "tracker_type: thin\n"
        "---\n\n" + body,
        encoding="utf-8",
    )
    return path


class TestParseEvolutionSectionsBulletShape:
    def test_parses_keyed_bullets(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Evolution per Band\n\n"
            "### B1 Firelight\n"
            "- **Start:** Cabin-Einsiedler.\n"
            "- **Ende:** Mit Theo zusammen.\n\n"
            "### B2 Moonrise (geplant)\n"
            "- Trauernder Bruder.\n"
            "- Macht-Asymmetrie kippt.\n",
        )
        sections = parse_evolution_sections(path)
        assert "B1" in sections and "B2" in sections
        assert sections["B1"]["title"] == "B1 Firelight"
        assert sections["B1"]["shape"] == "bullet"
        assert sections["B1"]["start"] == "Cabin-Einsiedler."
        assert sections["B1"]["ende"] == "Mit Theo zusammen."
        assert sections["B1"]["geplant"] == ""

    def test_recognizes_geplant_in_heading_suffix(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Evolution per Band\n\n### B2 Moonrise (geplant)\n- Trauernder Bruder.\n- Macht-Asymmetrie kippt.\n",
        )
        sections = parse_evolution_sections(path)
        assert sections["B2"]["title"] == "B2 Moonrise (geplant)"
        # When heading marks the band as planned, body becomes the geplant
        # value (joined bullets) — Start/Ende stay empty.
        assert sections["B2"]["start"] == ""
        assert sections["B2"]["ende"] == ""
        assert "Trauernder Bruder" in sections["B2"]["geplant"]
        assert "Macht-Asymmetrie kippt" in sections["B2"]["geplant"]

    def test_preserves_raw_body_for_diff(self, tmp_path: Path) -> None:
        body = (
            "## Evolution per Band\n\n"
            "### B1 Firelight\n"
            "- **Start:** Off-page-Praesenz.\n"
            "- **Ch 21:** Caelan findet Theo.\n"
            "- **Ende:** Sera stirbt trotz allem.\n"
        )
        path = _write_tracker(tmp_path / "caelan.md", body)
        sections = parse_evolution_sections(path)
        # raw_body lets the harvest tool show full context to the user
        # for diff prompts, even when freeform bullets sit between
        # Start and Ende.
        raw = sections["B1"]["raw_body"]
        assert "Off-page-Praesenz" in raw
        assert "Ch 21" in raw
        assert "Sera stirbt trotz allem" in raw

    def test_handles_lowercase_keys(self, tmp_path: Path) -> None:
        # Tolerance: some authors write **start:** / **ende:** lowercase.
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Evolution per Band\n\n### B1 Firelight\n- **start:** lower.\n- **ende:** lower end.\n",
        )
        sections = parse_evolution_sections(path)
        assert sections["B1"]["start"] == "lower."
        assert sections["B1"]["ende"] == "lower end."

    def test_handles_multiline_keyed_bullet(self, tmp_path: Path) -> None:
        # A keyed bullet can span continuation lines (indented or
        # blank-line-terminated). Parser collects the whole value.
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Evolution per Band\n\n"
            "### B1 Firelight\n"
            "- **Start:** First line of start.\n"
            "  Continuation indented.\n"
            "- **Ende:** End line.\n",
        )
        sections = parse_evolution_sections(path)
        assert "First line of start" in sections["B1"]["start"]
        assert "Continuation indented" in sections["B1"]["start"]
        assert sections["B1"]["ende"] == "End line."


class TestParseEvolutionSectionsH3Shape:
    def test_parses_separate_h3_headings(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "viktor.md",
            "## Evolution per Band\n\n"
            "### B1 Start\n"
            "Erbe per Wahl.\n\n"
            "### B1 Ende\n"
            "Vertrauenslinie cementiert.\n\n"
            "### B2 (geplant)\n"
            "Politische Heirat steht an.\n",
        )
        sections = parse_evolution_sections(path)
        assert sections["B1"]["shape"] == "h3"
        assert sections["B1"]["start"] == "Erbe per Wahl."
        assert sections["B1"]["ende"] == "Vertrauenslinie cementiert."
        assert sections["B2"]["geplant"] == "Politische Heirat steht an."

    def test_h3_section_supports_multi_paragraph_body(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "viktor.md",
            "## Evolution per Band\n\n### B1 Ende\nFirst paragraph.\n\nSecond paragraph.\n",
        )
        sections = parse_evolution_sections(path)
        assert "First paragraph" in sections["B1"]["ende"]
        assert "Second paragraph" in sections["B1"]["ende"]


class TestParseEvolutionSectionsEdgeCases:
    def test_returns_empty_dict_when_section_missing(self, tmp_path: Path) -> None:
        path = _write_tracker(tmp_path / "kael.md", "## Snapshot\n\nNo evolution section.\n")
        assert parse_evolution_sections(path) == {}

    def test_returns_empty_dict_when_section_has_no_bands(self, tmp_path: Path) -> None:
        path = _write_tracker(tmp_path / "kael.md", "## Evolution per Band\n\nNo H3 yet.\n")
        assert parse_evolution_sections(path) == {}

    def test_ignores_non_band_h3_inside_section(self, tmp_path: Path) -> None:
        # An H3 that doesn't match B<N> pattern is not an evolution band.
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Evolution per Band\n\n### Notes\nSome prose.\n\n### B1 Firelight\n- **Ende:** End.\n",
        )
        sections = parse_evolution_sections(path)
        assert "B1" in sections
        assert "Notes" not in sections


class TestParseRelationshipsSection:
    def test_returns_text_under_beziehungen(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Beziehungen ueber die Bande\n\n"
            "- **Theo:** Liebe -> Macht-Asymmetrie -> Gleichgewicht.\n"
            "- **Caelan:** Vater-Konflikt -> Mit-Trauernder.\n\n"
            "## Updates Log\n",
        )
        text = parse_relationships_section(path)
        assert "**Theo:**" in text
        assert "Vater-Konflikt" in text
        assert "Updates Log" not in text

    def test_supports_umlaut_heading(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Beziehungen über die Bände\n\n- **Theo:** Etwas.\n",
        )
        text = parse_relationships_section(path)
        assert "**Theo:**" in text

    def test_supports_relationships_heading(self, tmp_path: Path) -> None:
        # English fallback heading.
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Relationships\n\n- **Theo:** Lover.\n",
        )
        text = parse_relationships_section(path)
        assert "**Theo:**" in text

    def test_returns_empty_string_when_section_missing(self, tmp_path: Path) -> None:
        path = _write_tracker(tmp_path / "kael.md", "## Snapshot\n\nNothing else.\n")
        assert parse_relationships_section(path) == ""


class TestParseUpdatesLog:
    def test_returns_bulleted_entries(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Updates Log\n\n- 2026-05-07 — Tracker scaffolded\n- 2026-05-08 — Harvested from B1 final state\n",
        )
        entries = parse_updates_log(path)
        assert entries == [
            "2026-05-07 — Tracker scaffolded",
            "2026-05-08 — Harvested from B1 final state",
        ]

    def test_returns_empty_list_when_section_missing(self, tmp_path: Path) -> None:
        path = _write_tracker(tmp_path / "kael.md", "## Snapshot\n\nNothing.\n")
        assert parse_updates_log(path) == []

    def test_returns_empty_list_when_section_only_has_placeholder(self, tmp_path: Path) -> None:
        # Authors sometimes write "(noch keine Eintraege)" as a placeholder.
        # Parser ignores non-bullet lines.
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Updates Log\n\n(noch keine Eintraege)\n",
        )
        assert parse_updates_log(path) == []

    def test_strips_leading_dash_and_whitespace(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Updates Log\n\n-   2026-05-07 — Spaced entry\n",
        )
        assert parse_updates_log(path) == ["2026-05-07 — Spaced entry"]
