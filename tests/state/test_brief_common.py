"""Unit tests for tools.state.brief_common.cap_canon_facts (Issue #506).

No dedicated test file existed for this function before — its ranking
behavior was only covered indirectly through review_brief/continuity_brief
integration tests. #506 identified a real-world failure mode (CHANGED facts
evicted newest-first under oldest_first truncation) that needs precise,
direct coverage of the ranking logic itself.
"""

from __future__ import annotations

import json
from typing import Any

from tools.state.brief_common import CANON_FACTS_CHAR_BUDGET, cap_canon_facts


def _changed_fact(chapter: int, fact_id: int, fact_text: str = "x") -> dict[str, Any]:
    return {
        "fact": fact_text,
        "subject": "s",
        "established_in": f"Ch {chapter}",
        "status": "CHANGED",
        "notes": "",
        "domain": "",
        "book_num": 1,
        "id": fact_id,
    }


def _active_fact(chapter: int) -> dict[str, Any]:
    return {
        "fact": "y",
        "subject": "s",
        "established_in": f"Ch {chapter}",
        "status": "ACTIVE",
        "notes": "",
        "domain": "",
        "book_num": 1,
    }


def _unattributed_fact(fact_text: str = "z") -> dict[str, Any]:
    return {
        "fact": fact_text,
        "subject": "s",
        "established_in": "",  # chapter_num() parses this to 0 — unattributed
        "status": "ACTIVE",
        "notes": "",
        "domain": "",
        "book_num": 1,
    }


def _wire_size(fact: dict[str, Any]) -> int:
    """Mirrors cap_group's own measurement on the wire-stripped form (id is
    sort-only and stripped before budget accounting) — matches exactly what
    cap_canon_facts will actually count against char_budget."""
    wire_fact = {k: v for k, v in fact.items() if k != "id"}
    return len(json.dumps(wire_fact)) + 1


