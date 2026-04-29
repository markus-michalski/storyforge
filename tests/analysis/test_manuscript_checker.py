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
    _load_action_verbs,
    _load_cliche_banlist,
    _read_allowed_repetitions,
    _read_book_genres,
    _read_book_rules,
    _read_snapshot_threshold,
    _scan_adverb_density,
    _scan_book_rules,
    _scan_callbacks,
    _scan_cliches,
    _scan_filter_words,
    _scan_question_as_statement,
    _scan_sentence_repetitions,
    _scan_snapshots,
    _strip_dialogue,
    scan_repetitions,
)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


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
        clocked_finding = next(f for f in findings if "clocked" in f.phrase.lower())
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
        assert "She felt nothing." not in _strip_dialogue('He said "She felt nothing." and walked on.')

    def test_removes_curly_quoted_span(self) -> None:
        line = "He said \u201cShe felt nothing.\u201d and walked on."
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
            "01-open": ("# Ch 1\n\nHer heart skipped a beat. Time stood still. Her eyes widened in horror.\n"),
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
        lines = ['"Who did this."' for _ in range(6)]
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
            "01-open": "# Ch 1\n\n\u201cWho did this.\u201d\n",
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


# ---------------------------------------------------------------------------
# #80 — Cliché banlist: file-based loader
# ---------------------------------------------------------------------------


