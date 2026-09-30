"""Tests for tools.analysis.humanizer_scan — the deterministic pre-scan behind
chapter-humanizer: catalog shapes, flagged vocabulary, author rules, per-scene
density rules, dash density, repeated openers, invisible characters — and the
replacement check that makes Surgical Mode rule 2 verifiable."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools.analysis.humanizer_scan import (
    check_replacement,
    load_author_dash_limit,
    load_patterns,
    scan_draft,
)
from tools.banlist_loader import SEVERITY_BLOCK, BannedPattern

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep author-DB lookups away from the developer's real ~/.storyforge."""
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    return fake_home / ".storyforge"


@pytest.fixture(scope="module")
def catalog():
    # Module-scoped: parses the real anti-ai-patterns.md once.
    shapes, tells, _ = load_patterns(PLUGIN_ROOT, author_slug=None)
    return shapes, tells


def _scan(text: str, catalog, **kwargs):
    shapes, tells = catalog
    return scan_draft(text, global_shapes=shapes, global_tells=tells, author_patterns=[], **kwargs)


def _cats(result: dict) -> list[str]:
    return [h["category"] for h in result["hits"]]


class TestCatalogHits:
    def test_shape_hit_carries_line_and_category(self, catalog) -> None:
        result = _scan("Plain opening.\nThe words landed between them.\n", catalog)
        hits = [h for h in result["hits"] if h["category"] == "shape"]
        assert [h["line"] for h in hits] == [2]
        assert "landed" in hits[0]["snippet"]

    def test_vocabulary_hit(self, catalog) -> None:
        result = _scan("It was a nuanced tension between them.\n", catalog)
        assert "vocabulary" in _cats(result)

    def test_line_numbers_skip_frontmatter_offset(self, catalog) -> None:
        text = "---\ntitle: x\n---\n\nThe words landed hard.\n"
        hits = _scan(text, catalog)["hits"]
        assert [h["line"] for h in hits if h["category"] == "shape"] == [5]

    def test_hit_inside_dialogue_is_marked(self, catalog) -> None:
        result = _scan('"A nuanced view," he said.\n', catalog)
        vocab = [h for h in result["hits"] if h["category"] == "vocabulary"]
        assert vocab and vocab[0]["in_dialogue"] is True

    def test_hit_in_narration_is_not_marked_as_dialogue(self, catalog) -> None:
        result = _scan("It was a nuanced tension.\n", catalog)
        vocab = [h for h in result["hits"] if h["category"] == "vocabulary"]
        assert vocab[0]["in_dialogue"] is False

    def test_clean_prose_has_no_hits(self, catalog) -> None:
        result = _scan("Rain hit the tin roof. He put the kettle on.\n", catalog)
        assert result["hits"] == []

    def test_segment_index_is_reported(self, catalog) -> None:
        text = "Quiet start.\n\n***\n\nThe words landed hard.\n"
        hit = next(h for h in _scan(text, catalog)["hits"] if h["category"] == "shape")
        assert hit["segment"] == 2


class TestAuthorRules:
    def test_author_pattern_hit_is_categorised_and_severity_kept(self, catalog) -> None:
        shapes, tells = catalog
        author = [
            BannedPattern(
                label="math",
                pattern=re.compile(r"\bmath\b", re.IGNORECASE),
                severity=SEVERITY_BLOCK,
                source="author donts",
            )
        ]
        result = scan_draft(
            "He did the math in his head.\n",
            global_shapes=shapes,
            global_tells=tells,
            author_patterns=author,
        )
        hit = result["hits"][0]
        assert hit["category"] == "author_rule"
        assert hit["severity"] == "block"

    def test_author_hit_suppresses_global_hit_on_same_line(self, catalog) -> None:
        shapes, tells = catalog
        author = [
            BannedPattern(
                label="landed",
                pattern=re.compile(r"\blanded\b", re.IGNORECASE),
                severity=SEVERITY_BLOCK,
                source="author donts",
            )
        ]
        result = scan_draft(
            "The words landed between them.\n",
            global_shapes=shapes,
            global_tells=tells,
            author_patterns=author,
        )
        assert _cats(result) == ["author_rule"]