class TestChangedFactsRankNewestFirstRegardlessOfOldestFirst:
    def test_changed_facts_rank_newest_chapter_first_under_oldest_first(self) -> None:
        """Issue #506 core repro: continuity_brief calls with oldest_first=True
        so ACTIVE facts protect early foundational canon — but that same
        flag was, before this fix, ALSO applied to CHANGED facts, evicting
        the newest (most likely to still need attention) revisions first
        under a tight budget. A budget that only fits one fact must
        keep the ch-31 revision, not the ch-4 one."""
        facts = [
            _changed_fact(4, fact_id=1),
            _changed_fact(31, fact_id=2),
        ]
        one_entry_size = _wire_size(facts[0]) + 1
        kept, truncated, total = cap_canon_facts(
            facts, oldest_first=True, char_budget=one_entry_size
        )
        assert truncated is True
        assert total == 2
        assert len(kept) == 1
        assert kept[0]["established_in"] == "Ch 31", (
            "the newest-chapter CHANGED fact must survive truncation, not the oldest"
        )

    def test_changed_facts_rank_newest_id_first_within_same_chapter(self) -> None:
        """The concrete #506 recheck evidence: 4 CHANGED facts recorded for
        the SAME chapter (31), the newest 2 got evicted because chapter
        ranking alone can't distinguish them and insertion order (oldest
        first from the DB) won by default. The id tiebreak must keep the
        two highest (most recently inserted) ids."""
        facts = [
            _changed_fact(31, fact_id=101, fact_text="oldest"),
            _changed_fact(31, fact_id=102, fact_text="second"),
            _changed_fact(31, fact_id=103, fact_text="third"),
            _changed_fact(31, fact_id=104, fact_text="newest"),
        ]
        budget_for_two = _wire_size(facts[0]) * 2 + 1
        kept, truncated, total = cap_canon_facts(
            facts, oldest_first=True, char_budget=budget_for_two
        )
        kept_texts = {f["fact"] for f in kept}
        assert truncated is True
        assert total == 4
        assert kept_texts == {"newest", "third"}, (
            "the two highest-id (most recently inserted) facts must survive, not the two oldest"
        )

    def test_changed_facts_same_created_at_second_still_break_tie_by_id(self) -> None:
        """Code review HIGH-1: created_at is SECOND-resolution
        (CURRENT_TIMESTAMP), so multiple revisions written in the same tool
        call/batch — the exact same-chapter cluster #506 is about —
        routinely collide on the same second. The tiebreak must use id
        (strictly monotonic, collision-free), not created_at, or it
        silently does nothing in the common batch-write case. Facts here
        carry no created_at at all, simulating that collision — id alone
        must still resolve the tie correctly."""
        facts = [
            _changed_fact(31, fact_id=1, fact_text="oldest"),
            _changed_fact(31, fact_id=2, fact_text="second"),
            _changed_fact(31, fact_id=3, fact_text="third"),
            _changed_fact(31, fact_id=4, fact_text="newest"),
        ]
        budget_for_two = _wire_size(facts[0]) * 2 + 1
        kept, truncated, total = cap_canon_facts(
            facts, oldest_first=True, char_budget=budget_for_two
        )
        kept_texts = {f["fact"] for f in kept}
        assert kept_texts == {"newest", "third"}

    def test_active_facts_unaffected_oldest_first_still_protects_early_canon(self) -> None:
        """The fix must be scoped to CHANGED facts only — ACTIVE facts (in
        the "rest" group) must keep their existing oldest_first behavior,
        since #506's own evidence found no problem there and the rationale
        (protect early foundational canon under a whole-manuscript scan)
        still holds."""
        facts = [_active_fact(4), _active_fact(31)]
        one_entry_size = _wire_size(facts[0]) + 1
        kept, truncated, total = cap_canon_facts(
            facts, oldest_first=True, char_budget=one_entry_size
        )
        assert truncated is True
        assert len(kept) == 1
        assert kept[0]["established_in"] == "Ch 4", (
            "ACTIVE facts must still protect the oldest/earliest chapter under oldest_first"
        )

    def test_changed_facts_unaffected_by_oldest_first_false_review_brief_path(self) -> None:
        """review_brief.py calls with oldest_first=False (per-chapter review,
        newest-chapter-first already the desired direction for everything).
        The fix must not change behavior for that caller beyond adding the
        id tiebreak — chapter-level newest-first was already correct."""
        facts = [_changed_fact(4, fact_id=1), _changed_fact(31, fact_id=2)]
        one_entry_size = _wire_size(facts[0]) + 1
        kept, truncated, total = cap_canon_facts(
            facts, oldest_first=False, char_budget=one_entry_size
        )
        assert len(kept) == 1
        assert kept[0]["established_in"] == "Ch 31"

    def test_missing_id_does_not_crash(self) -> None:
        """DB rows predating this fix, or any caller not threading id
        through, must not crash — missing id is a valid input."""
        fact = _changed_fact(1, fact_id=0)
        del fact["id"]
        kept, truncated, total = cap_canon_facts([fact], oldest_first=True)
        assert len(kept) == 1

    def test_non_numeric_id_does_not_crash(self) -> None:
        """Code review MEDIUM-1: a non-int id (e.g. a caller passing a
        string, or a future schema change) must degrade gracefully, not
        raise TypeError mid-sort — which would otherwise be swallowed by
        review_brief/continuity_brief's Recorder fallback into a brief with
        ZERO canon facts and truncated=True, silently hiding a real error
        as "nothing to see here"."""
        facts = [
            {**_changed_fact(1, fact_id=0), "id": "not-a-number"},
            _changed_fact(2, fact_id=5),
        ]
        kept, truncated, total = cap_canon_facts(facts, oldest_first=True)
        assert len(kept) == 2

    def test_non_int_castable_id_does_not_crash(self) -> None:
        """The int(...) guard catches TypeError, not just ValueError — a
        value that isn't even string-shaped (e.g. a list, from a future
        schema mistake) raises TypeError from int(), not ValueError. Only
        test_non_numeric_id_does_not_crash's plain string exercises
        ValueError; this exercises the other branch of the except clause."""
        facts = [
            {**_changed_fact(1, fact_id=0), "id": [1, 2]},
            _changed_fact(2, fact_id=5),
        ]
        kept, truncated, total = cap_canon_facts(facts, oldest_first=True)
        assert len(kept) == 2

    def test_output_never_leaks_id_field(self) -> None:
        """id is sort-only — never part of the documented output schema."""
        facts = [_changed_fact(1, fact_id=1), _active_fact(2)]
        kept, _truncated, _total = cap_canon_facts(facts)
        assert all("id" not in f for f in kept)


