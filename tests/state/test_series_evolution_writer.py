"""Tests for series-tracker evolution-section writers (Issue #200, D-1 of #195).

Covers:
- ``write_evolution_section`` — replaces or inserts a Start/Ende/geplant
  slot in the right band, preserving existing structure (bullet vs h3
  shape, freeform bullets, untouched bands).
- ``append_updates_log_entry`` — appends a dated entry, creating the
  section if needed and clearing common placeholders.

Writers are deliberately conservative: they don't reformat the file,
they don't reorder bands, and they don't migrate between shapes. They
write into the structure that's there.
"""

from __future__ import annotations

from pathlib import Path

from tools.state.loaders.series import (
    append_updates_log_entry,
    parse_evolution_sections,
    parse_updates_log,
    write_evolution_section,
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


class TestWriteEvolutionSectionBulletShape:
    def test_replaces_existing_ende_bullet(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Evolution per Band\n\n### B1 Firelight\n- **Start:** Cabin-Einsiedler.\n- **Ende:** old end content.\n",
        )
        write_evolution_section(path, band="B1", kind="ende", content="new end content.")

        sections = parse_evolution_sections(path)
        assert sections["B1"]["ende"] == "new end content."
        # Start slot is preserved.
        assert sections["B1"]["start"] == "Cabin-Einsiedler."

    def test_inserts_ende_bullet_when_missing(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Evolution per Band\n\n### B1 Firelight\n- **Start:** Off-page-Praesenz.\n",
        )
        write_evolution_section(path, band="B1", kind="ende", content="Sera stirbt trotz allem.")
        sections = parse_evolution_sections(path)
        assert sections["B1"]["start"] == "Off-page-Praesenz."
        assert sections["B1"]["ende"] == "Sera stirbt trotz allem."

    def test_preserves_freeform_bullets(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "caelan.md",
            "## Evolution per Band\n\n"
            "### B1 Firelight\n"
            "- **Start:** Off-page.\n"
            "- **Ch 21 Szene 2:** Caelan findet Theo.\n"
            "- **Ende:** old.\n",
        )
        write_evolution_section(path, band="B1", kind="ende", content="new ende.")
        text = path.read_text(encoding="utf-8")
        # Freeform bullet survives.
        assert "**Ch 21 Szene 2:**" in text
        assert "Caelan findet Theo" in text
        # Ende was replaced, not duplicated.
        assert text.count("**Ende:**") == 1
        assert "new ende." in text
        assert "old.\n" not in text  # whole-line check; "old" might still
        # appear in other contexts but the line "- **Ende:** old." is gone

    def test_writes_to_correct_band_when_multiple_present(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Evolution per Band\n\n"
            "### B1 Firelight\n"
            "- **Start:** B1 start.\n"
            "- **Ende:** B1 ende.\n\n"
            "### B2 Moonrise (geplant)\n"
            "- B2 plan line one.\n"
            "- B2 plan line two.\n",
        )
        write_evolution_section(path, band="B2", kind="ende", content="B2 final state harvested.")
        sections = parse_evolution_sections(path)
        # B1 untouched.
        assert sections["B1"]["start"] == "B1 start."
        assert sections["B1"]["ende"] == "B1 ende."
        # B2 got a new keyed Ende bullet.
        assert sections["B2"]["ende"] == "B2 final state harvested."

    def test_inserts_band_when_band_missing(self, tmp_path: Path) -> None:
        # Tracker has B1 only; write Ende for B2 → creates new ### B2 block.
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Evolution per Band\n\n### B1 Firelight\n- **Start:** Start.\n- **Ende:** End.\n",
        )
        write_evolution_section(path, band="B2", kind="ende", content="B2 ende from harvest.")
        sections = parse_evolution_sections(path)
        assert "B2" in sections
        assert sections["B2"]["ende"] == "B2 ende from harvest."

    def test_creates_evolution_section_when_missing(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Snapshot\n\nEssence text.\n\n## Beziehungen ueber die Bande\n\n- **Theo:** ...\n",
        )
        write_evolution_section(path, band="B1", kind="ende", content="Bootstrapped.")
        sections = parse_evolution_sections(path)
        assert sections["B1"]["ende"] == "Bootstrapped."
        # Section ordering: Evolution should sit between Snapshot and
        # Beziehungen — but at minimum, Beziehungen must still be present
        # and parseable.
        from tools.state.loaders.series import parse_relationships_section

        assert "**Theo:**" in parse_relationships_section(path)

    def test_other_bands_remain_untouched_byte_for_byte(self, tmp_path: Path) -> None:
        body = (
            "## Evolution per Band\n\n"
            "### B1 Firelight\n"
            "- **Start:** B1 start.\n"
            "- **Ch 5 Detail:** detail one.\n"
            "- **Ch 12 Detail:** detail two.\n"
            "- **Ende:** B1 end.\n\n"
            "### B2 Moonrise (geplant)\n"
            "- B2 plan one.\n"
            "- B2 plan two.\n"
        )
        path = _write_tracker(tmp_path / "kael.md", body)
        write_evolution_section(path, band="B2", kind="ende", content="B2 harvested ende.")
        text = path.read_text(encoding="utf-8")
        # B1 details and bullets preserved.
        assert "- **Ch 5 Detail:** detail one." in text
        assert "- **Ch 12 Detail:** detail two." in text
        assert "- **Start:** B1 start." in text
        assert "- **Ende:** B1 end." in text


