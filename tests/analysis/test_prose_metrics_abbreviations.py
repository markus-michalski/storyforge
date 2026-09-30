"""Honorific abbreviations must not split sentences (code review L7)."""

from __future__ import annotations

import pytest

from tools.analysis.prose_metrics import analyse_draft


def _chapter(text: str) -> dict:
    return analyse_draft(text)["chapter"]


class TestAbbreviations:
    def test_honorific_does_not_end_a_sentence(self) -> None:
        text = "Mr. Smith went home. Mrs. Jones waited by the door. Dr. Who left.\n"
        assert _chapter(text)["narration_sentences"] == 3

    def test_opener_run_is_found_through_honorifics(self) -> None:
        text = "Mr. Smith sat. Mr. Smith stood. Mr. Smith left. Mr. Smith waited.\n"
        runs = _chapter(text)["repeated_openers"]
        assert len(runs) == 1
        assert runs[0]["opener"] == "mr"
        assert runs[0]["run"] == 4

    @pytest.mark.parametrize("abbr", ["Mr", "Mrs", "Ms", "Dr", "Prof", "Sr", "Jr", "St", "Capt", "Sgt"])
    def test_each_listed_abbreviation(self, abbr: str) -> None:
        text = f"{abbr}. Nolan waited. He left.\n"
        assert _chapter(text)["narration_sentences"] == 2

    def test_a_normal_word_ending_a_sentence_still_splits(self) -> None:
        text = "He saw the doctor. Dr. Who left. She stayed.\n"
        assert _chapter(text)["narration_sentences"] == 3
