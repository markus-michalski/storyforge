"""Unit tests for tools.analysis.manuscript.rules — rule parser + scanner."""

from __future__ import annotations

from pathlib import Path

from tools.analysis.manuscript.rules import (
    _extract_patterns_from_rule,
    _read_book_rules,
    _rule_label,
    _scan_book_rules,
)


class TestExtractPatternsFromRule:
    def test_backtick_literal(self) -> None:
        patterns = _extract_patterns_from_rule("Avoid `synergy` in narration.")
        assert len(patterns) == 1
        label, compiled = patterns[0]
        assert label == "synergy"
        assert compiled.search("the synergy here") is not None

    def test_backtick_with_regex_metachars(self) -> None:
        patterns = _extract_patterns_from_rule(
            "Limit `(very|really)\\s+\\w+` adverb pile-ups."
        )
        assert len(patterns) == 1
        _label, compiled = patterns[0]
        assert compiled.search("very tired") is not None

    def test_quoted_with_ban_cue_extracts(self) -> None:
        patterns = _extract_patterns_from_rule(
            'Banned phrase: "the worn-out construction".'
        )
        assert any("worn-out" in label for label, _ in patterns)

    def test_quoted_without_ban_cue_skipped(self) -> None:
        # No ban cue → quoted phrase treated as example, not pattern.
        patterns = _extract_patterns_from_rule(
            'Use "fresh imagery" instead of stale phrasing.'
        )
        assert patterns == []

    def test_short_backtick_skipped(self) -> None:
        patterns = _extract_patterns_from_rule("Note `a` is too short to ban.")
        assert patterns == []


class TestRuleLabel:
    def test_extracts_bold_title(self) -> None:
        label = _rule_label("**No vague nouns** — avoid 'thing' as filler.")
        assert label == "No vague nouns"

    def test_falls_back_to_rule_text(self) -> None:
        label = _rule_label("Plain rule with no bold prefix.")
        assert "Plain rule" in label

    def test_truncates_long_titles(self) -> None:
        label = _rule_label("a" * 200)
        assert len(label) <= 80


class TestReadBookRules:
    def test_reads_rules_section(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text(
            "## Rules\n\n- First rule\n- Second rule\n\n## Other\n",
            encoding="utf-8",
        )
        rules = _read_book_rules(tmp_path)
        assert rules == ["First rule", "Second rule"]

    def test_no_rules_section(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("# Book\n", encoding="utf-8")
        assert _read_book_rules(tmp_path) == []

    def test_strips_html_comments_inside_rules(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text(
            "## Rules\n\n<!-- generated -->\n- Real rule\n\n## Other\n",
            encoding="utf-8",
        )
        rules = _read_book_rules(tmp_path)
        assert rules == ["Real rule"]


class TestScanBookRules:
    def _build_book(self, tmp_path: Path, rule_text: str, draft_text: str) -> Path:
        book = tmp_path / "demo"
        (book / "chapters" / "01-opening").mkdir(parents=True)
        (book / "CLAUDE.md").write_text(
            f"## Rules\n\n- {rule_text}\n",
            encoding="utf-8",
        )
        (book / "chapters" / "01-opening" / "draft.md").write_text(
            draft_text, encoding="utf-8"
        )
        return book

    def test_finds_rule_violation(self, tmp_path: Path) -> None:
        book = self._build_book(
            tmp_path,
            "Avoid `synergy` in narration.",
            "The synergy of the team was unmatched.\n",
        )
        findings = _scan_book_rules(book)
        assert len(findings) == 1
        assert findings[0].category == "book_rule_violation"
        assert findings[0].severity == "high"
        assert findings[0].source_rule.startswith("Avoid")

    def test_no_findings_when_clean(self, tmp_path: Path) -> None:
        book = self._build_book(
            tmp_path,
            "Avoid `synergy`.",
            "Their teamwork was excellent.\n",
        )
        assert _scan_book_rules(book) == []
