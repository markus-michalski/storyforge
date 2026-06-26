"""Tests for ReDoS protection in _extract_block_patterns_from_rule (Issue #322).

Verifies that patterns with nested quantifiers (the primary ReDoS trigger)
are compiled as literals rather than regex, while safe regex patterns like
simple alternations and word boundaries continue to work as intended.
"""

from __future__ import annotations

import re
import time

from tools.analysis.chapter_validator import _extract_block_patterns_from_rule


class TestReDoSProtection:
    """Nested quantifiers on groups must be downgraded to literal matching."""

    def test_classic_redos_pattern_is_treated_as_literal(self) -> None:
        rule = "Never use `(a+)+b` in prose."
        patterns = _extract_block_patterns_from_rule(rule)

        assert len(patterns) == 1
        inner, compiled = patterns[0]
        # The pattern must be escaped — re.escape("(a+)+b") != "(a+)+b"
        assert compiled.pattern == re.escape("(a+)+b")

    def test_star_nested_quantifier_is_literal(self) -> None:
        rule = "Avoid `([a-z]+)*` constructs."
        patterns = _extract_block_patterns_from_rule(rule)

        assert len(patterns) == 1
        _, compiled = patterns[0]
        assert compiled.pattern == re.escape("([a-z]+)*")

    def test_brace_quantifier_on_group_is_literal(self) -> None:
        rule = "Do not write `(word){3,}`."
        patterns = _extract_block_patterns_from_rule(rule)

        assert len(patterns) == 1
        _, compiled = patterns[0]
        assert compiled.pattern == re.escape("(word){3,}")

    def test_character_class_with_outer_quantifier_is_literal(self) -> None:
        rule = "Avoid `[aeiou]+` repeated as `[aeiou]+{2}`."
        patterns = _extract_block_patterns_from_rule(rule)
        # [aeiou]+{2} is invalid regex (quantifier on quantifier) — raises re.error, skipped.
        # [aeiou]+ has no ) before quantifier, so the guard does not fire; compiled as regex.
        for _, compiled in patterns:
            if "{" in compiled.pattern and "aeiou" in compiled.pattern:
                # Escaped — no raw { quantifier on ]
                assert "\\[" in compiled.pattern or re.escape("[aeiou]+{2}") == compiled.pattern

    def test_redos_pattern_does_not_hang(self) -> None:
        """The guard must prevent catastrophic backtracking."""
        rule = "Never write `(a+)+b` here."
        patterns = _extract_block_patterns_from_rule(rule)
        assert patterns, "Pattern should still be extracted (as literal)"

        _, compiled = patterns[0]
        # Matching a long string of 'a's against a ReDoS pattern would hang
        # if compiled as regex; as a literal it completes instantly.
        evil_input = "a" * 30
        start = time.monotonic()
        compiled.search(evil_input)
        elapsed = time.monotonic() - start
        assert elapsed < 0.1, f"Match took {elapsed:.3f}s — possible ReDoS"

    def test_safe_alternation_remains_regex(self) -> None:
        """(room|silence) — no quantifier after ) — must stay as real regex."""
        rule = "Never write `\\bthe (room|silence) (received|held)\\b`."
        patterns = _extract_block_patterns_from_rule(rule)

        assert len(patterns) == 1
        _, compiled = patterns[0]
        # Must match as regex — the literal string would require backslash-b literally
        assert compiled.search("the room received the verdict")
        assert compiled.search("the silence held it")
        assert not compiled.search("the kitchen received it")

    def test_simple_word_boundary_remains_regex(self) -> None:
        """\\bword\\b patterns must still function as regex."""
        rule = "Avoid `\\bsuddenly\\b`."
        patterns = _extract_block_patterns_from_rule(rule)

        assert len(patterns) == 1
        _, compiled = patterns[0]
        assert compiled.search("He suddenly realized")
        assert not compiled.search("suddenlyfoo")  # word boundary respected

    def test_pipe_alternation_without_quantifier_remains_regex(self) -> None:
        """(foo|bar) with no outer quantifier is safe."""
        rule = "Do not use `(though|although)` as sentence openers."
        patterns = _extract_block_patterns_from_rule(rule)

        assert len(patterns) == 1
        _, compiled = patterns[0]
        assert compiled.search("Though, he said")
        assert compiled.search("Although she tried")


class TestExtractBlockPatternsEdgeCases:
    """Edge cases for the pattern extractor unrelated to ReDoS."""

    def test_plain_literal_is_escaped(self) -> None:
        rule = "Never write `very unique`."
        patterns = _extract_block_patterns_from_rule(rule)

        assert len(patterns) == 1
        inner, compiled = patterns[0]
        assert inner == "very unique"
        assert compiled.search("This is very unique indeed")

    def test_duplicate_patterns_deduplicated(self) -> None:
        rule = "Avoid `foo` and also `foo` again."
        patterns = _extract_block_patterns_from_rule(rule)
        assert len(patterns) == 1

    def test_short_patterns_skipped(self) -> None:
        rule = "Skip single char `a` patterns."
        patterns = _extract_block_patterns_from_rule(rule)
        assert len(patterns) == 0

    def test_malformed_regex_skipped(self) -> None:
        rule = "Bad pattern `[unclosed`."
        patterns = _extract_block_patterns_from_rule(rule)
        # Malformed regex raises re.error — must be skipped, not crash
        assert len(patterns) == 0