class TestDensityRules:
    def test_single_hedge_is_not_a_hit(self, catalog) -> None:
        result = _scan("He seemed tired.\n", catalog)
        assert result["hits"] == []

    def test_three_hedges_in_one_scene_flag_each_line(self, catalog) -> None:
        text = "He seemed tired.\nShe appeared to agree.\nIt seemed fine.\n"
        hits = [h for h in _scan(text, catalog)["hits"] if h["category"] == "hedge_density"]
        assert [h["line"] for h in hits] == [1, 2, 3]

    def test_hedges_split_across_scenes_stay_below_threshold(self, catalog) -> None:
        text = "He seemed tired. She appeared to agree.\n\n***\n\nIt seemed fine.\n"
        assert [h for h in _scan(text, catalog)["hits"] if h["category"] == "hedge_density"] == []

    def test_first_negation_assertion_is_allowed_second_is_flagged(self, catalog) -> None:
        text = (
            "It wasn't fear. It was something older.\n"
            "Rain fell.\n"
            "It wasn't the words that hurt. It was the silence after.\n"
        )
        hits = [h for h in _scan(text, catalog)["hits"] if h["category"] == "negation_loop"]
        assert [h["line"] for h in hits] == [3]

    def test_single_near_miss_is_allowed(self, catalog) -> None:
        text = "The corner of his mouth did not quite become a smile.\n"
        assert [h for h in _scan(text, catalog)["hits"] if h["category"] == "near_miss"] == []

    def test_two_near_misses_in_one_scene_flag_all(self, catalog) -> None:
        text = "His mouth did not quite become a smile.\nLater a breath that almost became a sentence.\n"
        hits = [h for h in _scan(text, catalog)["hits"] if h["category"] == "near_miss"]
        assert [h["line"] for h in hits] == [1, 2]

    def test_density_regexes_from_catalog_are_routed_not_double_reported(self, catalog) -> None:
        # The catalog's 11.9/11.10 regexes match single uses; they must not
        # surface as plain shape hits or one "seemed" would always be flagged.
        result = _scan("He seemed tired. It wasn't fear. It was rest.\n", catalog)
        assert [h for h in result["hits"] if h["category"] == "shape"] == []

    def test_density_shapes_are_routed_if_the_catalog_ever_loads_them(self, catalog) -> None:
        # Today the loader skips `**Banned shape (density):**` lines. If the
        # catalog switches them to the plain form, a single use must still not
        # become a per-occurrence hit.
        _, tells = catalog
        density = [
            BannedPattern(
                label=r"\b(seemed|appeared to|as if|might have)\b",
                pattern=re.compile(r"\b(seemed|appeared to|as if|might have)\b", re.IGNORECASE),
                severity="warn",
                source="synthetic",
            ),
            BannedPattern(
                label=r"\bIt wasn't [^.\n]{1,40}\.\s+It was\b",
                pattern=re.compile(r"\bIt wasn't [^.\n]{1,40}\.\s+It was\b"),
                severity="warn",
                source="synthetic",
            ),
        ]
        result = scan_draft(
            "He seemed tired. It wasn't fear. It was rest.\n",
            global_shapes=density,
            global_tells=tells,
            author_patterns=[],
        )
        assert [h for h in result["hits"] if h["category"] == "shape"] == []


