"""Tests for the manuscript-checker author-profile rule scanner (Issue #210).

The scanner mirrors ``_scan_book_rules`` but reads Don't-rules from the
resolved author's ``donts``-type rows in the ``author_discoveries`` SQLite
table (Issue #604 — previously read directly from
``~/.storyforge/authors/{slug}/profile.md ## Writing Discoveries /
### Don'ts``, which went stale relative to the DB) instead of the book's
``CLAUDE.md``.

Without this scanner, banned shapes declared at author scope (e.g. the
elegant-abstraction register patterns from PR #209) had to be duplicated
into every book's ``CLAUDE.md`` to be scannable — violating single-source-
of-truth and making author-level enforcement brittle.

Also exercises ``_extract_patterns_from_author_dont`` which adds italic
extraction on top of the book-rule extractor (italics in Don'ts encode
example phrases that should be treated as patterns when a ban cue is
present).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.analysis.manuscript.rules import (
    _extract_patterns_from_author_dont,
    _read_author_rules,
    _scan_author_rules,
)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def patch_storyforge_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``Path.home()/.storyforge`` to a fake home rooted in tmp_path."""
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    return fake_home / ".storyforge"


def _write_book(
    tmp_path: Path,
    *,
    author_line: str = "- **Author:** Ethan Cole",
    chapters: dict[str, str],
) -> Path:
    """Create a minimal book layout with an Author line so the scanner can
    resolve the author slug and load the profile."""
    book = tmp_path / "book"
    book.mkdir()
    (book / "CLAUDE.md").write_text(
        f"# Test Book\n\n## Book Facts\n\n{author_line}\n\n## Rules\n",
        encoding="utf-8",
    )
    chapters_dir = book / "chapters"
    chapters_dir.mkdir()
    for slug, content in chapters.items():
        d = chapters_dir / slug
        d.mkdir()
        (d / "draft.md").write_text(content, encoding="utf-8")
    return book


# ---------------------------------------------------------------------------
# _extract_patterns_from_author_dont
# ---------------------------------------------------------------------------


class TestExtractPatternsFromAuthorDont:
    """Don't-rule extractor: backticks + quoted (with cue) + italics (with cue)."""

    def test_extracts_backtick_regex(self):
        rule = r"**Never use room-as-receiver** — `\bthe (room|silence) (received|held)\b`"
        patterns = _extract_patterns_from_author_dont(rule)
        assert patterns
        labels = [label for label, _ in patterns]
        assert any("room|silence" in lab for lab in labels)

    def test_extracts_italic_phrase_with_ban_cue(self):
        rule = '**Never use word-count meta-commentary** — *Two words.* / *One word.*'
        patterns = _extract_patterns_from_author_dont(rule)
        assert patterns
        labels = [label for label, _ in patterns]
        assert "Two words." in labels
        assert "One word." in labels

    def test_ignores_italics_without_ban_cue(self):
        rule = "Style note — sometimes *italics* are just emphasis."
        patterns = _extract_patterns_from_author_dont(rule)
        # No ban cue → italics treated as narrative emphasis, not bannable.
        assert not patterns

    def test_does_not_match_bold_text_as_italic(self):
        # Ban cue ("Never") gates italic extraction — verifies that under the
        # cue, only the italic span is picked, NOT the bold title text.
        rule = '**Never use the bold title** — *Real italic phrase.* and more'
        patterns = _extract_patterns_from_author_dont(rule)
        labels = [label for label, _ in patterns]
        assert "Never use the bold title" not in labels
        assert "Real italic phrase." in labels

    def test_extracts_quoted_phrase_with_ban_cue(self):
        # Inherits quoted-phrase behavior from `_extract_patterns_from_rule`.
        rule = 'Never use the phrase "totally landed" in narration.'
        patterns = _extract_patterns_from_author_dont(rule)
        labels = [label for label, _ in patterns]
        assert "totally landed" in labels

    def test_skips_short_italic_phrases(self):
        # Single-char or near-single-char italic content is noise.
        rule = "**Never use** — *a* / *ok*"
        patterns = _extract_patterns_from_author_dont(rule)
        # Both *a* (1 char) and *ok* (2 chars, below the min-len threshold) are skipped.
        assert not patterns

    def test_compiled_pattern_matches_case_insensitively(self):
        rule = "**Never use** — *The Room Received It.*"
        patterns = _extract_patterns_from_author_dont(rule)
        assert patterns
        _label, pattern = patterns[0]
        assert pattern.search("the room received it.")
        assert pattern.search("The Room Received It.")


# ---------------------------------------------------------------------------
# _extract_patterns_from_author_dont — recommendation-marker boundary (Issue #217)
# ---------------------------------------------------------------------------


