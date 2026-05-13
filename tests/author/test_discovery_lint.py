"""Tests for ``tools.author.discovery_lint`` (Issue #218).

The author-discovery linter surfaces shapes the manuscript-checker scanner
will silently mis-extract from author-profile ``## Writing Discoveries``
write paths. It mirrors ``tools.claudemd.rules_lint.lint_rule_text`` but
applies section-aware semantics: italics in author Don'ts are bannable
(unlike book rules where they are narrative examples), Recurring Tics
fall back to title text when the bold title has no quote, and Style
Principles are intentionally not machine-scanned.

The linter must produce a uniform ``{"warnings": [...], "extracted_patterns": [...]}``
contract so the ``write_author_discovery`` MCP response stays consistent
with ``append_book_rule``.
"""

from __future__ import annotations

import pytest

from tools.author.discovery_lint import (
    LINT_BOLD_TITLE_UNSCANNABLE,
    LINT_BRACKET_PLACEHOLDER,
    LINT_MIXED_POSITIVE_NEGATIVE_ITALICS,
    LINT_MIXED_POSITIVE_NEGATIVE_QUOTES,
    LINT_SCANNER_EXTRACTS_NOTHING,
    lint_author_discovery,
)


def _codes(result: dict) -> list[str]:
    return [w["code"] for w in result["warnings"]]


# ---------------------------------------------------------------------------
# Don'ts section
# ---------------------------------------------------------------------------


class TestLintDonts:
    """Author Don'ts encode bannable phrases in italics + backticks + quotes."""

    def test_clean_donts_no_warnings(self):
        text = '**Never use rooms as receivers** — *The room received it.*'
        result = lint_author_discovery("donts", text)
        assert result["warnings"] == []
        labels = [p["label"] for p in result["extracted_patterns"]]
        assert "The room received it." in labels

    def test_mixed_italics_with_recommendation_marker_warns(self):
        """Bullet has ban cue + ≥2 italics + a recommendation marker.
        After #217 the post-marker italics silently do NOT extract — the
        user should know so they can verify intent."""
        text = (
            "**Never personify rooms** — *The room received it.* / "
            "*the silence held it.* Render the impact through a named body: "
            "*Caelan's eyes did not move*, *Viktor's hand stilled*."
        )
        result = lint_author_discovery("donts", text)
        assert LINT_MIXED_POSITIVE_NEGATIVE_ITALICS in _codes(result)
        # The bad italics still extract.
        labels = [p["label"] for p in result["extracted_patterns"]]
        assert "The room received it." in labels
        # The post-marker italics do NOT extract.
        assert "Caelan's eyes did not move" not in labels

    def test_mixed_italics_without_marker_no_warning(self):
        """No marker → all italics are treated as bans, no asymmetry to flag."""
        text = (
            "**Never use** — *first banned.* / *second banned.* / *third banned.*"
        )
        result = lint_author_discovery("donts", text)
        assert LINT_MIXED_POSITIVE_NEGATIVE_ITALICS not in _codes(result)

    def test_mixed_quoted_phrases_warns(self):
        """Multiple double-quoted phrases under a ban cue: every quote
        extracts as a banned pattern (unless a recommendation marker gates
        the later ones)."""
        text = 'Never use the phrase "totally landed" or "really landed" in narration.'
        result = lint_author_discovery("donts", text)
        assert LINT_MIXED_POSITIVE_NEGATIVE_QUOTES in _codes(result)

    def test_single_quoted_phrase_no_warning(self):
        text = 'Never use the phrase "totally landed" in narration.'
        result = lint_author_discovery("donts", text)
        assert LINT_MIXED_POSITIVE_NEGATIVE_QUOTES not in _codes(result)

    def test_scanner_extracts_nothing_warns(self):
        """Ban cue but no backtick, no quoted phrase, no italic — scanner
        will see no pattern at all."""
        text = "**Never use weather metaphors** — they are clichéd."
        result = lint_author_discovery("donts", text)
        assert LINT_SCANNER_EXTRACTS_NOTHING in _codes(result)
        assert result["extracted_patterns"] == []

    def test_scanner_extracts_nothing_silent_without_ban_cue(self):
        text = "**Style note** — italics are emphasis only here."
        result = lint_author_discovery("donts", text)
        assert LINT_SCANNER_EXTRACTS_NOTHING not in _codes(result)

    def test_bracket_placeholder_in_backtick_warns(self):
        text = "**Never use** — `\\bnever [verb] the [noun]\\b`"
        result = lint_author_discovery("donts", text)
        assert LINT_BRACKET_PLACEHOLDER in _codes(result)

    def test_clean_backtick_no_warning(self):
        text = "**Never personify rooms** — `\\bthe (room|silence) (received|held)\\b`"
        result = lint_author_discovery("donts", text)
        assert LINT_BRACKET_PLACEHOLDER not in _codes(result)
        assert result["extracted_patterns"], "backtick regex must surface as pattern"


# ---------------------------------------------------------------------------
# Recurring Tics section
# ---------------------------------------------------------------------------


