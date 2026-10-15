"""Issue #682: plot/tone.md "Banned Prose Patterns" is enforced like book rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.banlist_loader import (
    load_tone_banned_patterns,
    load_tone_banned_rule_texts,
    parse_tone_banned_bullets,
)

PLUGIN_ROOT = Path(__file__).resolve().parents[2]

H2 = """# Tone

## Banned Prose Patterns (Book-Specific)

- `plötzlich` Max. 1 pro Kapitel
- `Mit einem Mal`
- "plötzlich" mehr als einmal pro Geschichte
- Keine Wetterbeschreibung als
  Stimmungsmacher.

## Litmus Test

1. Lacht jemand?
"""

H3 = H2.replace("## Banned Prose Patterns", "### Banned Prose Patterns")

UNENFORCED = ['"plötzlich" mehr als einmal pro Geschichte', "Keine Wetterbeschreibung als Stimmungsmacher."]


def _book(tmp_path: Path, tone: str | None) -> Path:
    (tmp_path / "plot").mkdir(exist_ok=True)
    if tone is not None:
        (tmp_path / "plot" / "tone.md").write_text(tone, encoding="utf-8")
    return tmp_path


class TestParse:
    @pytest.mark.parametrize("text", [H2, H3])
    def test_heading_level_2_and_3_same_bullets(self, text: str) -> None:
        bullets = parse_tone_banned_bullets(text)
        assert len(bullets) == 4
        assert bullets[3] == "Keine Wetterbeschreibung als Stimmungsmacher."

    def test_level3_section_ends_at_next_level2(self) -> None:
        assert "Lacht jemand?" not in " ".join(parse_tone_banned_bullets(H3))

    def test_placeholders_and_comments_skipped(self) -> None:
        text = "### Banned Prose Patterns\n\n<!-- `x` -->\n- *e.g. No weather.*\n- `real`\n"
        assert parse_tone_banned_bullets(text) == ["`real`"]

    def test_no_section(self) -> None:
        assert parse_tone_banned_bullets("# Tone\n\n## Litmus Test\n- a\n") == []


class TestLoad:
    def test_patterns_limit_and_unenforced(self, tmp_path: Path) -> None:
        patterns, unenforced = load_tone_banned_patterns(_book(tmp_path, H2))
        by_label = {p.label: p for p in patterns}
        assert set(by_label) == {"plötzlich", "Mit einem Mal"}
        assert by_label["plötzlich"].chapter_limit == 1
        assert by_label["Mit einem Mal"].chapter_limit == 0
        assert by_label["Mit einem Mal"].severity == "block"
        assert unenforced == UNENFORCED

    def test_free_prose_not_guessed(self, tmp_path: Path) -> None:
        tone = '### Banned Prose Patterns\n\n- "plötzlich" mehr als einmal pro Geschichte\n'
        patterns, unenforced = load_tone_banned_patterns(_book(tmp_path, tone))
        assert patterns == []
        assert len(unenforced) == 1

    def test_missing_file_and_section(self, tmp_path: Path) -> None:
        assert load_tone_banned_patterns(_book(tmp_path, None)) == ([], [])
        assert load_tone_banned_rule_texts(_book(tmp_path, "# Tone\n")) == ([], [])


class TestPipelines:
    def test_chapter_validator_enforces_with_density(self, tmp_path: Path) -> None:
        from tools.analysis.chapter_validator import _book_banned_patterns

        got = {label: limit for label, _p, limit in _book_banned_patterns(_book(tmp_path, H2))}
        assert got["plötzlich"] == 1
        assert got["Mit einem Mal"] == 0

    def test_humanizer_load_patterns_includes_tone(self, tmp_path: Path) -> None:
        from tools.analysis.humanizer_scan import load_patterns

        _s, _t, author = load_patterns(PLUGIN_ROOT, None, book_root=_book(tmp_path, H2))
        assert "Mit einem Mal" in {p.label for p in author}
        _s, _t, author = load_patterns(PLUGIN_ROOT, None)
        assert "Mit einem Mal" not in {p.label for p in author}

    def test_banned_phrases_collector(self, tmp_path: Path) -> None:
        from tools.state.loaders.banlist import collect_banned_phrases

        out = collect_banned_phrases(_book(tmp_path, H2), PLUGIN_ROOT)
        sources = {e["phrase"]: e["source"] for e in out}
        assert sources.get("Mit einem Mal") == "plot/tone.md"

    def test_manuscript_scanner_flags_violation(self, tmp_path: Path, monkeypatch) -> None:
        from tools.analysis.manuscript import rules

        book = _book(tmp_path, H2)
        ch = book / "chapters" / "01-a"
        ch.mkdir(parents=True)
        (ch / "draft.md").write_text("Er ging. Mit einem Mal war es still.\n", encoding="utf-8")
        monkeypatch.setattr(rules, "_read_book_rules", lambda _p: [])
        findings = rules._scan_book_rules(book)
        assert any("Mit einem Mal" in f.phrase for f in findings)


class TestBriefs:
    def test_review_brief_level3_and_unenforced(self) -> None:
        from tools.state.review_brief import _parse_tonal_rules

        parsed = _parse_tonal_rules(H3)
        assert len(parsed["banned_prose_patterns"]) == 4
        assert parsed["banned_prose_unenforced"] == UNENFORCED

    def test_writing_brief_carries_banned_patterns(self, tmp_path: Path) -> None:
        from tools.state.brief_common import Recorder
        from tools.state.chapter_writing_brief import _gather_tone_banned

        out = _gather_tone_banned(_book(tmp_path, H2), recorder=Recorder([]))
        assert len(out["enforced"]) == 2
        assert out["advisory_unenforced"] == UNENFORCED
