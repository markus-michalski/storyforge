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

    oldest_first never affects the CHANGED-facts ranking within the priority
    tier (Issue #506 failure mode 1) — a CHANGED fact is a revision audit
    trail, and the newest revision (often a supersession notice invalidating
    an older one) is the one most likely to need author/tool attention,
    regardless of whether the caller is protecting early ACTIVE canon.
    CHANGED facts always rank newest-chapter-first within their tier. The
    chapter-unattributed facts sharing that tier keep their pre-existing,
    oldest_first-dependent position relative to CHANGED facts (first when
    oldest_first=True, last when oldest_first=False) — unaffected by this.

    On a 34-chapter book (Firelight), the unbounded fact list was 932 entries
    / 285K chars and blew the MCP tool output limit outright (Issue #500).
    This bounds that to a fixed ceiling and reports what happened via the
    returned ``truncated`` flag, instead of silently degrading.

    Returns (capped_facts, truncated, total_count).
    """
    if char_budget is None:
        char_budget = CANON_FACTS_CHAR_BUDGET

    total_count = len(facts)
    if not facts:
        return [], False, total_count

    def _sort_key(
        fact: dict[str, Any], *, force_newest_first: bool = False,
    ) -> tuple[bool, bool, bool, int]:
        is_current_book = current_book_num is None or fact.get("book_num") == current_book_num
        chapter = chapter_num(fact)
        at_or_before_current = current_chapter_num is None or chapter <= current_chapter_num
        # chapter 0 = heuristically migrated, no chapter attribution. Under
        # oldest_first=True (continuity_brief), the sign trick already put
        # these facts first before this fix existed — chapter_rank=0 is the
        # largest of the negated per-chapter values. force_newest_first=True
        # (this tier's Issue #506 fix) flips CHANGED facts' chapter_rank to
        # positive, which would flip chapter-0 to LAST instead (0 is now the
        # smallest), silently evicting the "always in scope" facts. Restored
        # explicitly here, scoped to oldest_first=True only — oldest_first=
        # False (review_brief) already ranked chapter-0 last in this tier
        # before force_newest_first existed and stays byte-for-byte
        # unchanged; broadening this to fire for oldest_first=False too
        # would be an undocumented, untested scope expansion beyond #506.
        unattributed_first = oldest_first and chapter == 0
        use_oldest_first = oldest_first and not force_newest_first
        chapter_rank = -chapter if use_oldest_first else chapter
        return (is_current_book, at_or_before_current, unattributed_first, chapter_rank)

    priority = [
        f for f in facts
        if f.get("status") == "CHANGED" or chapter_num(f) == 0
    ]
    rest = [
        f for f in facts
        if f.get("status") != "CHANGED" and chapter_num(f) != 0
    ]

    priority_sorted = sorted(
        priority, key=lambda f: _sort_key(f, force_newest_first=True), reverse=True,
    )
    rest_sorted = sorted(rest, key=_sort_key, reverse=True)

    kept_priority, priority_truncated = cap_group(priority_sorted, char_budget)
    kept_rest, rest_truncated = cap_group(rest_sorted, char_budget)

    kept = kept_priority + kept_rest
    truncated = priority_truncated or rest_truncated or len(kept) < total_count
    return kept, truncated, total_count