class TestDashDensity:
    @staticmethod
    def _dash_flags(result: dict) -> list[dict]:
        return [f for f in result["flags"] if f["kind"] == "dash_density"]

    def test_over_limit_is_a_chapter_flag_listing_the_dash_lines(self, catalog) -> None:
        text = "First — line.\nPlain line.\nSecond — line.\n"
        result = _scan(text, catalog, dash_limit=1.0)
        (flag,) = self._dash_flags(result)
        assert flag["lines"] == [1, 3]
        assert flag["limit"] == 1.0
        assert flag["per_1k"] > 1.0

    def test_dash_density_never_becomes_per_line_hits(self, catalog) -> None:
        # A dashy chapter has dozens of dash lines; they must not swamp the
        # 20-hit batch.
        text = "First — line.\nSecond — line.\n"
        assert "dash_density" not in _cats(_scan(text, catalog, dash_limit=0.1))

    def test_excess_is_the_number_of_dashes_above_the_allowance(self, catalog) -> None:
        # 100 narration words at limit 10/1k allows 1 dash; 5 present -> excess 4.
        text = ("word " * 19 + "— done. ") * 5 + "\n"
        (flag,) = self._dash_flags(_scan(text, catalog, dash_limit=10.0))
        assert flag["excess"] == 4

    def test_under_limit_is_quiet(self, catalog) -> None:
        text = "First — line.\n" + "word " * 400 + "\n"
        assert self._dash_flags(_scan(text, catalog, dash_limit=4.0)) == []

    def test_dialogue_dashes_never_flagged(self, catalog) -> None:
        text = '"I thought—" "Don\'t—" "Wait—" she said.\n'
        assert self._dash_flags(_scan(text, catalog, dash_limit=0.1)) == []

    def test_result_reports_the_limit_used(self, catalog) -> None:
        assert _scan("Plain.\n", catalog, dash_limit=2.5)["dash_limit"] == 2.5
        assert _scan("Plain.\n", catalog)["dash_limit"] > 0


class TestStructuralAndFingerprint:
    def test_repeated_opener_run_is_a_hit(self, catalog) -> None:
        text = "She opened the door. She stepped inside. She looked around. She waited.\n"
        hits = [h for h in _scan(text, catalog)["hits"] if h["category"] == "repeated_openers"]
        assert len(hits) == 1 and hits[0]["line"] == 1

    def test_invisible_character_is_a_hit(self, catalog) -> None:
        result = _scan("Clean.\nHid\u200bden.\n", catalog)
        hits = [h for h in result["hits"] if h["category"] == "invisible_char"]
        assert [h["line"] for h in hits] == [2]

    def test_uniform_rhythm_is_a_chapter_flag_not_a_line_hit(self, catalog) -> None:
        text = "The man crossed the road slowly. " * 10 + "\n"
        result = _scan(text, catalog)
        assert any(f["kind"] == "uniform_rhythm" for f in result["flags"])
        assert "uniform_rhythm" not in _cats(result)

    def test_varied_rhythm_raises_no_flag(self, catalog) -> None:
        text = (
            "No. The long road out of the valley wound past the mill and the "
            "burned-out church before it finally gave up. Rain. She counted the "
            "fence posts until the numbers stopped meaning anything at all and "
            "then counted them again. Fine. Quiet. The dog did not bark once "
            "that whole long night, which was somehow worse.\n"
        )
        assert [f for f in _scan(text, catalog)["flags"] if f["kind"] == "uniform_rhythm"] == []

    def test_metrics_are_included(self, catalog) -> None:
        result = _scan("One sentence.\n", catalog)
        assert "chapter" in result["metrics"]
        assert result["scene_breaks_found"] is False

    def test_counts_summarise_categories(self, catalog) -> None:
        result = _scan("The words landed between them.\n", catalog)
        assert result["counts"]["shape"] == 1


