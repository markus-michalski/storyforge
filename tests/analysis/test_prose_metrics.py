"""Tests for tools.analysis.prose_metrics — deterministic prose measurements
that back the chapter-humanizer (burstiness, dash density, hedge density,
repeated sentence openers, invisible characters)."""

from __future__ import annotations

import pytest

from tools.analysis.prose_metrics import (
    DEFAULT_DASH_PER_1K_LIMIT,
    analyse_draft,
    compare_metrics,
)


def _chapter(metrics: dict) -> dict:
    return metrics["chapter"]


class TestSegments:
    def test_no_break_marker_yields_single_segment(self) -> None:
        text = "She walked in. He looked up.\n\nNobody spoke for a while.\n"
        result = analyse_draft(text)
        assert result["scene_breaks_found"] is False
        assert len(result["segments"]) == 1

    @pytest.mark.parametrize("marker", ["---", "***", "* * *", "___"])
    def test_horizontal_rule_splits_segments(self, marker: str) -> None:
        text = f"First scene line.\n\n{marker}\n\nSecond scene line.\n"
        result = analyse_draft(text)
        assert result["scene_breaks_found"] is True
        assert len(result["segments"]) == 2

    def test_frontmatter_is_not_a_scene_break(self) -> None:
        text = "---\ntitle: x\n---\n\nOnly one scene here.\n"
        result = analyse_draft(text)
        assert result["scene_breaks_found"] is False
        assert len(result["segments"]) == 1

    def test_headings_are_skipped(self) -> None:
        text = "# Chapter One\n\nShe walked in and sat down.\n"
        result = analyse_draft(text)
        assert _chapter(result)["narration_words"] == 6

    def test_segment_line_numbers_follow_the_original_file(self) -> None:
        text = "---\ntitle: x\n---\n\nFirst.\n\n***\n\nSecond scene starts here.\n"
        result = analyse_draft(text)
        assert result["segments"][1]["first_line"] == 9


class TestDialogueNarrationSplit:
    def test_dialogue_words_are_not_counted_as_narration(self) -> None:
        text = 'He said, "I do not know what you mean by that."\n'
        chapter = _chapter(analyse_draft(text))
        assert chapter["dialogue_words"] == 9
        assert chapter["narration_words"] == 2

    def test_curly_quotes_are_dialogue_too(self) -> None:
        text = "He said, “I do not know what you mean.”\n"
        chapter = _chapter(analyse_draft(text))
        assert chapter["dialogue_words"] == 7

    def test_umlauts_count_as_letters(self) -> None:
        text = "Über Nacht fiel der Schnee auf die Dächer der Stadt.\n"
        assert _chapter(analyse_draft(text))["narration_words"] == 10


class TestDashDensity:
    def test_interruption_dash_inside_dialogue_is_not_counted(self) -> None:
        text = 'He started, "I thought—" She cut him off.\n'
        chapter = _chapter(analyse_draft(text))
        assert chapter["dash_count"] == 0
        assert chapter["dialogue_dash_count"] == 1

    def test_narration_dash_is_counted(self) -> None:
        text = "The house was quiet — too quiet. She listened.\n"
        chapter = _chapter(analyse_draft(text))
        assert chapter["dash_count"] == 1

    def test_spaced_en_dash_counts_as_dash(self) -> None:
        text = "The house was quiet – too quiet. She listened.\n"
        assert _chapter(analyse_draft(text))["dash_count"] == 1

    def test_range_en_dash_is_not_a_dash(self) -> None:
        text = "The house stood on pages 5–10 of the survey. She listened.\n"
        assert _chapter(analyse_draft(text))["dash_count"] == 0

    def test_density_is_per_thousand_narration_words(self) -> None:
        body = "word " * 99 + "— done."
        chapter = _chapter(analyse_draft(body + "\n"))
        assert chapter["dash_count"] == 1
        assert chapter["dash_per_1k"] == pytest.approx(10.0, rel=0.05)

    def test_dash_lines_are_reported_with_original_line_numbers(self) -> None:
        text = "Plain line here.\n\nOne — two.\n"
        assert _chapter(analyse_draft(text))["dash_lines"] == [3]

    def test_default_limit_is_a_positive_number(self) -> None:
        assert DEFAULT_DASH_PER_1K_LIMIT > 0