class TestRecommendationMarkerBoundary:
    """A bullet may carry both bad italic examples (to ban) and good italic
    examples (the recommended replacement). The extractor must stop italic /
    quoted extraction at the first 'recommendation marker' (``Render``,
    ``Instead:``, ``→``, ...) so positive examples never end up as banned
    patterns. Backticks always extract regardless of position because they
    encode explicit ban intent.
    """

    def test_render_marker_blocks_following_italics(self):
        rule = (
            "**Never personify rooms** — *The room received it.* / "
            "*the silence held it.* Render the impact through a named body: "
            "*Caelan's eyes did not move*, *Viktor's hand stilled*."
        )
        labels = [lab for lab, _ in _extract_patterns_from_author_dont(rule)]
        assert "The room received it." in labels
        assert "the silence held it." in labels
        assert "Caelan's eyes did not move" not in labels
        assert "Viktor's hand stilled" not in labels

    def test_instead_colon_marker_blocks_following_italics(self):
        rule = (
            "**Never use** — *bad phrase one.* / *bad phrase two.* "
            "Instead: *good phrase one.* / *good phrase two.*"
        )
        labels = [lab for lab, _ in _extract_patterns_from_author_dont(rule)]
        assert "bad phrase one." in labels
        assert "bad phrase two." in labels
        assert "good phrase one." not in labels
        assert "good phrase two." not in labels

    def test_arrow_marker_blocks_following_italics(self):
        rule = "**Never use** — *the old way.* → *the new way.*"
        labels = [lab for lab, _ in _extract_patterns_from_author_dont(rule)]
        assert "the old way." in labels
        assert "the new way." not in labels

    def test_replace_marker_blocks_following_italics(self):
        rule = "**Avoid** — *clunky phrasing.* Replace with *clean phrasing.*"
        labels = [lab for lab, _ in _extract_patterns_from_author_dont(rule)]
        assert "clunky phrasing." in labels
        assert "clean phrasing." not in labels

    def test_rather_colon_marker_blocks_following_italics(self):
        rule = "**Never** — *flat note.* Rather: *living note.*"
        labels = [lab for lab, _ in _extract_patterns_from_author_dont(rule)]
        assert "flat note." in labels
        assert "living note." not in labels

    def test_use_instead_marker_blocks_following_italics(self):
        rule = "**Don't use** — *passive voice example.* Use instead *active phrasing.*"
        labels = [lab for lab, _ in _extract_patterns_from_author_dont(rule)]
        assert "passive voice example." in labels
        assert "active phrasing." not in labels

    def test_marker_is_case_insensitive(self):
        rule = "**Never use** — *bad one.* INSTEAD: *good one.*"
        labels = [lab for lab, _ in _extract_patterns_from_author_dont(rule)]
        assert "bad one." in labels
        assert "good one." not in labels

    def test_no_marker_extracts_all_italics_status_quo(self):
        """Bullet without any recommendation marker — behavior unchanged from
        the pre-#217 status quo: every italic phrase under a ban cue is
        extracted. Recurring Tics rules and old-style bullets must keep working.
        """
        rule = "**Never use** — *first banned.* / *second banned.* / *third banned.*"
        labels = [lab for lab, _ in _extract_patterns_from_author_dont(rule)]
        assert "first banned." in labels
        assert "second banned." in labels
        assert "third banned." in labels

    def test_backtick_after_marker_still_extracts(self):
        """Backticks encode explicit ban intent. They must extract regardless
        of where they sit relative to the recommendation marker — backticks
        after ``Instead:`` are still ban patterns (the author chose to escalate
        them to backticks).
        """
        rule = (
            "**Never** — *bad italic.* Instead: *good italic.* "
            "Also banned: `\\bexplicit regex\\b`"
        )
        patterns = _extract_patterns_from_author_dont(rule)
        labels = [lab for lab, _ in patterns]
        assert "bad italic." in labels
        assert "good italic." not in labels
        assert any("explicit regex" in lab for lab in labels)

    def test_quoted_phrase_after_marker_is_not_extracted(self):
        """Quoted phrases follow the same gate as italics — they are bannable
        examples only when they sit inside the ban window.
        """
        rule = (
            'Never use the phrase "bad quoted phrase" in narration. '
            'Instead: "good quoted phrase" works better.'
        )
        labels = [lab for lab, _ in _extract_patterns_from_author_dont(rule)]
        assert "bad quoted phrase" in labels
        assert "good quoted phrase" not in labels

    def test_marker_inside_word_does_not_trigger(self):
        """``Render`` must match as a word, not as a substring inside another
        word. A bullet body containing e.g. ``rerendered`` must not be
        misread as a recommendation marker.
        """
        rule = "**Never use** — *render method calls.* / *rerendered output.*"
        labels = [lab for lab, _ in _extract_patterns_from_author_dont(rule)]
        # No real recommendation marker — both italics extract.
        assert "render method calls." in labels
        assert "rerendered output." in labels


