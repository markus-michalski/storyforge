"""Unit tests for tools.analysis.manuscript.body_tells (Issue #511).

``scan_repetitions``'s n-gram pass only flags a ``character_tell`` when the
exact same 4-7 word string repeats. An author who consciously varies the
phrasing of a body-language tic ("shoulders came down" / "shoulders had
dropped" / "the set of his shoulders") is invisible to it. This module adds
a slot-based detector: [body part] + [body-state verb], counted per body
part regardless of exact wording.
"""

from __future__ import annotations

from pathlib import Path

from tools.analysis.manuscript.body_tells import (
    _canonical_body_part,
    _scan_body_state_tells,
)
from tools.analysis.manuscript.vocabularies import BODY_PARTS


def _write_book(tmp_path: Path, chapters: dict[str, str], claudemd: str = "# Test Book\n") -> Path:
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


class TestCanonicalBodyPart:
    def test_plural_collapses_to_singular(self) -> None:
        assert _canonical_body_part("shoulders") == "shoulder"

    def test_singular_stays_singular(self) -> None:
        assert _canonical_body_part("shoulder") == "shoulder"

    def test_non_body_part_passes_through(self) -> None:
        assert _canonical_body_part("windows") == "windows"


class TestScanBodyStateTells:
    # Paraphrases of the same tension beat, taken from the issue repro —
    # deliberately share no 4-7 word n-gram with each other.
    _PARAPHRASED_SHOULDER_LINES = [
        "His shoulders came down instead, degree by degree.",
        "His shoulders squared, just slightly.",
        "But the tension in his shoulders eased, just slightly.",
        "The shoulder relaxed.",
        "Kevin's shoulders squared.",
        "His shoulders were set higher than usual, tension not posture.",
        "His shoulders had dropped from their earlier position.",
        "The shoulder drops whenever he lies.",
        "His shoulders dropped a fraction.",
        "The set of his shoulders went rigid again.",
    ]

    def test_paraphrased_tics_are_detected_as_one_finding(self, tmp_path: Path) -> None:
        draft = "# Chapter 1\n\n" + "\n".join(self._PARAPHRASED_SHOULDER_LINES) + "\n"
        book = _write_book(tmp_path, {"01-open": draft})

        findings = _scan_body_state_tells(book)

        assert len(findings) == 1
        finding = findings[0]
        assert finding.category == "character_tell"
        assert "shoulder" in finding.phrase
        # 10 lines match a [body part] + [state verb] slot -> high severity.
        assert finding.count == 10
        assert finding.severity == "high"

    def test_below_threshold_does_not_surface(self, tmp_path: Path) -> None:
        draft = "# Chapter 1\n\n" + "\n".join(self._PARAPHRASED_SHOULDER_LINES[:3]) + "\n"
        book = _write_book(tmp_path, {"01-open": draft})

        findings = _scan_body_state_tells(book)

        assert findings == []

    def test_empty_book_returns_no_findings(self, tmp_path: Path) -> None:
        # No chapters/ directory at all — _read_chapter_drafts returns [],
        # and _scan_body_state_tells must short-circuit rather than error.
        book = tmp_path / "empty-book"
        book.mkdir()
        (book / "CLAUDE.md").write_text("# Empty Book\n", encoding="utf-8")

        assert _scan_body_state_tells(book) == []

    def test_possessive_apostrophe_on_body_part_token(self, tmp_path: Path) -> None:
        # "shoulders'" (plural possessive) tokenises with a trailing
        # apostrophe (_TOKEN_RE keeps apostrophes inside tokens) — only the
        # rstrip("'") normalization collapses it onto "shoulder".
        draft = "# Chapter 1\n\n" + "\n".join(["Her shoulders' tension finally eased." for _ in range(6)]) + "\n"
        book = _write_book(tmp_path, {"01-open": draft})

        findings = _scan_body_state_tells(book)

        assert len(findings) == 1
        assert findings[0].phrase == "shoulder (varied phrasing)"
        assert findings[0].count == 6

    def test_medium_severity_between_five_and_nine(self, tmp_path: Path) -> None:
        draft = "# Chapter 1\n\n" + "\n".join(self._PARAPHRASED_SHOULDER_LINES[:6]) + "\n"
        book = _write_book(tmp_path, {"01-open": draft})

        findings = _scan_body_state_tells(book)

        assert len(findings) == 1
        assert findings[0].severity == "medium"
        assert findings[0].count == 6

    def test_allowed_repetitions_suppresses_the_body_part(self, tmp_path: Path) -> None:
        draft = "# Chapter 1\n\n" + "\n".join(self._PARAPHRASED_SHOULDER_LINES) + "\n"
        claudemd = "# Test Book\n\n## Allowed Repetitions\n\n- shoulder\n"
        book = _write_book(tmp_path, {"01-open": draft}, claudemd=claudemd)

        findings = _scan_body_state_tells(book)

        assert findings == []

    def test_allowed_repetitions_accepts_the_natural_plural_spelling(self, tmp_path: Path) -> None:
        # Regression: an author naturally writes the plural they see in
        # their own manuscript ("- shoulders"), not the internal singular
        # canonical form. Both sides must canonicalize for the allowlist to
        # actually work as an escape hatch.
        draft = "# Chapter 1\n\n" + "\n".join(self._PARAPHRASED_SHOULDER_LINES) + "\n"
        claudemd = "# Test Book\n\n## Allowed Repetitions\n\n- shoulders\n"
        book = _write_book(tmp_path, {"01-open": draft}, claudemd=claudemd)

        findings = _scan_body_state_tells(book)

        assert findings == []

    def test_allowed_repetitions_is_whole_token_not_substring(self, tmp_path: Path) -> None:
        # Regression: an allowlist entry that merely CONTAINS the body-part
        # word as a substring ("years" contains "ear") must not suppress it.
        lines = [
            "Her ears burned, tight with embarrassment.",
            "Her ears were tense, rigid at the sound.",
            "His ears set into a stiff line.",
            "Her ears tightened at the accusation.",
            "His ears loosened as the anger faded.",
        ]
        draft = "# Chapter 1\n\n" + "\n".join(lines) + "\n"
        claudemd = "# Test Book\n\n## Allowed Repetitions\n\n- for years the war had eased nothing\n"
        book = _write_book(tmp_path, {"01-open": draft}, claudemd=claudemd)

        findings = _scan_body_state_tells(book)

        assert any("ear" in f.phrase for f in findings)

    def test_no_finding_without_a_body_part_present(self, tmp_path: Path) -> None:
        draft = "# Chapter 1\n\n" + "\n".join(["The tension eased, just slightly." for _ in range(10)])
        book = _write_book(tmp_path, {"01-open": draft})

        findings = _scan_body_state_tells(book)

        assert findings == []

    def test_no_finding_without_a_state_verb_present(self, tmp_path: Path) -> None:
        draft = "# Chapter 1\n\n" + "\n".join(["He touched his shoulder and walked away." for _ in range(10)])
        book = _write_book(tmp_path, {"01-open": draft})

        findings = _scan_body_state_tells(book)

        assert findings == []