class TestClicheBanlistLoader:
    def test_real_file_has_minimum_120_phrases(self) -> None:
        phrases = _load_cliche_banlist(PLUGIN_ROOT)
        assert len(phrases) >= 120, f"only {len(phrases)} entries — expected ≥120"

    def test_all_legacy_phrases_still_present(self) -> None:
        phrases = _load_cliche_banlist(PLUGIN_ROOT)
        texts = [p[0] for p in phrases]
        assert "blood ran cold" in texts
        assert "heart skipped a beat" in texts
        assert "time stood still" in texts

    def test_filter_verbs_included(self) -> None:
        phrases = _load_cliche_banlist(PLUGIN_ROOT)
        texts = [p[0] for p in phrases]
        assert "began to" in texts
        assert "started to" in texts

    def test_each_entry_has_severity(self) -> None:
        phrases = _load_cliche_banlist(PLUGIN_ROOT)
        for phrase, severity in phrases:
            assert severity in ("high", "medium"), f"unexpected severity {severity!r} for {phrase!r}"

    def test_missing_file_falls_back_to_legacy_constant(self, tmp_path: Path) -> None:
        phrases = _load_cliche_banlist(tmp_path)
        texts = [p[0] for p in phrases]
        assert "blood ran cold" in texts

    def test_genre_override_adds_phrases(self, tmp_path: Path) -> None:
        ref = tmp_path / "reference" / "craft"
        ref.mkdir(parents=True)
        (ref / "cliche-banlist.md").write_text(
            "## Tired Phrases\n- blood ran cold (severity: high)\n",
            encoding="utf-8",
        )
        (ref / "cliche-banlist-romance.md").write_text(
            "## Romance Additions\n- star-crossed lovers (severity: medium)\n",
            encoding="utf-8",
        )
        phrases = _load_cliche_banlist(tmp_path, genres=["romance"])
        texts = [p[0] for p in phrases]
        assert "blood ran cold" in texts
        assert "star-crossed lovers" in texts

    def test_genre_override_without_base_still_works(self, tmp_path: Path) -> None:
        ref = tmp_path / "reference" / "craft"
        ref.mkdir(parents=True)
        (ref / "cliche-banlist-romance.md").write_text(
            "## Extra\n- hearts entwined (severity: medium)\n",
            encoding="utf-8",
        )
        phrases = _load_cliche_banlist(tmp_path, genres=["romance"])
        texts = [p[0] for p in phrases]
        # Falls back to legacy for base, merges genre override
        assert "blood ran cold" in texts
        assert "hearts entwined" in texts

    def test_multi_genre_merges_all_files(self, tmp_path: Path) -> None:
        ref = tmp_path / "reference" / "craft"
        ref.mkdir(parents=True)
        (ref / "cliche-banlist.md").write_text("## Base\n- blood ran cold (severity: high)\n", encoding="utf-8")
        (ref / "cliche-banlist-romance.md").write_text(
            "## Romance\n- star-crossed lovers (severity: medium)\n", encoding="utf-8"
        )
        (ref / "cliche-banlist-sci-fi.md").write_text(
            "## Sci-Fi\n- as you know bob (severity: high)\n", encoding="utf-8"
        )
        phrases = _load_cliche_banlist(tmp_path, genres=["romance", "sci-fi"])
        texts = [p[0] for p in phrases]
        assert "blood ran cold" in texts
        assert "star-crossed lovers" in texts
        assert "as you know bob" in texts

    def test_unknown_genre_silently_skipped(self, tmp_path: Path) -> None:
        ref = tmp_path / "reference" / "craft"
        ref.mkdir(parents=True)
        (ref / "cliche-banlist.md").write_text("## Base\n- blood ran cold (severity: high)\n", encoding="utf-8")
        # No cliche-banlist-nonexistent.md — should not raise
        phrases = _load_cliche_banlist(tmp_path, genres=["nonexistent"])
        assert any(p[0] == "blood ran cold" for p in phrases)

    def test_no_genre_deduplication_across_files(self, tmp_path: Path) -> None:
        ref = tmp_path / "reference" / "craft"
        ref.mkdir(parents=True)
        (ref / "cliche-banlist.md").write_text("## Base\n- blood ran cold (severity: high)\n", encoding="utf-8")
        (ref / "cliche-banlist-romance.md").write_text(
            "## Romance\n- blood ran cold (severity: high)\n", encoding="utf-8"
        )
        phrases = _load_cliche_banlist(tmp_path, genres=["romance"])
        texts = [p[0] for p in phrases]
        assert texts.count("blood ran cold") == 1

    def test_scan_cliches_detects_filter_verb_from_file(self, tmp_path: Path) -> None:
        chapters = {"01-open": "# Ch 1\n\nShe began to walk toward the door.\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_cliches(book)
        assert any("began to" in f.phrase for f in findings), "expected 'began to' from file-loaded banlist"

    def test_scan_cliches_severity_respected(self, tmp_path: Path) -> None:
        ref = tmp_path / "reference" / "craft"
        ref.mkdir(parents=True)
        (ref / "cliche-banlist.md").write_text(
            "## Test\n- seemed to (severity: medium)\n- blood ran cold (severity: high)\n",
            encoding="utf-8",
        )
        chapters = {
            "01-open": "# Ch 1\n\nHer blood ran cold. She seemed to hesitate.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_cliches(book, plugin_root=tmp_path)
        sev = {f.phrase: f.severity for f in findings}
        assert sev.get("blood ran cold") == "high"
        assert sev.get("seemed to") == "medium"


# ---------------------------------------------------------------------------
# _read_book_genres
# ---------------------------------------------------------------------------


def _write_readme(book: Path, genres_line: str) -> None:
    """Write a minimal book README.md with YAML frontmatter."""
    (book / "README.md").write_text(
        f"---\ntitle: Test\n{genres_line}\n---\n\n# Test\n",
        encoding="utf-8",
    )


class TestReadBookGenres:
    def test_parses_inline_list(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, {})
        _write_readme(book, 'genres: ["romance", "sci-fi"]')
        assert _read_book_genres(book) == ["romance", "sci-fi"]

    def test_parses_block_list(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, {})
        _write_readme(book, "genres:\n  - thriller\n  - horror")
        assert _read_book_genres(book) == ["thriller", "horror"]

    def test_parses_single_quoted(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, {})
        _write_readme(book, "genres: ['fantasy']")
        assert _read_book_genres(book) == ["fantasy"]

    def test_empty_list_returns_empty(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, {})
        _write_readme(book, "genres: []")
        assert _read_book_genres(book) == []

    def test_missing_readme_returns_empty(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, {})
        assert _read_book_genres(book) == []

    def test_missing_genres_field_returns_empty(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, {})
        _write_readme(book, "title: Test")
        assert _read_book_genres(book) == []

    def test_scan_repetitions_auto_detects_genres(self, tmp_path: Path) -> None:
        # Integration: genre phrases loaded automatically from README genres field
        ref = tmp_path / "reference" / "craft"
        ref.mkdir(parents=True)
        (ref / "cliche-banlist.md").write_text("## Base\n- blood ran cold (severity: high)\n", encoding="utf-8")
        (ref / "cliche-banlist-thriller.md").write_text(
            "## Thriller\n- adrenaline surged (severity: high)\n", encoding="utf-8"
        )
        book = tmp_path / "book"
        book.mkdir()
        (book / "CLAUDE.md").write_text(CLAUDEMD_EMPTY_RULES, encoding="utf-8")
        _write_readme(book, 'genres: ["thriller"]')
        chapters_dir = book / "chapters" / "01-open"
        chapters_dir.mkdir(parents=True)
        (chapters_dir / "draft.md").write_text("# Ch 1\n\nAdrenaline surged through her veins.\n", encoding="utf-8")
        result = scan_repetitions(book, plugin_root=ref.parent.parent)
        categories_phrases = [f["phrase"] for f in result["findings"]]
        assert any("adrenaline surged" in p for p in categories_phrases)


# ---------------------------------------------------------------------------
# #82 — Sentence-level repetition detector (8-15 word n-grams)
# ---------------------------------------------------------------------------

_LONG_REPEATED = "his heart hammered against his ribs as he forced himself to breathe"


class TestScanSentenceRepetitions:
    def test_detects_12_word_phrase_across_two_chapters(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": f"# Ch 1\n\n{_LONG_REPEATED.capitalize()}.\n",
            "02-mid": f"# Ch 2\n\n{_LONG_REPEATED.capitalize()} again.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_sentence_repetitions(book)
        assert findings, "expected sentence_repetition finding"
        all_phrases = " ".join(f.phrase for f in findings)
        assert "heart hammered against his ribs" in all_phrases

    def test_short_phrase_not_caught_by_sentence_detector(self, tmp_path: Path) -> None:
        # 5-word phrase — below 8-word minimum
        short = "the wind moved through trees"
        chapters = {
            "01-open": f"# Ch 1\n\n{short}.\n",
            "02-mid": f"# Ch 2\n\n{short}.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_sentence_repetitions(book)
        assert all("wind moved through" not in f.phrase for f in findings)

    def test_single_occurrence_not_flagged(self, tmp_path: Path) -> None:
        chapters = {"01-open": f"# Ch 1\n\n{_LONG_REPEATED.capitalize()}.\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        assert _scan_sentence_repetitions(book) == []

    def test_category_is_sentence_repetition(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": f"# Ch 1\n\n{_LONG_REPEATED.capitalize()}.\n",
            "02-mid": f"# Ch 2\n\n{_LONG_REPEATED.capitalize()} softly.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_sentence_repetitions(book)
        assert findings
        assert all(f.category == "sentence_repetition" for f in findings)

    def test_severity_is_always_high(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": f"# Ch 1\n\n{_LONG_REPEATED.capitalize()}.\n",
            "02-mid": f"# Ch 2\n\n{_LONG_REPEATED.capitalize()} again.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_sentence_repetitions(book)
        assert findings
        assert all(f.severity == "high" for f in findings)

    def test_allowed_repetitions_excluded(self, tmp_path: Path) -> None:
        claudemd = CLAUDEMD_EMPTY_RULES + f"\n## Allowed Repetitions\n- {_LONG_REPEATED}\n"
        chapters = {
            "01-open": f"# Ch 1\n\n{_LONG_REPEATED.capitalize()}.\n",
            "02-mid": f"# Ch 2\n\n{_LONG_REPEATED.capitalize()} softly.\n",
        }
        book = _write_book(tmp_path, claudemd, chapters)
        findings = _scan_sentence_repetitions(book)
        assert all("heart hammered against his ribs" not in f.phrase for f in findings)

    def test_sentence_repetition_in_scan_repetitions_result(self, tmp_path: Path) -> None:
        chapters = {
            "01-open": f"# Ch 1\n\n{_LONG_REPEATED.capitalize()}.\n",
            "02-mid": f"# Ch 2\n\n{_LONG_REPEATED.capitalize()} again.\n",
        }
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        result = scan_repetitions(book)
        categories = {f["category"] for f in result["findings"]}
        assert "sentence_repetition" in categories


class TestReadAllowedRepetitions:
    def test_parses_allowed_section(self, tmp_path: Path) -> None:
        claudemd = "# Book\n\n## Allowed Repetitions\n- his heart hammered against his ribs\n- the way the light fell\n"
        book = _write_book(tmp_path, claudemd, {})
        allowed = _read_allowed_repetitions(book)
        assert "his heart hammered against his ribs" in allowed
        assert "the way the light fell" in allowed

    def test_missing_section_returns_empty(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, {})
        assert _read_allowed_repetitions(book) == frozenset()

    def test_missing_claudemd_returns_empty(self, tmp_path: Path) -> None:
        book = tmp_path / "book"
        book.mkdir()
        assert _read_allowed_repetitions(book) == frozenset()


# ---------------------------------------------------------------------------
# #81 — Snapshot detector (static description blocks without movement)
# ---------------------------------------------------------------------------

# 7 sentences, all descriptive — no action verbs, no dialog
_SNAPSHOT_BLOCK = (
    "The room was warm. "
    "The fire burned low in the grate. "
    "Ash drifted up and settled on the mantelpiece. "
    "The curtains were heavy velvet, deep burgundy. "
    "A single lamp cast yellow light across the rug. "
    "Dust motes hung in the air near the window. "
    "The walls were lined with bookshelves, floor to ceiling."
)

# 4 sentences — below default threshold of 5
_SHORT_BLOCK = (
    "The room was warm. "
    "The fire burned low in the grate. "
    "Ash drifted up and settled on the mantelpiece. "
    "The curtains were heavy velvet, deep burgundy."
)


class TestScanSnapshots:
    def test_detects_7_sentence_description_block(self, tmp_path: Path) -> None:
        chapters = {"01-open": f"# Ch 1\n\n{_SNAPSHOT_BLOCK}\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_snapshots(book)
        assert findings, "expected snapshot finding for 7-sentence description block"
        assert findings[0].category == "snapshot"

    def test_ignores_4_sentence_block_below_threshold(self, tmp_path: Path) -> None:
        chapters = {"01-open": f"# Ch 1\n\n{_SHORT_BLOCK}\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        assert _scan_snapshots(book) == []

    def test_action_verb_breaks_block(self, tmp_path: Path) -> None:
        # 3 descriptive + 1 action + 3 descriptive = two 3-sentence blocks, neither ≥ 5
        action_break = (
            "The room was warm. "
            "The fire burned low. "
            "Ash drifted up. "
            "He walked to the window. "  # action verb → resets counter
            "The curtains were heavy velvet. "
            "Dust motes hung in the air. "
            "The walls were lined with bookshelves."
        )
        chapters = {"01-open": f"# Ch 1\n\n{action_break}\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        assert _scan_snapshots(book) == []

    def test_dialog_breaks_block(self, tmp_path: Path) -> None:
        dialog_break = (
            "The room was warm. "
            "The fire burned low. "
            "Ash drifted up. "
            '"It is rather cold tonight," she said. '  # dialog → resets counter
            "The curtains were heavy velvet. "
            "Dust motes hung in the air. "
            "The walls were lined with bookshelves."
        )
        chapters = {"01-open": f"# Ch 1\n\n{dialog_break}\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        assert _scan_snapshots(book) == []

    def test_per_book_threshold_respected(self, tmp_path: Path) -> None:
        # Default threshold = 5; set to 8 → 7 sentences should NOT flag
        claudemd = CLAUDEMD_EMPTY_RULES + "\n## Linter Config\n- snapshot_threshold: 8\n"
        chapters = {"01-open": f"# Ch 1\n\n{_SNAPSHOT_BLOCK}\n"}
        book = _write_book(tmp_path, claudemd, chapters)
        assert _scan_snapshots(book) == []

    def test_threshold_8_flags_9_sentence_block(self, tmp_path: Path) -> None:
        claudemd = CLAUDEMD_EMPTY_RULES + "\n## Linter Config\n- snapshot_threshold: 8\n"
        long_block = _SNAPSHOT_BLOCK + " The clock ticked on the mantle. The hour was late."
        chapters = {"01-open": f"# Ch 1\n\n{long_block}\n"}
        book = _write_book(tmp_path, claudemd, chapters)
        findings = _scan_snapshots(book)
        assert findings, "expected finding for 9-sentence block with threshold 8"

    def test_severity_is_medium(self, tmp_path: Path) -> None:
        chapters = {"01-open": f"# Ch 1\n\n{_SNAPSHOT_BLOCK}\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_snapshots(book)
        assert findings
        assert all(f.severity == "medium" for f in findings)

    def test_occurrence_records_chapter_and_line(self, tmp_path: Path) -> None:
        chapters = {"01-open": f"# Ch 1\n\n{_SNAPSHOT_BLOCK}\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        findings = _scan_snapshots(book)
        assert findings
        occ = findings[0].occurrences[0]
        assert occ.chapter == "01-open"
        assert occ.line >= 1

    def test_snapshot_appears_in_scan_repetitions(self, tmp_path: Path) -> None:
        chapters = {"01-open": f"# Ch 1\n\n{_SNAPSHOT_BLOCK}\n"}
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, chapters)
        result = scan_repetitions(book)
        categories = {f["category"] for f in result["findings"]}
        assert "snapshot" in categories

    def test_empty_chapters_no_findings(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, {})
        assert _scan_snapshots(book) == []


class TestReadSnapshotThreshold:
    def test_default_is_5(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, {})
        assert _read_snapshot_threshold(book) == 5

    def test_parses_custom_threshold(self, tmp_path: Path) -> None:
        claudemd = CLAUDEMD_EMPTY_RULES + "\n## Linter Config\n- snapshot_threshold: 8\n"
        book = _write_book(tmp_path, claudemd, {})
        assert _read_snapshot_threshold(book) == 8

    def test_missing_claudemd_returns_default(self, tmp_path: Path) -> None:
        book = tmp_path / "book"
        book.mkdir()
        assert _read_snapshot_threshold(book) == 5


class TestLoadActionVerbs:
    def test_real_file_loads_entries(self) -> None:
        verbs = _load_action_verbs(PLUGIN_ROOT)
        assert len(verbs) >= 50, f"only {len(verbs)} verbs — expected ≥50"

    def test_common_verbs_present(self) -> None:
        verbs = _load_action_verbs(PLUGIN_ROOT)
        assert "walk" in verbs
        assert "run" in verbs
        assert "reach" in verbs

    def test_missing_file_returns_fallback(self, tmp_path: Path) -> None:
        verbs = _load_action_verbs(tmp_path)
        # Should still return non-empty fallback set
        assert len(verbs) >= 20


# ---------------------------------------------------------------------------
# TestScanCallbacksIntegration
# ---------------------------------------------------------------------------

_CLAUDEMD_WITH_CALLBACKS = """\
# My Book

## Callback Register

<!-- CALLBACKS:START -->
- **Theo's watch** — expected return by Ch 5. _(added 2026-01-01)_
<!-- CALLBACKS:END -->
"""

_CLAUDEMD_LONG_SILENCE = """\
# My Book

## Callback Register

<!-- CALLBACKS:START -->
- **the silver ring** _(must not be forgotten)_ _(added 2026-01-01)_
<!-- CALLBACKS:END -->
"""


class TestScanCallbacksIntegration:
    def test_no_claudemd_returns_empty(self, tmp_path: Path) -> None:
        book = tmp_path / "book"
        book.mkdir()
        (book / "chapters").mkdir()
        assert _scan_callbacks(book) == []

    def test_no_callbacks_markers_returns_empty(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, CLAUDEMD_EMPTY_RULES, {"01": "Some text."})
        assert _scan_callbacks(book) == []

    def test_overdue_expected_return_is_high_severity(self, tmp_path: Path) -> None:
        chapters = {
            "01-ch": "She walked down the corridor.",
            "06-ch": "Rain fell outside the window.",
            "10-ch": "The final chapter arrived.",
        }
        book = _write_book(tmp_path, _CLAUDEMD_WITH_CALLBACKS, chapters)
        findings = _scan_callbacks(book)
        assert len(findings) == 1
        f = findings[0]
        assert f.category == "callback_dropped"
        assert f.severity == "high"
        assert "Theo" in f.phrase or "watch" in f.phrase

    def test_recent_deferred_below_threshold_no_finding(self, tmp_path: Path) -> None:
        claudemd = """\
# My Book

## Callback Register

<!-- CALLBACKS:START -->
- **the blue notebook** _(added 2026-01-01)_
<!-- CALLBACKS:END -->
"""
        # Only 3 chapters: chapters_since <= 10 → no finding
        chapters = {
            "01-ch": "She sat by the fire.",
            "02-ch": "Morning arrived.",
            "03-ch": "The rain continued.",
        }
        book = _write_book(tmp_path, claudemd, chapters)
        findings = _scan_callbacks(book)
        assert findings == []

    def test_scan_repetitions_includes_callback_findings(self, tmp_path: Path) -> None:
        chapters = {
            "01-ch": "She walked away without looking back.",
            "06-ch": "The sun set over the valley.",
            "10-ch": "Night fell at last.",
        }
        book = _write_book(tmp_path, _CLAUDEMD_WITH_CALLBACKS, chapters)
        result = scan_repetitions(book)
        categories = {f["category"] for f in result["findings"]}
        assert "callback_dropped" in categories
