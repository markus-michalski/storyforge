"""Tests for scan_for_named_characters alias resolution (Issue #182).

Covers:
- Auto-extract quoted aliases from name field ("Sera" from 'Seraphina "Sera"')
- Explicit aliases: frontmatter field
- Word-boundary matching avoids false positives
- Combined quoted + explicit aliases
- Regression: plain unquoted name still resolves (legacy path)
"""

from pathlib import Path

from tools.state.loaders.people import scan_for_named_characters


def _make_char(chars_dir: Path, slug: str, frontmatter: str) -> Path:
    path = chars_dir / f"{slug}.md"
    path.write_text(f"---\n{frontmatter}\n---\n", encoding="utf-8")
    return path


class TestScanForNamedCharactersAliases:
    def test_quoted_alias_in_name_is_recognized(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        chars_dir.mkdir()
        _make_char(chars_dir, "seraphina", 'name: Seraphina "Sera"\nrole: supporting')
        outline = "Sera arrives at the gate before dawn."
        assert scan_for_named_characters(outline, chars_dir) == ["seraphina"]

    def test_explicit_aliases_field_is_recognized(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        chars_dir.mkdir()
        _make_char(chars_dir, "seraphina", "name: Seraphina\naliases:\n  - Sera\n  - S.")
        outline = "S. steps forward and takes the lead."
        assert scan_for_named_characters(outline, chars_dir) == ["seraphina"]

    def test_word_boundary_avoids_false_positive(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        chars_dir.mkdir()
        _make_char(chars_dir, "lin", "name: Lin\nrole: supporting")
        outline = "The linguistics professor entered the room."
        assert scan_for_named_characters(outline, chars_dir) == []

    def test_quoted_and_explicit_aliases_combined(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        chars_dir.mkdir()
        _make_char(chars_dir, "vincent", 'name: Vincent "Vince"\naliases:\n  - V.')
        outline_vince = "Vince poured two glasses."
        outline_v = "V. nodded without a word."
        assert scan_for_named_characters(outline_vince, chars_dir) == ["vincent"]
        assert scan_for_named_characters(outline_v, chars_dir) == ["vincent"]

    def test_legacy_plain_name_still_resolves(self, tmp_path: Path) -> None:
        # Regression: unquoted name without aliases must still work.
        chars_dir = tmp_path / "characters"
        chars_dir.mkdir()
        _make_char(chars_dir, "mom", "name: Mom\nrole: supporting")
        outline = "Mom and Dad sat on the porch."
        assert scan_for_named_characters(outline, chars_dir) == ["mom"]