# ---------------------------------------------------------------------------
# _read_author_rules — DB-backed since Issue #604 (was: profile.md file)
# ---------------------------------------------------------------------------


class TestReadAuthorRules:
    def test_reads_donts_rows(self, tmp_path, patch_storyforge_home, seed_author_discoveries):
        book = _write_book(tmp_path, chapters={"01": "# Ch\n\nbody\n"})
        seed_author_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            "donts",
            [
                "**Never use word-count meta-commentary** — *Two words.* "
                "narrator must not count.",
                "**Never personify rooms** — `\\bthe (room|silence) "
                "(received|held)\\b`",
            ],
        )
        rules = _read_author_rules(book)
        assert len(rules) == 2
        assert any("word-count meta-commentary" in r for r in rules)
        assert any("personify rooms" in r for r in rules)

    def test_empty_when_no_author(self, tmp_path, patch_storyforge_home, seed_author_discoveries):
        book = _write_book(
            tmp_path,
            author_line="- **Genre:** test",
            chapters={"01": "# Ch\n\nbody\n"},
        )
        seed_author_discoveries(
            patch_storyforge_home, "ethan-cole", "donts", ["**Never** — *forbidden phrase.*"],
        )
        assert _read_author_rules(book) == []

    def test_empty_when_no_discoveries_db(self, tmp_path, patch_storyforge_home):
        book = _write_book(tmp_path, chapters={"01": "# Ch\n\nbody\n"})
        # No DB seeded at all.
        assert _read_author_rules(book) == []

    def test_empty_when_no_donts_rows(self, tmp_path, patch_storyforge_home, seed_author_discoveries):
        book = _write_book(tmp_path, chapters={"01": "# Ch\n\nbody\n"})
        seed_author_discoveries(
            patch_storyforge_home, "ethan-cole", "recurring_tics", ["**Vague-noun** — concretize."],
        )
        # Author has recurring_tics but no donts rows.
        assert _read_author_rules(book) == []

    def test_does_not_leak_recurring_tics_into_donts(self, tmp_path, patch_storyforge_home, seed_author_discoveries):
        """Both discovery types coexist; reader must only pick up donts rows."""
        book = _write_book(tmp_path, chapters={"01": "# Ch\n\nbody\n"})
        seed_author_discoveries(
            patch_storyforge_home, "ethan-cole", "recurring_tics",
            ["**\"thing\" als Fallback** — concretize."],
        )
        seed_author_discoveries(
            patch_storyforge_home, "ethan-cole", "donts",
            ["**Never use rooms as receivers** — *The room received it.*"],
        )
        rules = _read_author_rules(book)
        # Only the donts row must be returned.
        assert len(rules) == 1
        assert "rooms as receivers" in rules[0]
        assert "thing" not in rules[0]

    def test_reads_rows_from_a_second_promotion_batch(self, tmp_path, patch_storyforge_home, seed_author_discoveries):
        """Regression for a bug the file-based reader had: a book with two
        Don'ts entries promoted separately (e.g. under differently-worded
        profile.md subsections, like a later '### Don'ts (beyond banned
        phrases)') both surface — the DB has no per-subsection blind spot
        since every row is just discovery_type='donts' (Issue #604)."""
        book = _write_book(tmp_path, chapters={"01": "# Ch\n\nbody\n"})
        seed_author_discoveries(
            patch_storyforge_home, "ethan-cole", "donts",
            [
                "**Never use rooms** — *The room received it.*",
                "**Never announce the armor cracking** — *he realized he meant it.*",
            ],
        )
        rules = _read_author_rules(book)
        assert len(rules) == 2
        assert any("rooms" in r for r in rules)
        assert any("armor cracking" in r for r in rules)


# ---------------------------------------------------------------------------
# _scan_author_rules
# ---------------------------------------------------------------------------