class TestWriteEvolutionSectionPlannedBand:
    def test_writes_geplant_into_planned_band(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Evolution per Band\n\n### B2 Moonrise (geplant)\n- old plan line one.\n- old plan line two.\n",
        )
        write_evolution_section(
            path,
            band="B2",
            kind="geplant",
            content="Updated plan after series-planner pass.",
        )
        sections = parse_evolution_sections(path)
        assert "Updated plan" in sections["B2"]["geplant"]
        # Old plan content was replaced.
        assert "old plan line one" not in sections["B2"]["geplant"]


class TestWriteEvolutionSectionH3Shape:
    def test_replaces_existing_h3_body(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "viktor.md",
            "## Evolution per Band\n\n### B1 Start\nold start text.\n\n### B1 Ende\nold end text.\n",
        )
        write_evolution_section(path, band="B1", kind="ende", content="new end text.")
        sections = parse_evolution_sections(path)
        assert sections["B1"]["start"] == "old start text."
        assert sections["B1"]["ende"] == "new end text."

    def test_inserts_new_h3_when_kind_missing(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "viktor.md",
            "## Evolution per Band\n\n### B1 Start\nstart text.\n",
        )
        write_evolution_section(path, band="B1", kind="ende", content="harvested ende.")
        sections = parse_evolution_sections(path)
        assert sections["B1"]["start"] == "start text."
        assert sections["B1"]["ende"] == "harvested ende."


class TestAppendUpdatesLogEntry:
    def test_appends_to_existing_log(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Updates Log\n\n- 2026-05-01 — Tracker scaffolded\n",
        )
        append_updates_log_entry(path, message="Harvested from B1 final state", date="2026-05-08")
        entries = parse_updates_log(path)
        assert entries == [
            "2026-05-01 — Tracker scaffolded",
            "2026-05-08 — Harvested from B1 final state",
        ]

    def test_creates_log_section_when_missing(self, tmp_path: Path) -> None:
        path = _write_tracker(tmp_path / "kael.md", "## Snapshot\n\nEssence.\n")
        append_updates_log_entry(path, message="First entry", date="2026-05-08")
        entries = parse_updates_log(path)
        assert entries == ["2026-05-08 — First entry"]

    def test_default_date_is_today_iso(self, tmp_path: Path) -> None:
        # When date is omitted, the entry uses today's UTC date in
        # ISO format. We don't assert the exact day (would flake at
        # midnight UTC) but assert the shape.
        import re as _re

        path = _write_tracker(tmp_path / "kael.md", "## Updates Log\n")
        append_updates_log_entry(path, message="No-date entry")
        entries = parse_updates_log(path)
        assert len(entries) == 1
        assert _re.match(r"\d{4}-\d{2}-\d{2} — No-date entry", entries[0])

    def test_strips_placeholder_when_appending(self, tmp_path: Path) -> None:
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Updates Log\n\n(noch keine Eintraege)\n",
        )
        append_updates_log_entry(path, message="First real entry", date="2026-05-08")
        entries = parse_updates_log(path)
        assert entries == ["2026-05-08 — First real entry"]
        text = path.read_text(encoding="utf-8")
        assert "(noch keine Eintraege)" not in text

    def test_does_not_duplicate_identical_entry_same_day(self, tmp_path: Path) -> None:
        # Idempotency: re-running harvest on the same day with the same
        # message should not double-write the log entry. Authors might
        # accidentally re-trigger the skill.
        path = _write_tracker(
            tmp_path / "kael.md",
            "## Updates Log\n\n- 2026-05-08 — Harvested from B1 final state\n",
        )
        append_updates_log_entry(path, message="Harvested from B1 final state", date="2026-05-08")
        entries = parse_updates_log(path)
        assert entries == ["2026-05-08 — Harvested from B1 final state"]
