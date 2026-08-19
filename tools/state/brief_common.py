"""Shared brief-truncation helpers — Issue #505.

``review_brief.py`` and ``continuity_brief.py`` both assemble structured
JSON briefs and share the same size-bounding problem: an unbounded
canon-facts list is structurally guaranteed to blow the MCP tool output
limit on a long book (Issue #500 — 285K chars measured; #501 extended the
same fix to ``continuity_brief.py``).

This module holds that shared logic under PUBLIC names, so a second/third
consumer no longer has to reach into ``review_brief.py``'s ``_``-prefixed
"private" API (Issue #505). ``review_brief.py`` re-exports ``Recorder`` and
``cap_canon_facts`` under their old private aliases (``_Recorder``,
``_cap_canon_facts``) for its own internal use and for existing test
imports — the other symbols here (``cap_group``, ``chapter_num``,
``CANON_FACTS_CHAR_BUDGET``, ``ESTABLISHED_IN_NUM_RE``) moved without an
alias, since nothing outside this module needed them directly. This module
is the source of truth now, not ``review_brief.py`` — code that needs any of
these symbols should import from here, not from ``review_brief``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Error recorder (mirrors chapter_writing_brief._Recorder, which keeps its
# own independent copy — that assembler never reached into review_brief.py's
# private API, so it's out of scope for #505)
# ---------------------------------------------------------------------------


@dataclass
class Recorder:
    """Collects sub-tool errors so the brief can ship with partial data."""

    errors: list[dict[str, str]]

    def run(self, component: str, fn, default):
        try:
            return fn()
        except Exception as exc:  # pylint: disable=broad-except
            self.errors.append(
                {
                    "component": component,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            return default


# ---------------------------------------------------------------------------
# Canon-facts size cap (Issue #500, #501)
# ---------------------------------------------------------------------------

CANON_FACTS_CHAR_BUDGET = 40_000  # applied independently to two groups (priority + rest) — worst case ~2x
ESTABLISHED_IN_NUM_RE = re.compile(r"\d+")


def chapter_num(fact: dict[str, Any]) -> int:
    m = ESTABLISHED_IN_NUM_RE.search(fact.get("established_in", "") or "")
    return int(m.group()) if m else 0


def cap_group(
    items_sorted: list[dict[str, Any]],
    char_budget: int,
) -> tuple[list[dict[str, Any]], bool]:
    """Keep items (already priority-sorted) up to char_budget wire-size chars.

    Measures with default json.dumps (ensure_ascii=True) — the same encoding
    the MCP router uses to serialize the response — so the budget reflects
    actual wire size rather than undercounting non-ASCII text (Issue #500).
    """
    kept: list[dict[str, Any]] = []
    used = 0
    for item in items_sorted:
        entry_size = len(json.dumps(item)) + 1
        if used + entry_size > char_budget:
            return kept, True
        kept.append(item)
        used += entry_size
    return kept, False


def cap_canon_facts(
    facts: list[dict[str, Any]],
    *,
    current_book_num: int | None = None,
    current_chapter_num: int | None = None,
    char_budget: int | None = None,
    oldest_first: bool = False,
) -> tuple[list[dict[str, Any]], bool, int]:
    """Bound canon_log_facts to a char budget, dropping low-priority facts first.

    char_budget defaults to the module-level ``CANON_FACTS_CHAR_BUDGET``,
    read at call time (not bound as a parameter default) so tests can
    monkeypatch the module constant directly.

    Unlike domain filtering, this never assumes an entire category of fact is
    safe to drop — it prioritizes instead:

    1. CHANGED-status facts and chapter-unattributed facts (``chapter_num=0``,
       heuristically migrated — ``tools/state/loaders/canon_brief.py`` treats
       these as "always in scope", mirrored here) get first claim on the
       budget.
    2. Everything else (ACTIVE facts with a known chapter) fills the
       remaining budget.

    Both groups are capped against their OWN char_budget independently — a
    firm ceiling of roughly 2x char_budget total, rather than letting group 1
    alone (e.g. a book with thousands of revisions) grow unbounded while
    ``truncated`` misreports ``False`` because nothing in group 2 had to be
    dropped.

    Within each group, facts are ranked current-book-first, then facts
    established at or before the chapter under review, then newest-chapter-
    first. The middle tier matters: a reviewer checking chapter 5 can only be
    contradicted by facts from chapters 1-5, not by facts established later
    in the book — ranking purely by "newest chapter" would show chapter 5's
    reviewer the least relevant facts (chapters near the end) first and
    silently truncate away the ones it could actually conflict with.

    current_book_num, when given, ranks facts from THIS book above facts
    inherited from earlier books in a series — ``canon_log_facts`` includes
    the whole series' history (query_facts includes all book_num < current),
    and ranking by chapter_num alone is book-blind: chapter 34 of book 1
    would outrank chapter 2 of the book actually being reviewed, starving it
    of its own canon under a tight budget. Pass None to skip this ranking
    (e.g. for a standalone book with no series context).

    current_chapter_num, when given, ranks at-or-before-this-chapter facts
    above later ones for the reasons above. Pass None to skip (falls back to
    pure newest-chapter-first, e.g. if the chapter slug couldn't be parsed).

    oldest_first inverts the within-group chapter ranking to earliest-chapter-
    first instead of newest-chapter-first. Callers with a single "current
    chapter" to protect against (``review_brief``, ``current_chapter_num``
    set) want newest-first — that chapter can only be contradicted by facts
    established at or before it, and among those the closest ones are most
    relevant. A whole-manuscript caller with no such anchor (``continuity_brief``,
    ``current_chapter_num=None``) has the opposite problem: falling back to
    newest-first there would systematically keep only late-book facts and
    truncate away the early, foundational canon (traits, geography, world
    rules) that late chapters are most likely to accidentally contradict.
    Pass True for that case. Has no effect on ``current_book_num`` ranking.

    CHANGED-status facts are exempt from ``oldest_first`` (Issue #506): a
    revision's whole point is that it superseded something, so under a
    tight budget the NEWEST revision is the one most likely to still need
    author/tool attention — the opposite of the foundational-canon
    rationale ``oldest_first`` exists for on ACTIVE facts. CHANGED facts
    always rank newest-chapter-first, then highest-``id``-first (DB
    insertion order — see ``tools/db/brief_helpers.py::_db_row_to_legacy_fact``
    for why ``id`` and not ``created_at``) as a same-chapter tiebreak
    (missing/non-numeric ``id`` sorts last within a tie, never crashes),
    regardless of what ``oldest_first`` is set to. Chapter-unattributed
    facts (``chapter_num=0``) are ranked separately from this — they keep
    first claim on the priority-tier budget regardless of ``oldest_first``
    or CHANGED status, so the CHANGED-tier's rank-direction flip can't
    starve them (code review finding on #506: chapter 0's rank of ``-0 ==
    0`` used to tie/lose against the flipped CHANGED ranks).

    On a 34-chapter book (Firelight), the unbounded fact list was 932 entries
    / 285K chars and blew the MCP tool output limit outright (Issue #500).
    This bounds that to a fixed ceiling and reports what happened via the
    returned ``truncated`` flag, instead of silently degrading.

    Returns (capped_facts, truncated, total_count). The returned facts are
    shallow copies of the input dicts (id-stripping requires copying), not
    the same objects — mutating a returned fact does not affect the input.
    """
    if char_budget is None:
        char_budget = CANON_FACTS_CHAR_BUDGET

    total_count = len(facts)
    if not facts:
        return [], False, total_count

    def _sort_key(fact: dict[str, Any]) -> tuple[bool, bool, bool, int, int]:
        is_current_book = current_book_num is None or fact.get("book_num") == current_book_num
        chapter = chapter_num(fact)
        at_or_before_current = current_chapter_num is None or chapter <= current_chapter_num
        # Chapter-unattributed facts (chapter_num=0) keep first claim on the
        # priority tier as their own rank dimension, independent of
        # oldest_first/CHANGED-direction below (code review finding on
        # #506) — without this, chapter 0's rank collapses to -0 == 0 and
        # silently competes with (and can lose to) the CHANGED tier's
        # newest-first ranks instead of always winning.
        is_unattributed = chapter == 0
        if fact.get("status") == "CHANGED":
            # Issue #506: oldest_first's rationale (protect early
            # foundational canon under truncation) is built for ACTIVE
            # facts and actively backfires on CHANGED facts — a revision's
            # whole point is that it superseded something, so the NEWEST
            # one is the one still needing author/tool attention (real
            # case: a supersession notice on the newest of four same-
            # chapter revisions was evicted in favor of the three older
            # ones). CHANGED facts therefore always rank newest-chapter-
            # first, then highest-id-first (DB insertion order) as a
            # same-chapter tiebreak, regardless of oldest_first.
            chapter_rank = chapter
            try:
                fact_id = int(fact.get("id") or 0)
            except (TypeError, ValueError):
                fact_id = 0
        else:
            chapter_rank = -chapter if oldest_first else chapter
            fact_id = 0
        return (is_current_book, at_or_before_current, is_unattributed, chapter_rank, fact_id)

    priority = [
        f for f in facts
        if f.get("status") == "CHANGED" or chapter_num(f) == 0
    ]
    rest = [
        f for f in facts
        if f.get("status") != "CHANGED" and chapter_num(f) != 0
    ]

    priority_sorted = sorted(priority, key=_sort_key, reverse=True)
    rest_sorted = sorted(rest, key=_sort_key, reverse=True)

    # id is sort-only (Issue #506's same-chapter CHANGED tiebreak) — never
    # part of the documented output schema and never wire-measured.
    # Stripped here, after sorting but before cap_group's size accounting,
    # so a fact carrying it doesn't cost more budget than an identical fact
    # that doesn't (and doesn't leak an undocumented field to callers).
    # Must happen before cap_group, not after: measuring the inflated dict
    # and stripping afterward would make cap_group drop more facts than
    # actually fit.
    priority_sorted = [{k: v for k, v in f.items() if k != "id"} for f in priority_sorted]
    rest_sorted = [{k: v for k, v in f.items() if k != "id"} for f in rest_sorted]

    kept_priority, priority_truncated = cap_group(priority_sorted, char_budget)
    kept_rest, rest_truncated = cap_group(rest_sorted, char_budget)

    kept = kept_priority + kept_rest
    truncated = priority_truncated or rest_truncated or len(kept) < total_count
    return kept, truncated, total_count
