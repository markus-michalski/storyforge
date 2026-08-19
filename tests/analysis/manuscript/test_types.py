"""Unit tests for tools.analysis.manuscript.types — classifier + dataclasses."""

from __future__ import annotations

import pytest

from tools.analysis.manuscript.types import (
    Finding,
    Occurrence,
    _classify,
    _collapse_overlapping_findings,
    _looks_structural,
)


def _occ(text: str = "", chapter: str = "01", line: int = 1) -> Occurrence:
    return Occurrence(chapter=chapter, line=line, snippet=text)


class TestClassify:
    def test_simile_with_like(self) -> None:
        cat = _classify(
            "shifted like a shadow on the wall",
            [_occ("She moved like a shadow on the wall.")],
        )
        assert cat == "simile"

    def test_blocking_tic_with_closed_punctuation(self) -> None:
        cat = _classify(
            "closed his eyes for a moment",
            [_occ("He closed his eyes for a moment.")],
        )
        # contains 'closed' AND a body-part-ish flow — classifier picks
        # blocking_tic when blocking-verb + body part both present.
        assert cat in {"blocking_tic", "character_tell"}

    def test_character_tell_with_body_part(self) -> None:
        cat = _classify(
            "ran a hand through her hair",
            [_occ("Lena ran a hand through her hair.")],
        )
        assert cat == "character_tell"

    @pytest.mark.parametrize("phrase", ["her chins", "his elbows shook", "the wrists went", "both thumbs up"])
    def test_character_tell_with_newly_added_body_parts(self, phrase: str) -> None:
        # BODY_PARTS gained chins/elbows/wrists/thumbs (Issue #511 review
        # follow-up, closing a plural-coverage gap). These feed the
        # pre-existing n-gram classifier directly — pin that they actually
        # participate in character_tell classification.
        cat = _classify(phrase, [_occ(phrase)])
        assert cat == "character_tell"

    def test_sensory_with_smell(self) -> None:
        cat = _classify(
            "smell of smoke and wet earth",
            [_occ("The smell of smoke and wet earth filled the room.")],
        )
        assert cat == "sensory"

    def test_structural_for_years(self) -> None:
        cat = _classify("for a hundred and fifty years", [_occ("...")])
        assert cat == "structural"

    def test_signature_phrase_fallback(self) -> None:
        # No body parts, no blocking verbs, no sensory tokens, no structural
        # cues → falls through to signature_phrase.
        cat = _classify("she walked ahead alone", [_occ("...")])
        assert cat == "signature_phrase"


def _finding(phrase: str, occs: list[Occurrence], category: str = "character_tell") -> Finding:
    return Finding(phrase=phrase, category=category, severity="high", count=len(occs), occurrences=occs)


class TestCollapseOverlappingFindings:
    def test_shorter_subset_window_is_dropped(self) -> None:
        """Issue #613: 'the back of his' at the same two locations as the
        longer 'the back of his head' is pure redundancy — only the
        longer window should survive."""
        locs = [_occ(chapter="01", line=5), _occ(chapter="02", line=9)]
        short = _finding("the back of his", locs)
        long_ = _finding("the back of his head", locs)
        kept = _collapse_overlapping_findings([short, long_])
        assert kept == [long_]

    def test_disjoint_findings_both_kept(self) -> None:
        short = _finding("the back of his", [_occ(chapter="01", line=1)])
        unrelated = _finding("out the window quietly", [_occ(chapter="03", line=7)])
        kept = _collapse_overlapping_findings([short, unrelated])
        assert {f.phrase for f in kept} == {"the back of his", "out the window quietly"}

    def test_unrelated_findings_sharing_locations_both_kept(self) -> None:
        """Code review H-2: two completely unrelated findings — different
        phrase, different category — that happen to share an occurrence-
        location set (the same two paragraphs happen to carry both tics)
        must NOT be merged into one just because they co-occur. Location
        alone is not identity; it must be corroborated by either a
        substring relationship or a shared category."""
        locs = [_occ(chapter="01", line=5), _occ(chapter="02", line=9)]
        simile = _finding("like a struck match catching fire", locs, category="simile")
        tell = _finding("the back of his neck went cold", locs, category="character_tell")
        kept = _collapse_overlapping_findings([simile, tell])
        assert {f.phrase for f in kept} == {simile.phrase, tell.phrase}

    def test_same_length_shifted_windows_same_category_collapse(self) -> None:
        """Two different-content, same-length windows of the same
        underlying duplicate (shifted by one token, so neither is a
        substring of the other) still collapse when they share a
        category — the shape _scan_sentence_repetitions produces."""
        locs = [_occ(chapter="01", line=1), _occ(chapter="02", line=1)]
        a = _finding("zebra crossing the wide road", locs, category="sentence_repetition")
        b = _finding("crossing the wide road today", locs, category="sentence_repetition")
        kept = _collapse_overlapping_findings([a, b])
        assert len(kept) == 1

    def test_partial_overlap_subset_still_collapses(self) -> None:
        """A shorter finding's locations don't need to be byte-identical to
        the longer one's — being a SUBSET is enough to count as redundant."""
        long_locs = [_occ(chapter="01", line=1), _occ(chapter="02", line=2), _occ(chapter="03", line=3)]
        short_locs = [_occ(chapter="01", line=1), _occ(chapter="02", line=2)]
        short = _finding("hand on the back", short_locs)
        long_ = _finding("hand on the back of his neck", long_locs)
        kept = _collapse_overlapping_findings([short, long_])
        assert kept == [long_]


class TestLooksStructural:
    def test_for_years_pattern(self) -> None:
        assert _looks_structural(["for", "five", "long", "years"]) is True

    def test_the_x_of_y_pattern(self) -> None:
        assert _looks_structural(["the", "weight", "of", "her"]) is True

    def test_unknown_pattern_returns_false(self) -> None:
        assert _looks_structural(["she", "walked", "ahead"]) is False

    def test_empty_returns_false(self) -> None:
        assert _looks_structural([]) is False
