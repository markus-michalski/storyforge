"""Tests for linting rules in a book's CLAUDE.md.

Issue #145 — `lint_book_rules` (bulk) + `update_book_rule(validate=True)`
(single-rule) share the same per-rule linter so warnings are consistent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.claudemd.manager import init_claudemd
from tools.claudemd.rules_editor import update_rule
from tools.claudemd.rules_lint import (
    LINT_BRACKET_PLACEHOLDER,
    LINT_ITALIC_EXAMPLES_WITH_BAN_CUE,
    LINT_MIXED_POSITIVE_NEGATIVE_QUOTES,
    LINT_SCANNER_EXTRACTS_NOTHING,
    lint_book_rules,
    lint_rule_text,
)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def book_config(tmp_path: Path) -> dict:
    content_root = tmp_path / "books"
    book_dir = content_root / "projects" / "my-book"
    book_dir.mkdir(parents=True)
    (book_dir / "README.md").write_text("# My Book\n", encoding="utf-8")
    return {"paths": {"content_root": str(content_root)}}


def _seed_rules(book_config: dict, rules: list[str]) -> Path:
    from tools.claudemd.manager import resolve_claudemd_path

    init_claudemd(book_config, PLUGIN_ROOT, "my-book")
    path = resolve_claudemd_path(book_config, "my-book")
    content = path.read_text(encoding="utf-8")
    bullets = "\n".join(f"- {r}" for r in rules)
    new_content = content.replace(
        "<!-- RULES:START -->\n<!-- RULES:END -->",
        f"<!-- RULES:START -->\n{bullets}\n<!-- RULES:END -->",
    )
    path.write_text(new_content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# lint_rule_text — single-rule linter (used by both single + bulk paths)
# ---------------------------------------------------------------------------


class TestLintBracketPlaceholder:
    def test_flags_word_placeholder_in_backticks(self):
        rule = "Avoid `[noun] of [noun]` constructions"
        result = lint_rule_text(rule)
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_BRACKET_PLACEHOLDER in codes

    def test_flags_subj_verb_placeholder(self):
        rule = r"Avoid `[subj] [verb]ed` patterns"
        result = lint_rule_text(rule)
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_BRACKET_PLACEHOLDER in codes

    def test_does_not_flag_real_character_class(self):
        # [a-z] is a legitimate character class.
        rule = r"Avoid `[a-z]+\s+began` openers"
        result = lint_rule_text(rule)
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_BRACKET_PLACEHOLDER not in codes

    def test_does_not_flag_when_no_brackets(self):
        rule = "Avoid `clocked` as a verb"
        result = lint_rule_text(rule)
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_BRACKET_PLACEHOLDER not in codes


class TestLintItalicExamplesWithBanCue:
    def test_flags_italic_examples_when_ban_cue_present(self):
        rule = (
            'Avoid these phrases: *"clocked"*, *"registered"*, *"noticed it"*'
        )
        result = lint_rule_text(rule)
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_ITALIC_EXAMPLES_WITH_BAN_CUE in codes

    def test_does_not_flag_italic_without_ban_cue(self):
        rule = 'Tone reference: *"like cold steel"* — keep this kind of weight'
        result = lint_rule_text(rule)
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_ITALIC_EXAMPLES_WITH_BAN_CUE not in codes

    def test_does_not_flag_when_examples_already_in_backticks(self):
        rule = "Avoid `clocked`, `registered`, `noticed it` as verbs"
        result = lint_rule_text(rule)
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_ITALIC_EXAMPLES_WITH_BAN_CUE not in codes


class TestLintMixedPositiveNegativeQuotes:
    def test_flags_mixed_quotes_with_ban_cue(self):
        # Has ban cue + multiple quoted phrases — scanner can't tell
        # bans from positive examples, both get extracted as bans.
        rule = 'Avoid "clocked" — replace with "noticed" or "registered"'
        result = lint_rule_text(rule)
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_MIXED_POSITIVE_NEGATIVE_QUOTES in codes

    def test_does_not_flag_single_quote_with_ban_cue(self):
        rule = 'Avoid "clocked" as a verb'
        result = lint_rule_text(rule)
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_MIXED_POSITIVE_NEGATIVE_QUOTES not in codes

    def test_does_not_flag_quotes_without_ban_cue(self):
        rule = 'Compare "felt like steel" with "felt like ice" for tone'
        result = lint_rule_text(rule)
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_MIXED_POSITIVE_NEGATIVE_QUOTES not in codes


class TestLintScannerExtractsNothing:
    def test_flags_when_ban_cue_but_no_extractable_pattern(self):
        # Has ban cue but no backticks and no quotes → scanner extracts nothing.
        rule = "Avoid passive voice constructions in dialog"
        result = lint_rule_text(rule)
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_SCANNER_EXTRACTS_NOTHING in codes

    def test_does_not_flag_when_pattern_extracted(self):
        rule = "Avoid `clocked` as a verb"
        result = lint_rule_text(rule)
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_SCANNER_EXTRACTS_NOTHING not in codes

    def test_does_not_flag_narrative_rules_without_ban_cue(self):
        # Pure narrative rule, no ban cue — silent rules are fine.
        rule = "Keep prose dense and concrete"
        result = lint_rule_text(rule)
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_SCANNER_EXTRACTS_NOTHING not in codes


class TestExtractedPatterns:
    def test_returns_extracted_patterns_for_valid_rule(self):
        rule = "Avoid `clocked` and `began to`"
        result = lint_rule_text(rule)
        labels = [p["label"] for p in result["extracted_patterns"]]
        assert "clocked" in labels
        assert "began to" in labels

    def test_empty_for_unscannable_rule(self):
        rule = "Keep prose dense and concrete"
        result = lint_rule_text(rule)
        assert result["extracted_patterns"] == []


# ---------------------------------------------------------------------------
# lint_book_rules — bulk
# ---------------------------------------------------------------------------


class TestLintBookRules:
    def test_returns_per_rule_findings(self, book_config):
        _seed_rules(
            book_config,
            [
                "Avoid `clocked` as a verb",  # clean
                "Avoid passive voice constructions",  # SCANNER_EXTRACTS_NOTHING
                'Avoid "clocked" — replace with "noticed"',  # MIXED_QUOTES
            ],
        )
        result = lint_book_rules(book_config, "my-book")
        assert result["rules_total"] == 3
        # Issues only for rules with warnings.
        issue_indices = [i["rule_index"] for i in result["issues"]]
        assert 0 not in issue_indices  # clean rule, no warnings
        assert 1 in issue_indices
        assert 2 in issue_indices

    def test_empty_when_no_rules(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        result = lint_book_rules(book_config, "my-book")
        assert result["rules_total"] == 0
        assert result["issues"] == []

    def test_rule_12_firelight_regression(self, book_config):
        """Reproduces the actual bug from `Blood & Binary Firelight` Rule 12:
        eight banned-phrase examples wrapped in *"..."* — invisible to scanner.
        """
        _seed_rules(
            book_config,
            [
                "**Body-part anti-patterns** — Avoid these constructions: "
                '*"hand on chest"*, *"breath caught"*, *"chest tight"*'
            ],
        )
        result = lint_book_rules(book_config, "my-book")
        # The lint should flag this rule.
        assert len(result["issues"]) == 1
        codes = [w["code"] for w in result["issues"][0]["warnings"]]
        assert LINT_ITALIC_EXAMPLES_WITH_BAN_CUE in codes


# ---------------------------------------------------------------------------
# Consistency: single-rule lint and bulk lint produce identical warnings
# for the same rule.
# ---------------------------------------------------------------------------


class TestLintConsistency:
    def test_single_and_bulk_warnings_identical(self, book_config):
        rule_text = 'Avoid "clocked" — replace with "noticed"'
        _seed_rules(book_config, [rule_text])

        bulk = lint_book_rules(book_config, "my-book")
        bulk_codes = sorted(w["code"] for w in bulk["issues"][0]["warnings"])

        single = lint_rule_text(rule_text)
        single_codes = sorted(w["code"] for w in single["warnings"])

        assert bulk_codes == single_codes

    def test_validate_flag_in_update_rule_runs_lint(self, book_config):
        _seed_rules(book_config, ["**R1** — first"])
        result = update_rule(
            book_config, "my-book",
            rule_index=0,
            new_text="**R1** — Avoid passive voice constructions",
            validate=True,
        )
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_SCANNER_EXTRACTS_NOTHING in codes

    def test_validate_false_skips_lint(self, book_config):
        _seed_rules(book_config, ["**R1** — first"])
        result = update_rule(
            book_config, "my-book",
            rule_index=0,
            new_text="**R1** — Avoid passive voice constructions",
            validate=False,
        )
        assert result.get("warnings", []) == []
