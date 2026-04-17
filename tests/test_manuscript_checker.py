"""Tests for the manuscript checker.

Covers:
- Parsing rules out of a book's CLAUDE.md (static entries + RULES:START block).
- Heuristic extraction of scannable patterns from rule text.
- The `_scan_book_rules` pass that turns rule violations into high-severity
  findings with a `source_rule` field pointing back to the offending rule.
- The craft-level scanners: filter words, adverb density, clichés,
  and question-as-statement dialogue punctuation.
- Integration into `scan_repetitions` (the engine, still named that way
  internally because it started as the repetition detector).
"""

from __future__ import annotations

from pathlib import Path

from tools.analysis.manuscript_checker import (
    _extract_patterns_from_rule,
    _read_book_rules,
    _scan_adverb_density,
    _scan_book_rules,
    _scan_cliches,
    _scan_filter_words,
    _scan_question_as_statement,
    _strip_dialogue,
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


# ---------------------------------------------------------------------------
# Helpers: a body of prose long enough for density checks (>=200 words)
# ---------------------------------------------------------------------------


def _prose_body(words: int = 400, filler: str = "the wind moved through the trees") -> str:
    """Generate filler narration of a given word count.

    Uses neutral, non-dialogue prose so density tests only measure the
    keywords we inject manually.
    """
    per = len(filler.split())
    reps = max(1, words // per)
    return " ".join([filler] * reps) + "\n"


# ---------------------------------------------------------------------------
# _strip_dialogue
# ---------------------------------------------------------------------------


class TestStripDialogue:
    def test_removes_straight_quoted_span(self) -> None:
        assert "She felt nothing." not in _strip_dialogue(
            'He said "She felt nothing." and walked on.'
        )

    def test_removes_curly_quoted_span(self) -> None:
        line = "He said \u201CShe felt nothing.\u201D and walked on."
        out = _strip_dialogue(line)
        assert "She felt nothing" not in out

    def test_preserves_narration_outside_quotes(self) -> None:
        line = 'He said "x" and walked on.'
        out = _strip_dialogue(line)
        assert "He said" in out
        assert "walked on" in out

    def test_leaves_line_without_quotes_unchanged(self) -> None:
        line = "He walked home in silence."
        assert _strip_dialogue(line) == line


# ---------------------------------------------------------------------------
# _scan_filter_words
# ---------------------------------------------------------------------------


class TestScanFilterWords:
    def test_flags_chapter_with_high_density(self, tmp_path: Path) -> None:
        # Injected filter words at >6/1k density in 400-word chapter.
        narration = _prose_body(400)
        # Add filter words throughout — ~8 hits in 400 words = 20/1k, high
        narration = narration.replace(
            "the wind moved through the trees",
            "she felt the wind moved through the trees",
            4,
        )
        narration = narration.replace(
            "the wind moved",
            "she noticed the wind moved",
            4,
        )
        chapters = {"01-open": f"# Ch 1\n\n{narration}\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_filter_words(book)
        assert findings, "expected filter_word finding for high-density chapter"
        assert findings[0].category == "filter_word"
        assert findings[0].severity == "high"

    def test_ignores_short_chapters(self, tmp_path: Path) -> None:
        # 30-word chapter — too short to draw conclusions.
        chapters = {"01-open": "# Ch 1\n\nShe felt the wind. She noticed the rain. She felt cold.\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        assert _scan_filter_words(book) == []

    def test_ignores_filter_words_inside_dialogue(self, tmp_path: Path) -> None:
        # All filter words are inside character speech — should not flag.
        dialogue_line = '"I felt it. I noticed. I realized. I saw that too."'
        narration = _prose_body(400) + "\n" + ((dialogue_line + "\n") * 10)
        chapters = {"01-open": f"# Ch 1\n\n{narration}\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        assert _scan_filter_words(book) == []

    def test_clean_chapter_returns_no_findings(self, tmp_path: Path) -> None:
        chapters = {"01-open": f"# Ch 1\n\n{_prose_body(400)}\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        assert _scan_filter_words(book) == []


# ---------------------------------------------------------------------------
# _scan_adverb_density
# ---------------------------------------------------------------------------


class TestScanAdverbDensity:
    def test_flags_heavy_adverb_chapter(self, tmp_path: Path) -> None:
        # Inject ~15 distinct adverbs into 400 words = ~37/1k, high severity.
        adverbs = (
            "quickly slowly quietly loudly softly harshly gently roughly "
            "carefully carelessly suddenly eventually finally barely truly "
        )
        narration = _prose_body(400) + adverbs * 2
        chapters = {"01-open": f"# Ch 1\n\n{narration}\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_adverb_density(book)
        assert findings
        assert findings[0].category == "adverb_density"
        assert findings[0].severity == "high"

    def test_excludes_non_adverb_ly_words(self, tmp_path: Path) -> None:
        # "only", "family", "belly" are in the exclusion list and common.
        bad = "only family belly ugly lovely lonely lively friendly " * 30
        narration = _prose_body(400) + bad
        chapters = {"01-open": f"# Ch 1\n\n{narration}\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        # No genuine adverbs injected → no finding.
        assert _scan_adverb_density(book) == []

    def test_ignores_adverbs_inside_dialogue(self, tmp_path: Path) -> None:
        dialogue_line = '"I quickly, quietly, suddenly, carefully, loudly walked."'
        narration = _prose_body(400) + "\n" + ((dialogue_line + "\n") * 20)
        chapters = {"01-open": f"# Ch 1\n\n{narration}\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        # All adverbs are in quoted speech, should not flag narrator density.
        assert _scan_adverb_density(book) == []

    def test_clean_chapter_returns_no_findings(self, tmp_path: Path) -> None:
        chapters = {"01-open": f"# Ch 1\n\n{_prose_body(400)}\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        assert _scan_adverb_density(book) == []


# ---------------------------------------------------------------------------
# _scan_cliches
# ---------------------------------------------------------------------------


class TestScanCliches:
    def test_detects_single_cliche(self, tmp_path: Path) -> None:
        chapters = {"01-open": "# Ch 1\n\nHer blood ran cold at the sight.\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_cliches(book)
        assert any("blood ran cold" in f.phrase for f in findings)

    def test_detects_multiple_cliches(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": (
                "# Ch 1\n\n"
                "Her heart skipped a beat. Time stood still. "
                "Her eyes widened in horror.\n"
            ),
        }
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_cliches(book)
        phrases = {f.phrase for f in findings}
        assert "heart skipped a beat" in phrases
        assert "time stood still" in phrases
        assert "eyes widened in horror" in phrases

    def test_case_insensitive(self, tmp_path: Path) -> None:
        chapters = {"01-open": "# Ch 1\n\nHer Blood Ran Cold.\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_cliches(book)
        assert findings
        assert findings[0].severity == "high"

    def test_clean_chapter_returns_no_findings(self, tmp_path: Path) -> None:
        chapters = {"01-open": "# Ch 1\n\nShe felt the cold reach her.\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        assert _scan_cliches(book) == []

    def test_counts_multiple_occurrences(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": "# Ch 1\n\nBlood ran cold.\nBlood ran cold again.\n",
            "02-mid": "# Ch 2\n\nHer blood ran cold once more.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_cliches(book)
        cold = next(f for f in findings if "blood ran cold" in f.phrase)
        assert cold.count == 3


# ---------------------------------------------------------------------------
# _scan_question_as_statement
# ---------------------------------------------------------------------------


class TestScanQuestionAsStatement:
    def test_flags_question_word_with_period(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": '# Ch 1\n\nHe stared. "Who did this."\n',
        }
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_question_as_statement(book)
        assert findings
        assert findings[0].category == "question_as_statement"

    def test_ignores_properly_punctuated_question(self, tmp_path: Path) -> None:
        chapters = {"01-open": '# Ch 1\n\n"Who did this?"\n'}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        assert _scan_question_as_statement(book) == []

    def test_ignores_non_interrogative_statement(self, tmp_path: Path) -> None:
        chapters = {"01-open": '# Ch 1\n\n"I went home."\n'}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        assert _scan_question_as_statement(book) == []

    def test_ignores_ellipsis_ending(self, tmp_path: Path) -> None:
        # Ellipsis is trailing-off dialog, not a misplaced period.
        chapters = {"01-open": '# Ch 1\n\n"What..."\n'}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        assert _scan_question_as_statement(book) == []

    def test_severity_high_when_many_hits(self, tmp_path: Path) -> None:
        lines = [f'"Who did this."' for _ in range(6)]
        chapters = {"01-open": "# Ch 1\n\n" + "\n".join(lines) + "\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_question_as_statement(book)
        assert findings[0].severity == "high"
        assert findings[0].count == 6

    def test_severity_medium_when_few_hits(self, tmp_path: Path) -> None:
        chapters = {"01-open": '# Ch 1\n\n"Who."\n"What."\n'}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_question_as_statement(book)
        assert findings[0].severity == "medium"

    def test_detects_aux_verb_questions(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": '# Ch 1\n\n"Did you go."\n"Can you stop."\n"Will he."\n',
        }
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_question_as_statement(book)
        assert findings[0].count >= 3

    def test_detects_curly_quotes(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": "# Ch 1\n\n\u201CWho did this.\u201D\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_question_as_statement(book)
        assert findings


# ---------------------------------------------------------------------------
# Integration: all new categories appear in scan_repetitions output
# ---------------------------------------------------------------------------


class TestScanManuscriptIntegration:
    def test_cliche_appears_in_findings(self, tmp_path: Path) -> None:
        chapters = {"01-open": "# Ch 1\n\nHer blood ran cold.\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        result = scan_repetitions(book)
        categories = {f["category"] for f in result["findings"]}
        assert "cliche" in categories

    def test_question_as_statement_appears_in_findings(self, tmp_path: Path) -> None:
        chapters = {"01-open": '# Ch 1\n\n"Who did this."\n"What now."\n'}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        result = scan_repetitions(book)
        categories = {f["category"] for f in result["findings"]}
        assert "question_as_statement" in categories

    def test_cliches_sort_above_ngrams(self, tmp_path: Path) -> None:
        # Rule violations outrank clichés; clichés outrank everything else.
        chapters = {"01-open": "# Ch 1\n\nHer blood ran cold.\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        result = scan_repetitions(book)
        assert result["findings"]
        assert result["findings"][0]["category"] == "cliche"