class TestExtendedVocabulary:
    """Adjective state-words + additional verbs (follow-up to #511 review)."""

    def _repeated(self, tmp_path: Path, line: str, times: int = 6) -> Path:
        draft = "# Chapter 1\n\n" + "\n".join([line] * times) + "\n"
        return _write_book(tmp_path, {"01-open": draft})

    def test_adjective_loose_is_detected(self, tmp_path: Path) -> None:
        # Verbatim from the issue's own example: "mouth easy, shoulders loose"
        # — an adjective state-word, not an inflected verb. Missed until the
        # BODY_STATE_ADJECTIVES follow-up.
        book = self._repeated(tmp_path, "His shoulders loose, his mouth easy.")

        findings = _scan_body_state_tells(book)

        parts = {f.phrase.split()[0] for f in findings}
        assert "shoulder" in parts
        assert "mouth" in parts

    def test_adjective_rigid_is_detected(self, tmp_path: Path) -> None:
        book = self._repeated(tmp_path, "Her jaw was rigid.")

        findings = _scan_body_state_tells(book)

        assert any("jaw" in f.phrase for f in findings)

    def test_clenched_verb_is_detected(self, tmp_path: Path) -> None:
        book = self._repeated(tmp_path, "His fists clenched at his sides.")

        findings = _scan_body_state_tells(book)

        assert any("fist" in f.phrase for f in findings)

    def test_slumped_verb_is_detected(self, tmp_path: Path) -> None:
        book = self._repeated(tmp_path, "Her shoulders slumped.")

        findings = _scan_body_state_tells(book)

        assert any("shoulder" in f.phrase for f in findings)

    def test_straightened_verb_is_detected(self, tmp_path: Path) -> None:
        book = self._repeated(tmp_path, "His spine straightened.")

        findings = _scan_body_state_tells(book)

        assert any("spine" in f.phrase for f in findings)


