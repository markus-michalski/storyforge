"""Tests for ``tools.banlist_loader.load_global_shape_bans`` (Issue #213).

Section 11 of ``reference/craft/anti-ai-patterns.md`` documents the
elegant-abstraction-register patterns as ``**Banned shape:** `regex```
lines. Until this loader, those regexes were reference text only — no
scanner read them, so authors had to manually copy each shape into their
profile's ``### Don'ts`` to get enforcement.

This loader closes the gap: it parses every ``**Banned shape:** \\`...\\```
line from Section 11 and returns ``BannedPattern`` instances with
warn-severity. The hook and manuscript-checker then surface them globally
across all authors.
"""

from __future__ import annotations

from pathlib import Path

from tools.banlist_loader import (
    SEVERITY_WARN,
    load_global_shape_bans,
)


def _write_anti_ai_patterns(plugin_root: Path, body: str) -> None:
    """Write a fake ``reference/craft/anti-ai-patterns.md`` for testing."""
    craft = plugin_root / "reference" / "craft"
    craft.mkdir(parents=True, exist_ok=True)
    (craft / "anti-ai-patterns.md").write_text(body, encoding="utf-8")


class TestLoadGlobalShapeBans:
    def test_returns_empty_when_file_missing(self, tmp_path: Path):
        assert load_global_shape_bans(tmp_path) == []

    def test_returns_empty_when_no_section_11(self, tmp_path: Path):
        _write_anti_ai_patterns(
            tmp_path,
            "## 1. Known AI Tells — Vocabulary\n\nblah blah\n",
        )
        assert load_global_shape_bans(tmp_path) == []

    def test_parses_single_banned_shape(self, tmp_path: Path):
        _write_anti_ai_patterns(
            tmp_path,
            "## 11. Known AI Tells — Elegant Abstraction Register\n\n"
            "### 11.1 Word-Count Meta-Commentary\n\n"
            "Some narrative explanation.\n\n"
            "**Banned shape:** `\\b(One|Two|Three|Four) words?\\.` followed by editorialising.\n",
        )
        patterns = load_global_shape_bans(tmp_path)
        assert len(patterns) == 1
        assert patterns[0].severity == SEVERITY_WARN
        # Pattern is compiled and matches the expected text
        assert patterns[0].pattern.search("Two words. He had not used them often.")
        assert patterns[0].pattern.search("THREE WORDS.")  # case-insensitive

    def test_parses_multiple_banned_shapes(self, tmp_path: Path):
        _write_anti_ai_patterns(
            tmp_path,
            "## 11. Known AI Tells — Elegant Abstraction Register\n\n"
            "### 11.1 X\n\n**Banned shape:** `\\bA\\b`.\n\n"
            "### 11.2 Y\n\n**Banned shape:** `\\bB\\b`.\n\n"
            "### 11.3 Z\n\n**Banned shape:** `\\bC\\b`.\n",
        )
        patterns = load_global_shape_bans(tmp_path)
        assert len(patterns) == 3

    def test_source_attribution(self, tmp_path: Path):
        _write_anti_ai_patterns(
            tmp_path,
            "## 11. Known AI Tells\n\n"
            "**Banned shape:** `\\bfoo\\b`.\n",
        )
        patterns = load_global_shape_bans(tmp_path)
        assert patterns
        assert "section 11" in patterns[0].source.lower()
        assert "anti-ai" in patterns[0].source.lower()

    def test_stops_at_next_top_level_section(self, tmp_path: Path):
        """The loader must not bleed into Section 12 or later."""
        _write_anti_ai_patterns(
            tmp_path,
            "## 11. Section 11\n\n**Banned shape:** `\\bglobal\\b`.\n\n"
            "## 12. Section 12\n\n**Banned shape:** `\\bnot_global\\b`.\n",
        )
        patterns = load_global_shape_bans(tmp_path)
        labels = [p.label for p in patterns]
        # Only the Section 11 pattern is in the result.
        assert any("global" in lab for lab in labels)
        assert not any("not_global" in lab for lab in labels)

    def test_invalid_regex_is_skipped(self, tmp_path: Path):
        _write_anti_ai_patterns(
            tmp_path,
            "## 11. Section 11\n\n"
            "**Banned shape:** `\\bvalid\\b`.\n"
            "**Banned shape:** `[unclosed`.\n"
            "**Banned shape:** `\\balso_valid\\b`.\n",
        )
        patterns = load_global_shape_bans(tmp_path)
        labels = [p.label for p in patterns]
        # Invalid regex is silently skipped; valid ones load.
        assert "\\bvalid\\b" in labels
        assert "\\balso_valid\\b" in labels
        assert not any("[unclosed" in lab for lab in labels)

    def test_real_section_11_patterns_present(self, tmp_path: Path):
        """Smoke test using the real Section 11 from the production catalog."""
        # Use the actual plugin root.
        plugin_root = Path(__file__).resolve().parent.parent.parent
        patterns = load_global_shape_bans(plugin_root)
        # Should load at least 4 shapes (word-count, sentence-projectile,
        # room-as-receiver, economic-metaphor).
        assert len(patterns) >= 4
        # Spot-check: room-as-receiver should be matchable.
        assert any(
            p.pattern.search("The room received it without complaint.")
            for p in patterns
        )