class TestBurstiness:
    def test_uniform_sentences_have_low_variation(self) -> None:
        sentence = "The man crossed the road slowly. "
        chapter = _chapter(analyse_draft(sentence * 10 + "\n"))
        assert chapter["burstiness_cv"] is not None
        assert chapter["burstiness_cv"] < 0.05

    def test_varied_sentences_have_high_variation(self) -> None:
        text = (
            "No. The long road out of the valley wound past the mill and the "
            "burned-out church before it finally gave up. Rain. She counted "
            "the fence posts until the numbers stopped meaning anything at all "
            "and then counted them again. Fine.\n"
        )
        chapter = _chapter(analyse_draft(text))
        assert chapter["burstiness_cv"] > 0.6

    def test_too_few_sentences_yields_none(self) -> None:
        chapter = _chapter(analyse_draft("One sentence only here.\n"))
        assert chapter["burstiness_cv"] is None


class TestHedgeDensity:
    def test_hedges_are_counted_per_segment(self) -> None:
        text = "He seemed tired. She appeared to agree.\n\n***\n\nIt seemed fine.\n"
        result = analyse_draft(text)
        assert [s["hedge_count"] for s in result["segments"]] == [2, 1]
        assert _chapter(result)["hedge_count"] == 3

    def test_hedge_lines_recorded(self) -> None:
        text = "Nothing here.\nHe seemed tired.\n"
        segment = analyse_draft(text)["segments"][0]
        assert segment["hedge_lines"] == [2]


class TestRepeatedOpeners:
    def test_four_consecutive_same_openers_are_reported(self) -> None:
        text = "She opened the door. She stepped inside. She looked around. She waited.\n"
        runs = _chapter(analyse_draft(text))["repeated_openers"]
        assert len(runs) == 1
        assert runs[0]["opener"] == "she"
        assert runs[0]["run"] == 4
        assert runs[0]["line"] == 1

    def test_three_in_a_row_is_below_the_threshold(self) -> None:
        # Runs of 3 are ordinary prose (107 of 143 runs in a reviewed novel).
        text = "She opened the door. She stepped inside. She looked around.\n"
        assert _chapter(analyse_draft(text))["repeated_openers"] == []

    def test_run_continues_across_paragraph_lines(self) -> None:
        text = "She opened.\nShe stepped inside.\nShe looked around.\nShe waited.\n"
        runs = _chapter(analyse_draft(text))["repeated_openers"]
        assert len(runs) == 1 and runs[0]["line"] == 1

    def test_dialogue_led_sentence_breaks_a_run(self) -> None:
        text = 'She opened. She sat. "She knew." She stood. She waited. She left.\n'
        assert _chapter(analyse_draft(text))["repeated_openers"] == []

    def test_dialogue_tag_fragment_is_not_an_opener(self) -> None:
        text = '"Come in," she said. She waited. She sat. She stood.\n'
        assert _chapter(analyse_draft(text))["repeated_openers"] == []


class TestInvisibleCharacters:
    def test_zero_width_space_is_reported_with_line(self) -> None:
        text = "Clean line.\nHidden\u200b mark.\n"
        chapter = _chapter(analyse_draft(text))
        assert chapter["invisible_chars"] == 1
        assert chapter["invisible_lines"] == [2]

    def test_bom_and_nbsp_are_reported(self) -> None:
        text = "\ufeffStart here.\nA\u00a0B.\n"
        chapter = _chapter(analyse_draft(text))
        assert chapter["invisible_chars"] == 2

    def test_clean_text_has_none(self) -> None:
        chapter = _chapter(analyse_draft("All clean here.\n"))
        assert chapter["invisible_chars"] == 0
        assert chapter["invisible_lines"] == []


class TestCompare:
    def test_delta_reports_before_after_for_key_metrics(self) -> None:
        before = analyse_draft("One — two. Three — four. She seemed tired.\n")
        after = analyse_draft("One, two. Three, four. She was tired.\n")
        delta = compare_metrics(before, after)
        assert delta["dash_count"] == {"before": 2, "after": 0}
        assert delta["hedge_count"] == {"before": 1, "after": 0}
        assert set(delta) >= {
            "burstiness_cv",
            "dash_per_1k",
            "repeated_opener_runs",
            "invisible_chars",
        }

    def test_delta_handles_missing_burstiness(self) -> None:
        a = analyse_draft("Short.\n")
        b = analyse_draft("Short.\n")
        delta = compare_metrics(a, b)
        assert delta["burstiness_cv"] == {"before": None, "after": None}
