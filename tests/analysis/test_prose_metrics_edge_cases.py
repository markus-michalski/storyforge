"""Edge cases for tools.analysis.prose_metrics found in code review: narration
that shares a line with dialogue, non-English quote styles, BOM/CRLF/Unicode
line separators, and dash-line bookkeeping."""

from __future__ import annotations

import pytest

from tools.analysis.prose_metrics import analyse_draft


def _chapter(text: str) -> dict:
    return analyse_draft(text)["chapter"]


class TestNarrationAfterDialogueOnTheSameLine:
    def test_sentence_after_a_closed_quote_counts_as_narration(self) -> None:
        text = "".join(
            f'"Hi." He sat down on the old chair by the window number {n}.\n'
            for n in ("one", "two", "three", "four", "five")
        )
        chapter = _chapter(text)
        assert chapter["narration_sentences"] == 5
        assert chapter["burstiness_cv"] is not None

    def test_sentence_after_an_interrupted_quote_counts_as_narration(self) -> None:
        text = '"I thought—" She cut him off before he finished the sentence.\n'
        assert _chapter(text)["narration_sentences"] == 1

    def test_tag_after_a_comma_quote_is_still_not_an_opener(self) -> None:
        text = '"Come in," she said. She waited. She sat. She stood.\n'
        assert _chapter(text)["repeated_openers"] == []

    def test_run_of_openers_after_quotes_is_still_found(self) -> None:
        text = '"No." He turned. He walked. He stopped. He waited.\n'
        runs = _chapter(text)["repeated_openers"]
        assert len(runs) == 1 and runs[0]["run"] == 4


class TestQuoteStyles:
    @pytest.mark.parametrize(
        "text",
        [
            "'I thought — ' she began.\n",
            "„Ich dachte — “ sagte er.\n",
            "»Nein — nie« sagte sie.\n",
            "«Non — jamais» dit-elle.\n",
            "‘I thought — ’ she began.\n",
        ],
    )
    def test_dashes_inside_any_quote_style_are_dialogue_dashes(self, text: str) -> None:
        chapter = _chapter(text)
        assert chapter["dialogue_dash_count"] == 1
        assert chapter["dash_count"] == 0

    def test_apostrophes_are_not_quotes(self) -> None:
        text = "He didn't go and she wouldn't stay, and the dogs' bowls were empty.\n"
        assert _chapter(text)["dialogue_words"] == 0

    def test_curly_apostrophes_are_not_quotes(self) -> None:
        text = "He didn’t go and she wouldn’t stay, and the dogs’ bowls were empty.\n"
        assert _chapter(text)["dialogue_words"] == 0

    def test_single_quoted_speech_with_inner_apostrophe(self) -> None:
        text = "'Don't go — please,' he said.\n"
        chapter = _chapter(text)
        assert chapter["dialogue_dash_count"] == 1
        assert chapter["dash_count"] == 0


class TestLineHandling:
    def test_bom_before_frontmatter_does_not_create_a_scene_break(self) -> None:
        text = "\ufeff---\ntitle: x\n---\n\nShe walked in.\n"
        result = analyse_draft(text)
        assert result["scene_breaks_found"] is False
        assert len(result["segments"]) == 1
        assert result["chapter"]["narration_words"] == 3

    def test_crlf_line_endings_keep_line_numbers(self) -> None:
        text = "Plain.\r\n\r\nOne — two.\r\n"
        assert _chapter(text)["dash_lines"] == [3]

    def test_unicode_line_separator_does_not_shift_line_numbers(self) -> None:
        text = "Line one.\u2028still one.\nOne — two.\n"
        assert _chapter(text)["dash_lines"] == [2]

    def test_unicode_line_separator_is_reported_as_invisible(self) -> None:
        chapter = _chapter("Line one.\u2028still one.\n")
        assert chapter["invisible_chars"] == 1
        assert chapter["invisible_lines"] == [1]


class TestDashLines:
    def test_a_line_is_listed_once_per_dash_on_it(self) -> None:
        chapter = _chapter("A — b — c — d.\n")
        assert chapter["dash_count"] == 3
        assert chapter["dash_lines"] == [1, 1, 1]
