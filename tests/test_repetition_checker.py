"""Tests for the repetition checker, especially the per-book CLAUDE.md rule scan.

Covers:
- Parsing rules out of a book's CLAUDE.md (static entries + RULES:START block).
- Heuristic extraction of scannable patterns from rule text.
- The `_scan_book_rules` pass that turns rule violations into high-severity
  findings with a `source_rule` field pointing back to the offending rule.
- Integration into `scan_repetitions` so book-rule findings appear alongside
  n-gram findings and ignore frequency thresholds.
"""

from __future__ import annotations

from pathlib import Path

from tools.analysis.repetition_checker import (
    _extract_patterns_from_rule,
    _read_book_rules,
    _scan_book_rules,
    scan_repetitions,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


CLAUDEMD_WITH_RULES = """# Test Book

## Book Facts
- **POV:** third person

## Rules

- **Imperial units only** — Pacific Northwest setting, no metric.

<!-- RULES:START -->
- **Avoid vague-noun "thing" as a fallback** — banned: "doing a thing with his hand". How to apply: grep for ` thing ` in narration.
- **Do not use "clocked" as a verb for noticing** — alternatives: noticed, saw, registered.
- **Limit "specific kind of X that Y" construction** — scan for `the (specific|particular|kind of|sort of) [a-z]+ (that|of)`.
<!-- RULES:END -->

## Callback Register
- **Gary the cat** — must return.
"""


CLAUDEMD_EMPTY_RULES = """# Test Book

## Book Facts
- **POV:** third person

## Rules

<!-- RULES:START -->
<!-- RULES:END -->

## Callback Register
"""


def _write_book(tmp_path: Path, claudemd: str, chapters: dict[str, str]) -> Path:
    """Create a minimal book layout: CLAUDE.md + chapters/<slug>/draft.md."""
    book = tmp_path / "book"
    book.mkdir()
    (book / "CLAUDE.md").write_text(claudemd, encoding="utf-8")
    chapters_dir = book / "chapters"
    chapters_dir.mkdir()
    for slug, content in chapters.items():
        d = chapters_dir / slug
        d.mkdir()
        (d / "draft.md").write_text(content, encoding="utf-8")
    return book


# ---------------------------------------------------------------------------
# _read_book_rules
# ---------------------------------------------------------------------------


class TestReadBookRules:
    def test_parses_static_and_dynamic_entries(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CLAUDEMD_WITH_RULES, {})
        rules = _read_book_rules(book)
        joined = " ".join(rules)
        assert "Imperial units only" in joined
        assert "vague-noun" in joined
        assert "clocked" in joined
        assert "specific kind of X that Y" in joined
        # Callback section must NOT leak in
        assert "Gary the cat" not in joined

    def test_returns_empty_when_claudemd_missing(self, tmp_path: Path) -> None:
        book = tmp_path / "book"
        book.mkdir()
        assert _read_book_rules(book) == []

    def test_returns_empty_when_rules_section_absent(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, "# Book\n\nNo rules here.\n", {})
        assert _read_book_rules(book) == []

    def test_returns_empty_when_rules_section_is_empty(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, {})
        assert _read_book_rules(book) == []

    def test_strips_leading_bullet_marker(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CLAUDEMD_WITH_RULES, {})
        rules = _read_book_rules(book)
        # No rule should still start with "- " after parsing
        for r in rules:
            assert not r.startswith("- ")


# ---------------------------------------------------------------------------
# _extract_patterns_from_rule
# ---------------------------------------------------------------------------


class TestExtractPatterns:
    def test_extracts_backtick_literal_substring(self) -> None:
        rule = "grep for ` thing ` in narration"
        patterns = _extract_patterns_from_rule(rule)
        hay = "he was doing a thing with his hand"
        assert any(p.search(hay) for _, p in patterns)

    def test_extracts_backtick_regex(self) -> None:
        rule = "scan for `the (specific|particular) [a-z]+ (that|of)`"
        patterns = _extract_patterns_from_rule(rule)
        hay = "the specific quality of quiet"
        assert any(p.search(hay) for _, p in patterns)

    def test_extracts_double_quoted_phrase(self) -> None:
        rule = 'banned: "doing a thing with his hand"'
        patterns = _extract_patterns_from_rule(rule)
        hay = "he was doing a thing with his hand, softly"
        assert any(p.search(hay) for _, p in patterns)

    def test_case_insensitive_matching(self) -> None:
        rule = 'banned: "Clocked"'
        patterns = _extract_patterns_from_rule(rule)
        hay = "She clocked him walking into the store."
        assert any(p.search(hay) for _, p in patterns)

    def test_ignores_italics(self) -> None:
        # Italics are used for examples/narrative, not scannable patterns.
        rule = "reader disliked *a long exhale* as a default move"
        patterns = _extract_patterns_from_rule(rule)
        hay = "He gave a long exhale."
        # No italic-sourced pattern should match — otherwise we'd flag examples
        assert not any(p.search(hay) for _, p in patterns)

    def test_skips_too_short_quoted_strings(self) -> None:
        rule = 'ban: "a" and "ok"'
        patterns = _extract_patterns_from_rule(rule)
        assert patterns == []

    def test_no_patterns_returns_empty(self) -> None:
        rule = "Keep the narrative voice consistent and grounded."
        assert _extract_patterns_from_rule(rule) == []

    def test_quoted_strings_require_ban_cue(self) -> None:
        # Rule WITHOUT a ban cue — quoted phrases are examples, not bans.
        rule = 'e.g. Kael ordering "a second coffee in a diner" is fine'
        patterns = _extract_patterns_from_rule(rule)
        assert not any(p.search("a second coffee in a diner") for _, p in patterns)

    def test_quoted_strings_extracted_with_cue(self) -> None:
        rule = 'banned: "doing a thing with his hand"'
        patterns = _extract_patterns_from_rule(rule)
        assert any(p.search("doing a thing with his hand") for _, p in patterns)

    def test_preserves_backtick_whitespace(self) -> None:
        # ` thing ` (with spaces) should NOT match "something" or "things".
        rule = "grep for ` thing ` in narration"
        patterns = _extract_patterns_from_rule(rule)
        hay_bad = "there was something wrong"
        hay_good = "doing a thing with his hand"
        assert not any(p.search(hay_bad) for _, p in patterns)
        assert any(p.search(hay_good) for _, p in patterns)

    def test_dedups_identical_patterns(self) -> None:
        # Same pattern appearing as both backtick and quote should collapse.
        rule = 'banned: "clocked" — avoid `clocked`'
        patterns = _extract_patterns_from_rule(rule)
        assert len(patterns) == 1


# ---------------------------------------------------------------------------
# _scan_book_rules (integration with chapter drafts)
# ---------------------------------------------------------------------------


class TestScanBookRules:
    def test_finds_literal_violation(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": "# Chapter 1\n\nHe was doing a thing with his hand, quietly.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_WITH_RULES, chapters)
        findings = _scan_book_rules(book)
        assert findings, "expected at least one violation finding"
        assert any("thing" in f.phrase.lower() for f in findings)

    def test_finds_regex_violation(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": "# Chapter 1\n\nIt had the specific quality of quiet that pubs knew.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_WITH_RULES, chapters)
        findings = _scan_book_rules(book)
        assert any(f.category == "book_rule_violation" for f in findings)

    def test_populates_source_rule(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": "# Chapter 1\n\nShe clocked him across the room.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_WITH_RULES, chapters)
        findings = _scan_book_rules(book)
        clocked_finding = next(
            f for f in findings if "clocked" in f.phrase.lower()
        )
        assert clocked_finding.source_rule is not None
        assert "clocked" in clocked_finding.source_rule.lower()

    def test_severity_always_high(self, tmp_path: Path) -> None:
        # Even a single occurrence must be flagged — user-authored rules
        # override frequency thresholds.
        chapters = {
            "01-open": "# Chapter 1\n\nShe clocked him once, just once.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_WITH_RULES, chapters)
        findings = _scan_book_rules(book)
        assert findings
        assert all(f.severity == "high" for f in findings)

    def test_category_is_book_rule_violation(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": "# Chapter 1\n\nShe clocked him across the room.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_WITH_RULES, chapters)
        findings = _scan_book_rules(book)
        assert all(f.category == "book_rule_violation" for f in findings)

    def test_no_violations_returns_empty(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": "# Chapter 1\n\nClean prose without any banned terms.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_WITH_RULES, chapters)
        assert _scan_book_rules(book) == []

    def test_missing_claudemd_returns_empty(self, tmp_path: Path) -> None:
        book = tmp_path / "book"
        (book / "chapters" / "01-x").mkdir(parents=True)
        (book / "chapters" / "01-x" / "draft.md").write_text("clocked him.", encoding="utf-8")
        assert _scan_book_rules(book) == []

    def test_records_all_occurrences(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": "# Chapter 1\n\nShe clocked him.\nHe clocked her.\n",
            "02-mid": "# Chapter 2\n\nThey all clocked each other.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_WITH_RULES, chapters)
        findings = _scan_book_rules(book)
        clocked = next(f for f in findings if "clocked" in f.phrase.lower())
        assert clocked.count >= 3
        chapters_hit = {o.chapter for o in clocked.occurrences}
        assert chapters_hit == {"01-open", "02-mid"}


# ---------------------------------------------------------------------------
# Integration: scan_repetitions returns book-rule findings
# ---------------------------------------------------------------------------


class TestScanRepetitionsIntegration:
    def test_book_rule_findings_are_merged(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": "# Chapter 1\n\nShe clocked him at the counter.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_WITH_RULES, chapters)
        result = scan_repetitions(book)
        categories = {f["category"] for f in result["findings"]}
        assert "book_rule_violation" in categories

    def test_book_rule_findings_precede_ngram_findings(self, tmp_path: Path) -> None:
        # Rule violations must sort to the top even with severity=="high" ngrams.
        chapters = {
            "01-open": "# Chapter 1\n\nShe clocked him once.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_WITH_RULES, chapters)
        result = scan_repetitions(book)
        assert result["findings"], "expected at least the rule finding"
        assert result["findings"][0]["category"] == "book_rule_violation"

    def test_summary_contains_book_rule_category(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": "# Chapter 1\n\nShe clocked him.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_WITH_RULES, chapters)
        result = scan_repetitions(book)
        assert "book_rule_violation" in result["summary"]