class TestChapterUnattributedFactsKeepPriority:
    def test_unattributed_fact_survives_under_oldest_first_with_saturated_changed_tier(
        self,
    ) -> None:
        """Code review HIGH-2: chapter-unattributed facts (chapter_num=0,
        heuristically migrated) share the priority tier with CHANGED facts.
        Before this fix, flipping CHANGED facts to newest-chapter-first
        (chapter_rank=chapter) put them in direct, silent competition with
        chapter 0's rank of -0 == 0 — on continuity_brief's real saturated
        Firelight case (21 CHANGED facts already filling the priority
        budget), every migrated chapter-0 fact got starved out entirely.
        Chapter-unattributed facts must keep first claim regardless."""
        unattributed = _unattributed_fact("MIGRATED-GLOBAL")
        changed = [_changed_fact(i, fact_id=i) for i in range(1, 11)]
        facts = [unattributed] + changed
        # Budget that fits the unattributed fact plus a few CHANGED ones,
        # but not all — the priority tier must be saturated for this to
        # actually exercise competition between the two rank dimensions.
        budget = _wire_size(unattributed) + _wire_size(changed[0]) * 3 + 1

        kept, truncated, total = cap_canon_facts(facts, oldest_first=True, char_budget=budget)

        kept_texts = {f["fact"] for f in kept}
        assert truncated is True
        assert "MIGRATED-GLOBAL" in kept_texts, (
            "chapter-unattributed facts must survive truncation even when the "
            "CHANGED tier's own budget is saturated"
        )

    def test_unattributed_fact_survives_under_oldest_first_false_too(self) -> None:
        """Same guarantee must hold regardless of oldest_first — the
        unattributed rank dimension is independent of it."""
        unattributed = _unattributed_fact("MIGRATED-GLOBAL")
        changed = [_changed_fact(i, fact_id=i) for i in range(1, 11)]
        facts = [unattributed] + changed
        budget = _wire_size(unattributed) + _wire_size(changed[0]) * 3 + 1

        kept, truncated, total = cap_canon_facts(facts, oldest_first=False, char_budget=budget)

        kept_texts = {f["fact"] for f in kept}
        assert "MIGRATED-GLOBAL" in kept_texts


class TestCapCanonFactsBasics:
    """Baseline regression coverage — this function had none before #506."""

    def test_empty_input_returns_empty(self) -> None:
        kept, truncated, total = cap_canon_facts([])
        assert kept == []
        assert truncated is False
        assert total == 0

    def test_no_truncation_when_under_budget(self) -> None:
        facts = [_active_fact(1), _changed_fact(2, fact_id=1)]
        kept, truncated, total = cap_canon_facts(facts, char_budget=CANON_FACTS_CHAR_BUDGET)
        assert len(kept) == 2
        assert truncated is False
        assert total == 2

    def test_current_book_num_ranks_above_chapter(self) -> None:
        facts = [
            {**_active_fact(99), "book_num": 1},
            {**_active_fact(1), "book_num": 2},
        ]
        one_entry_size = _wire_size(facts[0]) + 1
        kept, truncated, total = cap_canon_facts(
            facts, current_book_num=2, char_budget=one_entry_size
        )
        assert len(kept) == 1
        assert kept[0]["book_num"] == 2