class TestLintRecurringTics:
    """Recurring Tics encode the scannable phrase in the bold title quote,
    optionally fall back to body extraction or title text."""

    def test_quoted_title_no_warning(self):
        text = '**Vague-noun "thing" als Fallback** — concretize on sight.'
        result = lint_author_discovery("recurring_tics", text)
        assert result["warnings"] == []
        labels = [p["label"] for p in result["extracted_patterns"]]
        assert "thing" in labels

    def test_body_quoted_phrase_no_warning(self):
        """German rule-name title + English body phrases is the new
        canonical post-#212 pattern — must not warn."""
        text = (
            '**Abstrakte Körperteil-Anthropomorphisierung** — '
            'Körperteil als Subjekt + vages Prädikat: '
            '"his hands were having a conversation with each other".'
        )
        result = lint_author_discovery("recurring_tics", text)
        assert LINT_BOLD_TITLE_UNSCANNABLE not in _codes(result)
        labels = [p["label"] for p in result["extracted_patterns"]]
        assert "his hands were having a conversation with each other" in labels

    def test_german_title_no_body_pattern_warns(self):
        """German rule-name title with NO body quotes/backticks → title-text
        fallback fires and won't match English chapter prose."""
        text = (
            '**Abstrakte Körperteil-Anthropomorphisierung** — '
            'Körperteil als Subjekt mit vagem Prädikat. Konkretisieren.'
        )
        result = lint_author_discovery("recurring_tics", text)
        assert LINT_BOLD_TITLE_UNSCANNABLE in _codes(result)

    def test_english_title_no_pattern_no_warning(self):
        """English bold-title bullets that ARE the pattern (e.g.
        ``**Opened his mouth. Closed it.**``) must NOT warn — the title-text
        fallback is intentional and works."""
        text = "**Opened his mouth. Closed it.** — vary or skip."
        result = lint_author_discovery("recurring_tics", text)
        assert LINT_BOLD_TITLE_UNSCANNABLE not in _codes(result)

    def test_bracket_placeholder_warns(self):
        text = "**Body part anti-pattern** — `\\b[bodypart] (was|were)\\b`"
        result = lint_author_discovery("recurring_tics", text)
        assert LINT_BRACKET_PLACEHOLDER in _codes(result)


# ---------------------------------------------------------------------------
# Style Principles section
# ---------------------------------------------------------------------------


class TestLintStylePrinciples:
    """Style Principles are not machine-scanned — the linter must not warn
    about scanner gaps. Bracket-placeholder typos still get flagged."""

    def test_clean_style_principle_no_warnings(self):
        text = "**POV-Wissens-Integrität** — kein POV-Charakter macht Fachbehauptungen."
        result = lint_author_discovery("style_principles", text)
        assert result["warnings"] == []

    def test_style_principle_with_ban_cue_does_not_warn_about_scanner_gap(self):
        """Even with a ban cue, style principles aren't scanned — no
        ``scanner_extracts_nothing`` warning."""
        text = "**No purple prose** — avoid lush descriptions."
        result = lint_author_discovery("style_principles", text)
        assert LINT_SCANNER_EXTRACTS_NOTHING not in _codes(result)
        assert LINT_MIXED_POSITIVE_NEGATIVE_ITALICS not in _codes(result)
        assert LINT_MIXED_POSITIVE_NEGATIVE_QUOTES not in _codes(result)
        assert LINT_BOLD_TITLE_UNSCANNABLE not in _codes(result)

    def test_style_principle_bracket_placeholder_still_warns(self):
        text = "**Avoid filler** — see `[noun] of [noun]` for placeholder typo."
        result = lint_author_discovery("style_principles", text)
        assert LINT_BRACKET_PLACEHOLDER in _codes(result)


# ---------------------------------------------------------------------------
# Contract / shape
# ---------------------------------------------------------------------------


class TestLintContract:
    def test_returns_warnings_and_patterns_keys(self):
        result = lint_author_discovery("donts", "**clean** — `\\bfoo\\b`")
        assert "warnings" in result
        assert "extracted_patterns" in result
        assert isinstance(result["warnings"], list)
        assert isinstance(result["extracted_patterns"], list)

    def test_warning_shape(self):
        text = "**Never use weather** — clichéd."
        result = lint_author_discovery("donts", text)
        assert result["warnings"]
        w = result["warnings"][0]
        assert "code" in w
        assert "message" in w
        assert "hint" in w
        assert isinstance(w["code"], str)
        assert isinstance(w["message"], str)
        assert isinstance(w["hint"], str)

    def test_extracted_pattern_shape(self):
        text = "**Never use** — `\\bfoo\\b`"
        result = lint_author_discovery("donts", text)
        assert result["extracted_patterns"]
        p = result["extracted_patterns"][0]
        assert "label" in p
        assert "pattern" in p
        assert "is_regex" in p
        assert isinstance(p["is_regex"], bool)

    def test_unknown_section_raises(self):
        with pytest.raises(ValueError):
            lint_author_discovery("invalid_section", "anything")

    def test_extracted_patterns_match_author_dont_extractor(self):
        """Patterns reported by the lint MUST be the same as what
        ``_extract_patterns_from_author_dont`` would extract — same source
        of truth so the displayed list matches reality."""
        from tools.analysis.manuscript.rules import _extract_patterns_from_author_dont

        text = (
            "**Never personify** — *The room received it.* "
            "Render: *Caelan's eyes did not move.*"
        )
        result = lint_author_discovery("donts", text)
        ground_truth = [label for label, _ in _extract_patterns_from_author_dont(text)]
        lint_labels = [p["label"] for p in result["extracted_patterns"]]
        assert sorted(lint_labels) == sorted(ground_truth)
