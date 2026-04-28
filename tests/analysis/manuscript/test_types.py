"""Unit tests for tools.analysis.manuscript.types — classifier + dataclasses."""

from __future__ import annotations

from tools.analysis.manuscript.types import (
    Occurrence,
    _classify,
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


class TestLooksStructural:
    def test_for_years_pattern(self) -> None:
        assert _looks_structural(["for", "five", "long", "years"]) is True

    def test_the_x_of_y_pattern(self) -> None:
        assert _looks_structural(["the", "weight", "of", "her"]) is True

    def test_unknown_pattern_returns_false(self) -> None:
        assert _looks_structural(["she", "walked", "ahead"]) is False

    def test_empty_returns_false(self) -> None:
        assert _looks_structural([]) is False