class TestCheckReplacement:
    def test_clean_replacement_passes(self, catalog) -> None:
        shapes, tells = catalog
        result = check_replacement(
            "His throat tightened. He looked at the wall.",
            global_shapes=shapes,
            global_tells=tells,
            author_patterns=[],
        )
        assert result["clean"] is True
        assert result["hits"] == []

    def test_replacement_with_shape_fails(self, catalog) -> None:
        shapes, tells = catalog
        result = check_replacement(
            "The silence held.",
            global_shapes=shapes,
            global_tells=tells,
            author_patterns=[],
        )
        assert result["clean"] is False
        assert result["hits"][0]["category"] == "shape"

    def test_replacement_with_flagged_vocabulary_fails(self, catalog) -> None:
        shapes, tells = catalog
        result = check_replacement(
            "A nuanced silence followed.",
            global_shapes=shapes,
            global_tells=tells,
            author_patterns=[],
        )
        assert result["clean"] is False

    def test_hedge_or_dash_is_a_caution_not_a_failure(self, catalog) -> None:
        shapes, tells = catalog
        result = check_replacement(
            "He seemed tired — nothing more.",
            global_shapes=shapes,
            global_tells=tells,
            author_patterns=[],
        )
        assert result["clean"] is True
        kinds = {c["kind"] for c in result["cautions"]}
        assert {"hedge", "dash"} <= kinds

    def test_replacement_with_author_ban_fails(self, catalog) -> None:
        shapes, tells = catalog
        author = [
            BannedPattern(
                label="math",
                pattern=re.compile(r"\bmath\b", re.IGNORECASE),
                severity=SEVERITY_BLOCK,
                source="author donts",
            )
        ]
        result = check_replacement(
            "He did the math.",
            global_shapes=shapes,
            global_tells=tells,
            author_patterns=author,
        )
        assert result["clean"] is False
        assert result["hits"][0]["category"] == "author_rule"

    def test_invisible_character_in_replacement_fails(self, catalog) -> None:
        shapes, tells = catalog
        result = check_replacement(
            "Hid\u200bden.",
            global_shapes=shapes,
            global_tells=tells,
            author_patterns=[],
        )
        assert result["clean"] is False


class TestLoaders:
    def test_load_patterns_without_author_returns_empty_author_list(self) -> None:
        shapes, tells, author = load_patterns(PLUGIN_ROOT, author_slug=None)
        assert shapes and tells
        assert author == []

    def test_load_patterns_survives_unknown_author(self, isolated_home: Path) -> None:
        _, _, author = load_patterns(PLUGIN_ROOT, author_slug="nobody")
        assert author == []

    def test_author_dash_limit_read_from_profile_frontmatter(self, tmp_path: Path) -> None:
        author_dir = tmp_path / "ethan"
        author_dir.mkdir()
        (author_dir / "profile.md").write_text(
            "---\nname: Ethan\nem_dash_per_1k_limit: 9.5\n---\n\nBody.\n", encoding="utf-8"
        )
        assert load_author_dash_limit(author_dir) == 9.5

    def test_author_dash_limit_absent_returns_none(self, tmp_path: Path) -> None:
        author_dir = tmp_path / "ethan"
        author_dir.mkdir()
        (author_dir / "profile.md").write_text("---\nname: Ethan\n---\n", encoding="utf-8")
        assert load_author_dash_limit(author_dir) is None

    def test_author_dash_limit_missing_profile_returns_none(self, tmp_path: Path) -> None:
        assert load_author_dash_limit(tmp_path / "nope") is None

    @pytest.mark.parametrize("bad", ["abc", "-3", "0", "[1]"])
    def test_author_dash_limit_invalid_values_return_none(self, tmp_path: Path, bad: str) -> None:
        author_dir = tmp_path / "ethan"
        author_dir.mkdir()
        (author_dir / "profile.md").write_text(f"---\nem_dash_per_1k_limit: {bad}\n---\n", encoding="utf-8")
        assert load_author_dash_limit(author_dir) is None


class TestCatalogDoesNotBanDashes:
    """The hook and manuscript-checker auto-load every `**Banned shape:**` line
    as a per-occurrence warn. Dash handling is density-based (this module);
    a catalog regex for the dash would flag every single use."""

    def test_no_global_shape_matches_a_lone_em_dash(self, catalog) -> None:
        shapes, _ = catalog
        sample = "The house was quiet — too quiet."
        assert [p.label for p in shapes if p.pattern.search(sample)] == []
