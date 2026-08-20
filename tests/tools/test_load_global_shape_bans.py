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

    def test_11_1_count_and_editorialise_anchoring(self):
        """11.1 must catch spoken/written-unit counts but not plain time/distance counts.

        Regression coverage for a false-positive explosion caught in review: an
        earlier draft of this pattern widened the noun list to include duration
        and movement nouns (day, step, second, breath), which made it match
        ordinary narration ("He had been gone three days.") as well as
        legitimate countdowns ("Twelve seconds."). The fix narrows the noun
        list to units of speech/writing and anchors the count to the start of
        a sentence or dialogue beat.
        """
        plugin_root = Path(__file__).resolve().parent.parent.parent
        patterns = load_global_shape_bans(plugin_root)
        shape_11_1 = next(
            p for p in patterns if "One|Two" in p.label and "word" in p.label
        )

        # Must NOT match: ordinary time/distance/duration narration.
        for text in (
            "He had been gone three days.",
            "She waited five minutes.",
            "The journey took twelve hours.",
            "He crossed the room in four steps.",
            "It was over in ten seconds.",
            "Wait one second.",
            "Twelve seconds.",
            "Two breaths. Three. Then Viktor took two steps.",
        ):
            assert not shape_11_1.pattern.search(text), f"false positive: {text!r}"

        # Must match: the actual AI tell (count-and-editorialise fragment).
        for text in (
            "Two words. Viktor had not used them often in his life.",
            '"Mother is right." Two words. He had not used them often.',
            "Twelve texts. That was what it had taken.",
            "*Two words.* He never said more.",
        ):
            assert shape_11_1.pattern.search(text), f"missed true positive: {text!r}"

        # Must match even right after a chapter heading (write-time-hook path
        # passes raw, unstripped chapter text with no re.MULTILINE handling
        # beyond what the pattern itself declares inline).
        raw_chapter = (
            "# Chapter 25: Instinct\n\n"
            "Twelve seconds.\n\n"
            "He counted them off.\n\n"
            '"Mother is right."\n\n'
            "Two words. Viktor had not used them often.\n"
        )
        matches = [m.group(0) for m in shape_11_1.pattern.finditer(raw_chapter)]
        assert matches == ["Two words."], matches

    def test_11_11_verb_substitution_has_no_automated_regex(self):
        """11.11 (Verb Substitution / "Avoiding Is/Are") is documented as a
        manual-judgment shape, not an automated regex — an earlier draft
        shipped a `**Banned shape:**` regex for it that both missed the tell
        in its dominant past-tense form ("served as") and flagged ordinary
        literal action verbs ("he offers a hand", "the cover features a
        woman in a corset"), verified against real manuscript prose during
        review. It was demoted to manual judgment, matching 11.12/11.13.
        This guards against silently re-adding a regex for it without
        re-doing that false-positive analysis. Checks the whole verb-substitution
        vocabulary, not just "serves as" — a narrower guard checking one verb
        would pass a re-added regex spelled with a different subset (e.g.
        `\b(stands as|marks|represents|boasts)\b`) while defeating the point.
        """
        plugin_root = Path(__file__).resolve().parent.parent.parent
        patterns = load_global_shape_bans(plugin_root)
        verb_substitution_terms = (
            "serves as",
            "stands as",
            "marks a",
            "marks the",
            "represents a",
            "represents the",
            "boasts",
            "features",
            "offers",
        )
        for label in (p.label for p in patterns):
            for term in verb_substitution_terms:
                assert term not in label, (
                    f"verb-substitution term {term!r} found in shape-ban label "
                    f"{label!r} — 11.11 was demoted to manual judgment; re-adding "
                    "a regex for it requires re-doing the false-positive analysis "
                    "in reference/craft/anti-ai-patterns.md §11.11"
                )