class TestScanAuthorRules:
    def test_finds_italic_pattern_violation(self, tmp_path, patch_storyforge_home, seed_author_discoveries):
        book = _write_book(
            tmp_path,
            chapters={
                "01-open": "# Chapter 1\n\nThe room received it without complaint.\n",
            },
        )
        seed_author_discoveries(
            patch_storyforge_home, "ethan-cole", "donts",
            ["**Never use rooms as receivers** — *The room received it.*"],
        )
        findings = _scan_author_rules(book)
        assert findings, "expected violation for 'the room received it'"
        assert all(f.category == "author_rule_violation" for f in findings)

    def test_finds_backtick_regex_violation(self, tmp_path, patch_storyforge_home, seed_author_discoveries):
        book = _write_book(
            tmp_path,
            chapters={
                "01-open": "# Chapter 1\n\nThe silence received the line.\n",
            },
        )
        seed_author_discoveries(
            patch_storyforge_home, "ethan-cole", "donts",
            [
                "**Never personify rooms** — `\\bthe (room|silence) "
                "(received|held)\\b`",
            ],
        )
        findings = _scan_author_rules(book)
        assert findings
        assert all(f.category == "author_rule_violation" for f in findings)

    def test_severity_high(self, tmp_path, patch_storyforge_home, seed_author_discoveries):
        book = _write_book(
            tmp_path,
            chapters={
                "01-open": "# Chapter 1\n\nThe room received it.\n",
            },
        )
        seed_author_discoveries(
            patch_storyforge_home, "ethan-cole", "donts",
            ["**Never use rooms** — *The room received it.*"],
        )
        findings = _scan_author_rules(book)
        assert findings
        assert all(f.severity == "high" for f in findings)

    def test_source_rule_attributes_to_author_profile(self, tmp_path, patch_storyforge_home, seed_author_discoveries):
        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nThe room received it.\n"},
        )
        seed_author_discoveries(
            patch_storyforge_home, "ethan-cole", "donts",
            ["**Never use rooms** — *The room received it.*"],
        )
        findings = _scan_author_rules(book)
        assert findings
        source = findings[0].source_rule or ""
        # Must point at the author profile section + carry the author slug.
        assert "don't" in source.lower() or "donts" in source.lower()
        assert "ethan-cole" in source.lower()

    def test_no_violations_returns_empty(self, tmp_path, patch_storyforge_home, seed_author_discoveries):
        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nClean prose with no banned shapes.\n"},
        )
        seed_author_discoveries(
            patch_storyforge_home, "ethan-cole", "donts",
            ["**Never use rooms** — *The room received it.*"],
        )
        assert _scan_author_rules(book) == []

    def test_no_author_returns_empty(self, tmp_path, patch_storyforge_home, seed_author_discoveries):
        book = _write_book(
            tmp_path,
            author_line="- **Genre:** test",
            chapters={"01": "# Ch\n\nThe room received it.\n"},
        )
        seed_author_discoveries(
            patch_storyforge_home, "ethan-cole", "donts",
            ["**Never use rooms** — *The room received it.*"],
        )
        assert _scan_author_rules(book) == []

    def test_no_donts_rows_returns_empty(self, tmp_path, patch_storyforge_home, seed_author_discoveries):
        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nThe room received it.\n"},
        )
        seed_author_discoveries(
            patch_storyforge_home, "ethan-cole", "recurring_tics", ["**\"thing\"** — concretize."],
        )
        assert _scan_author_rules(book) == []

    def test_both_donts_and_recurring_tics_yield_independent_findings(
        self, tmp_path, patch_storyforge_home, seed_author_discoveries
    ):
        """When both discovery types are populated, author_rules picks up
        the donts rows; the existing _scan_writing_discoveries handles
        recurring_tics. This test verifies the two scanners do not
        double-count or interfere.
        """
        from tools.analysis.manuscript.rules import _scan_writing_discoveries

        book = _write_book(
            tmp_path,
            chapters={
                "01": (
                    "# Ch\n\nThe room received it. "
                    "He was doing a thing with his hand.\n"
                ),
            },
        )
        seed_author_discoveries(
            patch_storyforge_home, "ethan-cole", "donts",
            ["**Never use rooms** — *The room received it.*"],
        )
        seed_author_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            "recurring_tics",
            ['**Vague-noun "thing" als Fallback** — concretize.'],
        )
        dont_findings = _scan_author_rules(book)
        tic_findings = _scan_writing_discoveries(book)

        assert dont_findings
        assert tic_findings
        assert all(f.category == "author_rule_violation" for f in dont_findings)
        assert all(f.category == "writing_discovery_violation" for f in tic_findings)

    def test_deleted_donts_row_no_longer_flagged(
        self, tmp_path, patch_storyforge_home, seed_author_discoveries, monkeypatch
    ):
        """Issue #604's core regression, at the scanner level: once a donts
        row is removed from the DB, the very next scan must not flag it —
        no stale profile.md snapshot left enforcing it."""
        import tools.db.connection as _db_conn
        from tools.db.author_discoveries import remove_discovery
        from tools.db.connection import open_authors_db

        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nThe room received it.\n"},
        )
        text = "**Never use rooms** — *The room received it.*"
        seed_author_discoveries(patch_storyforge_home, "ethan-cole", "donts", [text])
        assert _scan_author_rules(book), "sanity check: must be flagged before deletion"

        monkeypatch.setattr(_db_conn, "DB_DIR", patch_storyforge_home / "db")
        conn = open_authors_db()
        try:
            remove_discovery(conn, author_slug="ethan-cole", discovery_type="donts", text=text)
        finally:
            conn.close()

        assert _scan_author_rules(book) == []
