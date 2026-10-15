"""Tests for the voice candidate engine — Epic #663 / Issue #667."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.analysis.voice_candidates import (
    DEFAULT_MIN_CHAPTERS,
    DEFAULT_MIN_WEIGHT,
    SOURCE_WEIGHTS,
    build_voice_candidates,
)

ROOT = Path(__file__).resolve().parents[2]

_next_id = iter(range(1, 10_000))


def row(
    *,
    dimension: str = "sentence_rhythm",
    direction: str = "shorter",
    chapter: str = "01",
    book: str = "firelight",
    genres: str = "dark-fantasy,lgbtq",
    category: str = "fiction",
    source: str = "reviewer",
    decision: str = "accepted",
    status: str = "classified",
    rule: str = "Prefer shorter sentences.",
) -> dict:
    return {
        "id": next(_next_id),
        "author_slug": "ethan-cole",
        "book_slug": book,
        "chapter_slug": chapter,
        "book_category": category,
        "genres": genres,
        "source_skill": source,
        "decision": decision,
        "dimension": dimension,
        "direction": direction,
        "normalized_rule": rule,
        "status": status,
    }


def evidence(n: int, **kw) -> list[dict]:
    """n rows spread over n distinct chapters."""
    return [row(chapter=f"{i:02d}", **kw) for i in range(1, n + 1)]


def build(rows, **kw):
    return build_voice_candidates(rows, plugin_root=ROOT, **kw)


class TestThreshold:
    def test_defaults(self):
        assert DEFAULT_MIN_WEIGHT == 3.0
        assert DEFAULT_MIN_CHAPTERS == 2

    def test_three_entries_in_three_chapters_make_a_candidate(self):
        result = build(evidence(3))
        assert len(result["candidates"]) == 1
        c = result["candidates"][0]
        assert (c["dimension"], c["direction"]) == ("sentence_rhythm", "shorter")
        assert c["weight"] == 3.0
        assert c["chapter_count"] == 3
        assert c["evidence_count"] == 3

    def test_two_entries_are_not_enough(self):
        assert build(evidence(2))["candidates"] == []

    def test_weight_enough_but_single_chapter_is_not_enough(self):
        rows = [row(chapter="01") for _ in range(4)]
        assert build(rows)["candidates"] == []

    def test_chapters_are_counted_per_book(self):
        rows = [row(chapter="01", book="a"), row(chapter="01", book="b"), row(chapter="02", book="b")]
        assert len(build(rows)["candidates"]) == 1

    def test_pending_rows_do_not_count(self):
        rows = evidence(2) + [row(chapter="03", status="pending", dimension=None, direction=None)]
        result = build(rows)
        assert result["candidates"] == []
        assert result["unclassified"] == 1

    def test_thresholds_are_configurable(self):
        assert len(build(evidence(2), min_weight=2.0)["candidates"]) == 1


class TestWeighting:
    def test_source_weights(self):
        assert SOURCE_WEIGHTS["reviewer"] == 1.0
        assert SOURCE_WEIGHTS["fixer"] == 1.0
        assert SOURCE_WEIGHTS["humanizer"] == 0.5
        assert SOURCE_WEIGHTS["proofreader"] == 0.25

    def test_humanizer_entries_weigh_half(self):
        assert build(evidence(4, source="humanizer"))["candidates"] == []
        assert build(evidence(6, source="humanizer"))["candidates"][0]["weight"] == 3.0

    def test_proofreader_alone_needs_twelve_entries(self):
        assert build(evidence(11, source="proofreader"))["candidates"] == []
        assert len(build(evidence(12, source="proofreader"))["candidates"]) == 1

    def test_rejected_decisions_count_like_accepted_ones(self):
        rows = evidence(3, decision="rejected")
        assert build(rows)["candidates"][0]["weight"] == 3.0


class TestScope:
    def test_single_genre_set_gives_genre_scoped_candidate(self):
        c = build(evidence(3, genres="dark-fantasy,lgbtq"))["candidates"][0]
        assert c["scope"] == {"universal": False, "genres": ["dark-fantasy", "lgbtq"]}

    def test_shared_genre_across_books_is_the_intersection(self):
        rows = [
            row(chapter="01", book="a", genres="dark-romance,lgbtq"),
            row(chapter="02", book="a", genres="dark-romance,lgbtq"),
            row(chapter="01", book="b", genres="dark-romance,thriller"),
        ]
        c = build(rows)["candidates"][0]
        assert c["scope"] == {"universal": False, "genres": ["dark-romance"]}

    def test_disjoint_genres_make_it_universal(self):
        rows = [
            row(chapter="01", book="a", genres="dark-romance"),
            row(chapter="02", book="a", genres="dark-romance"),
            row(chapter="01", book="b", genres="dark-comedy"),
        ]
        c = build(rows)["candidates"][0]
        assert c["scope"] == {"universal": True, "genres": []}

    def test_entries_without_genres_are_universal(self):
        c = build(evidence(3, genres=""))["candidates"][0]
        assert c["scope"]["universal"] is True

    def test_memoir_and_fiction_are_never_mixed(self):
        rows = evidence(2) + [row(chapter="03", category="memoir", genres="")]
        assert build(rows)["candidates"] == []
        memoir = evidence(3, category="memoir", genres="", dimension="hedging",
                          direction="less", rule="No hedging.")
        c = build(memoir)["candidates"][0]
        assert c["book_category"] == "memoir"
        assert c["scope"]["universal"] is True


class TestConflicts:
    def test_opposite_directions_in_overlapping_scope_are_a_conflict(self):
        rows = evidence(3, direction="shorter") + [
            row(chapter="09", direction="longer", rule="Longer sentences.")
        ]
        result = build(rows)
        assert result["candidates"] == []
        assert len(result["conflicts"]) == 1
        conflict = result["conflicts"][0]
        assert conflict["dimension"] == "sentence_rhythm"
        assert {s["direction"] for s in conflict["sides"]} == {"shorter", "longer"}

    def test_disjoint_scopes_are_not_a_conflict(self):
        rows = evidence(3, direction="shorter", genres="dark-romance", book="a") + [
            row(chapter=f"{i:02d}", direction="longer", genres="dark-comedy", book="b")
            for i in range(1, 4)
        ]
        result = build(rows)
        assert result["conflicts"] == []
        assert {c["direction"] for c in result["candidates"]} == {"shorter", "longer"}

    def test_weak_opposite_below_threshold_with_no_strong_side_is_no_conflict(self):
        rows = [row(chapter="01", direction="shorter"), row(chapter="02", direction="longer")]
        result = build(rows)
        assert result["conflicts"] == []
        assert result["candidates"] == []

    def test_unrelated_directions_do_not_conflict(self):
        rows = evidence(3, direction="shorter") + evidence(
            3, dimension="simile_density", direction="fewer", rule="Fewer similes."
        )
        result = build(rows)
        assert result["conflicts"] == []
        assert len(result["candidates"]) == 2


class TestSuppression:
    def test_discarded_candidate_needs_double_the_evidence(self):
        discarded = [row(chapter=f"{i:02d}", status="discarded") for i in range(1, 4)]
        fresh3 = evidence(3, book="b")
        assert build(discarded + fresh3[:0])["candidates"] == []
        # open evidence equal to the discarded weight is enough again
        assert len(build(discarded + fresh3)["candidates"]) == 1

    def test_less_open_evidence_than_discarded_stays_suppressed(self):
        discarded = [row(chapter=f"{i:02d}", status="discarded") for i in range(1, 6)]
        open_rows = evidence(3, book="b")
        result = build(discarded + open_rows)
        assert result["candidates"] == []
        assert result["suppressed"] == 1

    def test_discarded_other_direction_does_not_suppress(self):
        discarded = [row(chapter=f"{i:02d}", direction="longer", status="discarded")
                     for i in range(1, 6)]
        assert len(build(discarded + evidence(3))["candidates"]) == 1

    def test_harvested_weight_is_reported_not_suppressed(self):
        harvested = [row(chapter=f"{i:02d}", status="harvested") for i in range(1, 4)]
        c = build(harvested + evidence(3, book="b"))["candidates"][0]
        assert c["harvested_weight"] == 3.0


class TestTargetSection:
    def test_prefer_goes_to_style_principles(self):
        assert build(evidence(3))["candidates"][0]["target_section"] == "style_principles"

    def test_avoid_goes_to_donts(self):
        rows = evidence(3, dimension="simile_density", direction="fewer", rule="Fewer similes.")
        assert build(rows)["candidates"][0]["target_section"] == "donts"

    def test_prefer_kept_against_proposals_is_a_recurring_tic(self):
        rows = evidence(3, decision="rejected", dimension="sentence_rhythm",
                        direction="more_fragments", rule="Keep fragments.")
        assert build(rows)["candidates"][0]["target_section"] == "recurring_tics"

    def test_avoid_with_rejections_stays_donts(self):
        rows = evidence(3, decision="rejected", dimension="simile_density",
                        direction="fewer", rule="Fewer similes.")
        assert build(rows)["candidates"][0]["target_section"] == "donts"


class TestCandidateContent:
    def test_most_common_rule_wins_and_ties_prefer_latest(self):
        rows = [
            row(chapter="01", rule="Shorter."),
            row(chapter="02", rule="Prefer shorter sentences."),
            row(chapter="03", rule="Prefer shorter sentences."),
        ]
        assert build(rows)["candidates"][0]["normalized_rule"] == "Prefer shorter sentences."

    def test_evidence_ids_and_books(self):
        rows = evidence(3)
        c = build(rows)["candidates"][0]
        assert c["evidence_ids"] == [r["id"] for r in rows]
        assert c["books"] == ["firelight"]
        assert c["kind"] == "prefer"

    def test_sorted_by_weight_descending(self):
        rows = evidence(3) + evidence(5, dimension="simile_density", direction="fewer",
                                      rule="Fewer similes.")
        dims = [c["dimension"] for c in build(rows)["candidates"]]
        assert dims == ["simile_density", "sentence_rhythm"]

    def test_deterministic(self):
        rows = evidence(3) + evidence(4, dimension="pacing", direction="faster", rule="Faster.")
        assert build(rows) == build(list(reversed(rows)))

    def test_rows_with_unknown_vocabulary_are_skipped_and_counted(self):
        rows = evidence(3) + [row(dimension="renamed_dimension", direction="x", chapter="09")]
        result = build(rows)
        assert result["skipped_unknown"] == 1
        assert len(result["candidates"]) == 1

    def test_input_rows_are_not_mutated(self):
        rows = evidence(3)
        snapshot = [dict(r) for r in rows]
        build(rows)
        assert rows == snapshot

    def test_empty_input(self):
        result = build([])
        assert result == {
            "candidates": [], "conflicts": [], "suppressed": 0,
            "unclassified": 0, "skipped_unknown": 0,
        }


def test_invalid_thresholds_raise():
    with pytest.raises(ValueError):
        build([], min_weight=0)
    with pytest.raises(ValueError):
        build([], min_chapters=0)