class TestCanonicalBodyPartIrregularPlural:
    def test_feet_collapses_to_foot(self) -> None:
        assert _canonical_body_part("feet") == "foot"


class TestProximityWindow:
    """Body part and state signal must be close together, not just co-present
    somewhere in the same (paragraph-length) markdown line — the false
    positive the code review caught."""

    def test_unrelated_clauses_in_one_paragraph_do_not_match(self, tmp_path: Path) -> None:
        # A single long paragraph line where a generic state word and a body
        # part both appear, but far apart and about unrelated things.
        line = (
            "He set the kettle on the stove, checked the lock twice, found his "
            "coat, and only then did he let his eyes follow a single taxi "
            "crawling down the wet street outside."
        )
        draft = "# Chapter 1\n\n" + "\n".join([line] * 8) + "\n"
        book = _write_book(tmp_path, {"01-open": draft})

        findings = _scan_body_state_tells(book)

        assert findings == []

    def test_came_requires_adjacent_down(self, tmp_path: Path) -> None:
        # Bare "came" near a body part, with no "down", must not match.
        line = "Tears came to her eyes as the news came over the radio."
        draft = "# Chapter 1\n\n" + "\n".join([line] * 8) + "\n"
        book = _write_book(tmp_path, {"01-open": draft})

        findings = _scan_body_state_tells(book)

        assert findings == []

    def test_come_down_within_window_still_matches(self, tmp_path: Path) -> None:
        line = "His shoulders had come down by the time she looked back."
        draft = "# Chapter 1\n\n" + "\n".join([line] * 6) + "\n"
        book = _write_book(tmp_path, {"01-open": draft})

        findings = _scan_body_state_tells(book)

        assert any("shoulder" in f.phrase for f in findings)


class TestDialogueStripped:
    def test_dialogue_does_not_count_toward_a_tell(self, tmp_path: Path) -> None:
        line = '"Your hand is tight on that glass," she said, and looked away.'
        draft = "# Chapter 1\n\n" + "\n".join([line] * 8) + "\n"
        book = _write_book(tmp_path, {"01-open": draft})

        findings = _scan_body_state_tells(book)

        assert findings == []

    def test_narration_around_dialogue_still_counts(self, tmp_path: Path) -> None:
        line = 'His hand tightened. "Let go," she said.'
        draft = "# Chapter 1\n\n" + "\n".join([line] * 6) + "\n"
        book = _write_book(tmp_path, {"01-open": draft})

        findings = _scan_body_state_tells(book)

        assert any("hand" in f.phrase for f in findings)


