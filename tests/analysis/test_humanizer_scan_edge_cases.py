"""Edge cases for tools.analysis.humanizer_scan found in code review: curly
apostrophes, dialogue vs. density rules, span-based author dedup, repeated
matches in one paragraph."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools.analysis.humanizer_scan import check_replacement, load_patterns, scan_draft
from tools.banlist_loader import SEVERITY_BLOCK, BannedPattern

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))


@pytest.fixture(scope="module")
def catalog():
    shapes, tells, _ = load_patterns(PLUGIN_ROOT, author_slug=None)
    return shapes, tells


def _scan(text: str, catalog, author=None, **kwargs) -> dict:
    shapes, tells = catalog
    return scan_draft(text, global_shapes=shapes, global_tells=tells, author_patterns=author or [], **kwargs)


def _math_author() -> list[BannedPattern]:
    return [
        BannedPattern(
            label="math",
            pattern=re.compile(r"\bmath\b", re.IGNORECASE),
            severity=SEVERITY_BLOCK,
            source="author donts",
        )
    ]


def _lines(result: dict, category: str) -> list[int]:
    return [h["line"] for h in result["hits"] if h["category"] == category]


class TestCurlyApostrophes:
    def test_negation_loop_fires_with_curly_apostrophes(self, catalog) -> None:
        text = "It wasn’t fear. It was rest.\nRain fell.\nIt wasn’t hope. It was habit.\n"
        assert _lines(_scan(text, catalog), "negation_loop") == [3]

    def test_near_miss_fires_with_curly_apostrophes(self, catalog) -> None:
        text = "He didn’t quite smile.\nShe didn’t quite nod.\n"
        assert _lines(_scan(text, catalog), "near_miss") == [1, 2]

    def test_replacement_caution_with_curly_apostrophes(self, catalog) -> None:
        shapes, tells = catalog
        result = check_replacement(
            "It wasn’t fear. It was rest.",
            global_shapes=shapes,
            global_tells=tells,
            author_patterns=[],
        )
        assert {"kind": "negation_loop", "count": 1} in result["cautions"]


class TestDensityRulesCountNarrationOnly:
    def test_near_miss_in_dialogue_does_not_count_toward_density(self, catalog) -> None:
        text = '"I didn\'t quite catch that," he said.\nHis mouth did not quite become a smile.\n'
        assert _lines(_scan(text, catalog), "near_miss") == []

    def test_two_narration_near_misses_still_flag(self, catalog) -> None:
        text = 'His mouth did not quite become a smile.\n"Fine," he said. She never quite nodded.\n'
        assert _lines(_scan(text, catalog), "near_miss") == [1, 2]

    def test_negation_loop_in_dialogue_is_ignored(self, catalog) -> None:
        text = (
            '"It wasn\'t fear. It was rest," she said.\n'
            '"It wasn\'t hope. It was habit," he said.\n'
            "It wasn't cold. It was quiet.\n"
        )
        assert _lines(_scan(text, catalog), "negation_loop") == []

    def test_replacement_dialogue_does_not_raise_density_cautions(self, catalog) -> None:
        shapes, tells = catalog
        result = check_replacement(
            '"He didn\'t quite smile," she said.',
            global_shapes=shapes,
            global_tells=tells,
            author_patterns=[],
        )
        assert result["cautions"] == []


class TestAuthorDedupBySpan:
    def test_unrelated_global_hit_on_the_same_line_is_kept(self, catalog) -> None:
        text = "He did the math. The silence held for a long time.\n"
        cats = [h["category"] for h in _scan(text, catalog, author=_math_author())["hits"]]
        assert cats == ["author_rule", "shape"]

    def test_overlapping_global_hit_is_suppressed(self, catalog) -> None:
        author = [
            BannedPattern(
                label="landed",
                pattern=re.compile(r"\blanded\b", re.IGNORECASE),
                severity=SEVERITY_BLOCK,
                source="author donts",
            )
        ]
        cats = [h["category"] for h in _scan("The words landed.\n", catalog, author=author)["hits"]]
        assert cats == ["author_rule"]


class TestEveryOccurrenceIsReported:
    def test_same_shape_twice_in_one_paragraph_gives_two_hits(self, catalog) -> None:
        text = "The words landed. Much later the words landed again.\n"
        assert _lines(_scan(text, catalog), "shape") == [1, 1]

    def test_counts_reflect_every_occurrence(self, catalog) -> None:
        text = "A nuanced plan and a nuanced reply.\n"
        assert _scan(text, catalog)["counts"]["vocabulary"] == 2


class TestLineNumbers:
    def test_unicode_line_separator_does_not_shift_hit_lines(self, catalog) -> None:
        text = "Line one.\u2028still one.\nThe words landed.\n"
        assert _lines(_scan(text, catalog), "shape") == [2]

    def test_dash_flag_lists_a_line_once_per_dash(self, catalog) -> None:
        result = _scan("A — b — c — d.\n", catalog, dash_limit=0.1)
        (flag,) = [f for f in result["flags"] if f["kind"] == "dash_density"]
        assert flag["lines"] == [1, 1, 1]
        assert flag["excess"] == 3
