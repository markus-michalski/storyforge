"""Tests for ``append_book_rule(validate=True)`` lint behavior.

Issue follow-up to #145: rule append should run the same lint as
update_book_rule so we don't accept new rules that the manuscript-checker
will silently ignore.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.claudemd import append_book_rule, init_book_claudemd
from tools.claudemd.rules_lint import (
    LINT_ITALIC_EXAMPLES_WITH_BAN_CUE,
    LINT_MIXED_POSITIVE_NEGATIVE_QUOTES,
    LINT_SCANNER_EXTRACTS_NOTHING,
)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def book_config(tmp_path: Path) -> dict:
    content_root = tmp_path / "books"
    book_dir = content_root / "projects" / "my-book"
    book_dir.mkdir(parents=True)
    (book_dir / "README.md").write_text("# My Book\n", encoding="utf-8")
    return {"paths": {"content_root": str(content_root)}}


@pytest.fixture
def initialized_book(
    book_config: dict, monkeypatch: pytest.MonkeyPatch
) -> dict:
    """Initialize CLAUDE.md and patch load_config so MCP tools see the
    test config."""
    monkeypatch.setattr(_app, "load_config", lambda: book_config)
    init_book_claudemd("my-book", book_title="My Book")
    return book_config


class TestAppendBookRuleValidateDefault:
    def test_default_returns_warnings_field(self, initialized_book):
        result = json.loads(append_book_rule("my-book", "Avoid `clocked` as a verb"))
        assert "warnings" in result
        assert isinstance(result["warnings"], list)

    def test_clean_rule_no_warnings(self, initialized_book):
        result = json.loads(append_book_rule("my-book", "Avoid `clocked` as a verb"))
        assert result["warnings"] == []

    def test_extracted_patterns_present_for_scannable_rule(self, initialized_book):
        result = json.loads(append_book_rule("my-book", "Avoid `clocked` as a verb"))
        labels = [p["label"] for p in result["extracted_patterns"]]
        assert "clocked" in labels


class TestAppendBookRuleWarningsForBadRules:
    def test_italic_examples_with_ban_cue_warns(self, initialized_book):
        result = json.loads(
            append_book_rule(
                "my-book",
                'Avoid these phrases: *"clocked"*, *"registered"*',
            )
        )
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_ITALIC_EXAMPLES_WITH_BAN_CUE in codes

    def test_mixed_quotes_warning(self, initialized_book):
        result = json.loads(
            append_book_rule(
                "my-book",
                'Avoid "clocked" — replace with "noticed" or "registered"',
            )
        )
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_MIXED_POSITIVE_NEGATIVE_QUOTES in codes

    def test_scanner_extracts_nothing_warning(self, initialized_book):
        result = json.loads(
            append_book_rule("my-book", "Avoid passive voice constructions")
        )
        codes = [w["code"] for w in result["warnings"]]
        assert LINT_SCANNER_EXTRACTS_NOTHING in codes


class TestAppendStillHappensWithWarnings:
    """Lint warnings are advisory — the rule is still appended."""

    def test_rule_appended_despite_warnings(self, initialized_book):
        result = json.loads(
            append_book_rule(
                "my-book",
                'Avoid these: *"clocked"*, *"registered"*',
            )
        )
        # Append succeeded.
        assert "path" in result
        assert "error" not in result
        # And we got warnings back.
        assert len(result["warnings"]) > 0


class TestValidateFalseSkipsLint:
    def test_validate_false_returns_empty_warnings(self, initialized_book):
        result = json.loads(
            append_book_rule(
                "my-book",
                "Avoid passive voice constructions",
                validate=False,
            )
        )
        assert result["warnings"] == []
        assert result["extracted_patterns"] == []


class TestEnrichedScannerExtractsNothingHint:
    """When a rule has a ban cue but no extractable pattern AND no
    discernible alternative ('use X instead', 'replace with', '→'),
    the hint should call out both gaps explicitly so the user knows
    to add either a backticked phrase OR an alternative."""

    def test_hint_mentions_alternative_when_missing(self, initialized_book):
        result = json.loads(
            append_book_rule(
                "my-book",
                "Avoid passive voice constructions",  # no alternative
            )
        )
        warnings = [
            w for w in result["warnings"] if w["code"] == LINT_SCANNER_EXTRACTS_NOTHING
        ]
        assert warnings
        hint = warnings[0]["hint"].lower()
        assert "alternative" in hint or "instead" in hint or "replace" in hint

    def test_hint_does_not_demand_alternative_when_present(
        self, initialized_book
    ):
        # Rule has 'replace with' — alternative is documented, even though
        # the scanner still can't extract anything. Hint should NOT push for
        # an alternative (that's already there).
        result = json.loads(
            append_book_rule(
                "my-book",
                "Avoid passive voice — replace with active constructions",
            )
        )
        warnings = [
            w for w in result["warnings"] if w["code"] == LINT_SCANNER_EXTRACTS_NOTHING
        ]
        if warnings:
            hint = warnings[0]["hint"].lower()
            # No demand for an alternative — it's already in the rule.
            assert "alternative" not in hint or "backtick" in hint