class TestMultiChapterAndExcludeParts:
    def test_occurrences_span_and_sort_across_chapters(self, tmp_path: Path) -> None:
        line = "Her shoulders slumped again."
        book = _write_book(
            tmp_path,
            {
                "02-second": "\n".join([line] * 3) + "\n",
                "01-first": "\n".join([line] * 3) + "\n",
            },
        )

        findings = _scan_body_state_tells(book)

        assert len(findings) == 1
        chapters = [o.chapter for o in findings[0].occurrences]
        assert chapters == sorted(chapters)
        assert {"01-first", "02-second"} == set(chapters)

    def test_exclude_sites_only_removes_matching_lines(self, tmp_path: Path) -> None:
        draft = "# Chapter 1\n\n" + "\n".join(TestScanBodyStateTells._PARAPHRASED_SHOULDER_LINES) + "\n"
        book = _write_book(tmp_path, {"01-open": draft})
        # Lines 1-2 are the (blank, post-strip) heading + separator; the
        # paraphrase lines start at line 3.
        excluded = frozenset({("01-open", 3, "shoulder"), ("01-open", 4, "shoulder")})

        findings = _scan_body_state_tells(book, exclude_sites=excluded)

        assert len(findings) == 1
        assert findings[0].count == 8

    def test_exclude_sites_does_not_wipe_out_the_whole_aggregate(self, tmp_path: Path) -> None:
        # Regression (code review H1): a single excluded site must only
        # reduce the aggregate count, never delete the finding entirely —
        # the old body-part-wide exclusion could erase a 10-occurrence,
        # high-severity finding because of one incidental n-gram hit that
        # merely mentioned the same body part elsewhere.
        draft = "# Chapter 1\n\n" + "\n".join(TestScanBodyStateTells._PARAPHRASED_SHOULDER_LINES) + "\n"
        book = _write_book(tmp_path, {"01-open": draft})

        findings = _scan_body_state_tells(book, exclude_sites=frozenset({("01-open", 3, "shoulder")}))

        assert len(findings) == 1
        assert findings[0].count == 9

    def test_exclude_sites_for_unrelated_chapter_has_no_effect(self, tmp_path: Path) -> None:
        draft = "# Chapter 1\n\n" + "\n".join(TestScanBodyStateTells._PARAPHRASED_SHOULDER_LINES) + "\n"
        book = _write_book(tmp_path, {"01-open": draft})

        findings = _scan_body_state_tells(book, exclude_sites=frozenset({("99-other", 1, "shoulder")}))

        assert len(findings) == 1
        assert findings[0].count == 10

    def test_exclude_sites_does_not_wipe_out_a_different_body_part_on_the_same_line(self, tmp_path: Path) -> None:
        # Regression (code review H1, round 2): the same paragraph can carry
        # an unrelated n-gram tic (a different body part, or none at all)
        # alongside a genuine paraphrase. Excluding by (chapter, line) alone
        # would wipe out the genuine tell too — the key must include the
        # body part.
        line = "He set the jaw, his shoulders finally relaxed."
        draft = "# Chapter 1\n\n" + "\n".join([line] * 6) + "\n"
        book = _write_book(tmp_path, {"01-open": draft})
        # Simulate: the n-gram pass already reported "jaw" (a different body
        # part) on every one of these lines.
        excluded = frozenset({("01-open", i, "jaw") for i in range(3, 9)})

        findings = _scan_body_state_tells(book, exclude_sites=excluded)

        assert len(findings) == 1
        assert findings[0].phrase.startswith("shoulder")
        assert findings[0].count == 6


class TestFalsePositiveVocabulary:
    """Confirmed false positives from code review, now excluded/gated."""

    def _repeated(self, tmp_path: Path, line: str, times: int = 7) -> Path:
        draft = "# Chapter 1\n\n" + "\n".join([line] * times) + "\n"
        return _write_book(tmp_path, {"01-open": draft})

    def test_pulled_back_is_not_a_tell(self, tmp_path: Path) -> None:
        book = self._repeated(tmp_path, "She pulled back and studied the door.")
        assert _scan_body_state_tells(book) == []

    def test_dropped_back_is_not_a_tell(self, tmp_path: Path) -> None:
        book = self._repeated(tmp_path, "He dropped back a step to let the cart pass.")
        assert _scan_body_state_tells(book) == []

    def test_rolled_back_is_not_a_tell(self, tmp_path: Path) -> None:
        book = self._repeated(tmp_path, "The truck rolled back down the slope.")
        assert _scan_body_state_tells(book) == []

    def test_temple_as_building_is_not_a_tell(self, tmp_path: Path) -> None:
        book = self._repeated(tmp_path, "The temple was set on the far hill above the village.")
        assert _scan_body_state_tells(book) == []

    def test_back_and_temple_excluded_from_detector_body_parts(self) -> None:
        # BODY_PARTS (the shared classifier vocabulary) keeps "back" and
        # "temple" — only this detector's local scanning surface excludes
        # them, so the n-gram classifier elsewhere is unaffected.
        assert "back" in BODY_PARTS
        assert "temple" in BODY_PARTS


class TestCanonicalizationInvariant:
    def test_canonicalizing_every_body_part_stays_within_body_parts(self) -> None:
        # Pins the invariant the code review verified by hand: no BODY_PARTS
        # member canonicalizes to something outside BODY_PARTS (i.e. no
        # accidental cross-word merge via the trailing-"s" strip).
        for part in BODY_PARTS:
            assert _canonical_body_part(part) in BODY_PARTS
