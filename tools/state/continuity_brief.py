"""Continuity brief assembler — Issue #100.

Bundles canonical_calendar, travel_matrix, canon_log_facts,
character_index, and chapter_timelines into one structured JSON brief.

Chapter draft texts are intentionally NOT included — they are the data
being checked, not project-state metadata (ADR-0001: data-briefs-over-
prompt-instructions).

Design follows ``chapter_writing_brief.py`` (Issue #78).

Size bounding (Issue #504, follow-up to #500/#501): ``canon_log_facts``,
``chapter_timelines``, and ``canonical_calendar`` are all size-capped — the
fields that scale with book length (revision count, chapter count, story-day
count) rather than with a roughly-fixed per-book quantity. Their combined
WORST CASE is bounded to ~40,000 chars (canon_log_facts's own worst case is
2x its budget — it caps two priority groups independently, see
_cap_canon_facts()'s docstring — so 10,000 * 2 + 10,000 + 10,000 = 40,000),
comfortably under the ~50K real MCP output limit this repo already
documents and enforces on the sibling ``get_canon_brief`` tool
(tests/state/test_canon_brief.py's <45,000-char assertion) — see the budget
constants below for the full math. Measured on the real Firelight project
(34 chapters, the #500 reference case, current budgets): total assembled
brief was 19,076 wire chars, canon_log_facts alone accounting for 12,009 of
those (936 facts truncated down to 51) and chapter_timelines for 5,132 (34
of 34 chapters, not truncated at this budget). ``canonical_calendar``
measured 2 chars on that project (its plot/timeline.md has no events
recorded yet) — that's absence of data, not evidence of smallness, so it's
capped defensively too rather than left unbounded on an unverified
assumption; see the per-entry budget comment below for why the budget
itself isn't empirically pinned the way the other two are.
``character_index`` (859 chars / 10 characters) and ``character_snapshots``
(677 chars / 1 snapshot) were left unbounded — entry *count* is small and
structurally bounded by cast size, though per-entry free text
(description/injuries/etc.) is not itself size-limited. Accepted as a real
but low-probability risk (YAGNI) rather than adding budget machinery on top
of already-small, naturally-bounded-by-count fields.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.analysis.timeline_validator import parse_plot_timeline
from tools.db.brief_helpers import load_canon_facts_for_brief
from tools.db.character_snapshots import get_all_latest_snapshots
from tools.db.connection import get_book_num, get_db_slug_for_book, open_canon_db
from tools.state.brief_common import (
    Recorder as _Recorder,
    cap_canon_facts as _cap_canon_facts,
    cap_group as _cap_group,
)
from tools.state.chapter_timeline_parser import parse_chapter_timeline_grid
from tools.state.parsers import parse_frontmatter
from tools.state.review_brief import _CHAPTER_NUM_RE, _parse_travel_matrix
from tools.state import brief_common as _brief_common_module

# Quarter of review_brief's char budget (Issue #504 review finding F2 —
# originally a half, tightened further): this brief carries THREE capped
# fields on top of each other (canon_log_facts, chapter_timelines,
# canonical_calendar), each capped independently, so their worst cases add
# up. cap_canon_facts() applies its budget to TWO groups independently
# (priority + rest — see its docstring), so canon_log_facts's real worst
# case is 2x this constant: 40_000 // 4 = 10_000 per group = 20_000 worst
# case. Combined with the other two fields' budgets below (10_000 each),
# worst-case total for all three capped fields is 40_000 — comfortably under
# the ~50K real MCP output limit this repo already documents and enforces
# elsewhere (tests/state/test_canon_brief.py's <45_000 assertion on the
# sibling get_canon_brief tool), leaving headroom for the small uncapped
# fields (character_index, character_snapshots).
_CANON_FACTS_BUDGET_DIVISOR = 4

# Issue #504: unlike canon_log_facts, chapter_timelines has no CHANGED/ACTIVE
# priority split — every chapter matters equally, so this is a single
# cap_group() pass, not the two-tier cap_canon_facts() logic. Measured on the
# real Firelight project (34 chapters): ~151 chars/chapter, so this budget
# gives headroom for ~65 chapters before truncation ever triggers. Sized
# down from an initial 20_000 (see _CANON_FACTS_BUDGET_DIVISOR comment above
# for why) — still generous for the vast majority of real books, and a
# truncated continuity scan that reports what it dropped beats one that
# risks blowing the MCP output limit outright.
_CHAPTER_TIMELINES_CHAR_BUDGET = 10_000

# Issue #504: canonical_calendar is one entry per story-day with a free-text
# key_events field — scales with book length the same way chapter_timelines
# does. No real project with plot/timeline.md events was available to
# measure a per-entry size against, so this budget is not empirically pinned
# the way the other two are — set to match chapter_timelines's budget as a
# reasonable default pending a real measurement.
_CANONICAL_CALENDAR_CHAR_BUDGET = 10_000


# ---------------------------------------------------------------------------
# Character index builder
# ---------------------------------------------------------------------------


def _build_character_index(book_root: Path) -> list[dict[str, str]]:
    """Load all character files and return a flat index.

    Returns a list of dicts with ``slug``, ``name``, ``role``,
    ``description`` keys. INDEX.md is excluded.
    """
    chars_dir = book_root / "characters"
    if not chars_dir.is_dir():
        return []

    index: list[dict[str, str]] = []
    for path in sorted(chars_dir.iterdir()):
        if path.suffix.lower() != ".md" or path.name.upper() == "INDEX.MD":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, _body = parse_frontmatter(text)
        index.append(
            {
                "slug": path.stem,
                "name": str(meta.get("name", path.stem)),
                "role": str(meta.get("role", "supporting")),
                "description": str(meta.get("description", "")),
            }
        )

    return index


# ---------------------------------------------------------------------------
# All-chapter timelines (no review-rank filter — continuity needs all)
# ---------------------------------------------------------------------------


def _get_all_chapter_timelines(book_root: Path) -> list[dict[str, Any]]:
    """Return timeline grids for ALL chapters regardless of status.

    Unlike ``get_recent_chapter_timelines``, this imposes no review-rank
    filter — continuity-checker scans the full manuscript, including
    drafts and outline-stage chapters.
    """
    chapters_dir = book_root / "chapters"
    if not chapters_dir.is_dir():
        return []

    numbered: list[tuple[int, Path]] = []
    for entry in chapters_dir.iterdir():
        if not entry.is_dir():
            continue
        m = _CHAPTER_NUM_RE.match(entry.name)
        if not m:
            continue
        numbered.append((int(m.group(1)), entry))
    numbered.sort(key=lambda pair: pair[0])

    grids: list[dict[str, Any]] = []
    for _, chapter_dir in numbered:
        grid = parse_chapter_timeline_grid(chapter_dir)
        if grid is not None:
            grids.append(grid.to_dict())
    return grids


# ---------------------------------------------------------------------------
# Public assembler
# ---------------------------------------------------------------------------


def build_continuity_brief(
    *,
    book_root: Path,
    book_slug: str,
) -> dict[str, Any]:
    """Assemble the continuity-checker brief — Issue #100.

    Bundles canonical_calendar, travel_matrix, canon_log_facts,
    character_index, and chapter_timelines into a single
    JSON-serializable dict. ``continuity-checker`` calls this once
    instead of reading timeline/setting/canon/character files by hand.

    Chapter draft texts are intentionally excluded — they are the data
    being checked, not project-state metadata (ADR-0001).

    Args:
        book_root: Absolute path to the book project directory.
        book_slug: Book identifier.

    Returns dict with:
        book_slug            — echoes the book_slug argument
        canonical_calendar   — parsed plot/timeline.md events, size-bounded
                                earliest-story-day-first (Issue #504) — see
                                canonical_calendar_truncated/_total_count below
        canonical_calendar_truncated — True if canonical_calendar was capped for size
        canonical_calendar_total_count — untruncated event count (== len(canonical_calendar)
                                when not truncated)
        travel_matrix        — parsed world/setting.md Travel Matrix rows
        canon_log_facts      — established facts from the canon DB, size-bounded
                                the same way as get_review_brief but at a quarter
                                of the budget (Issue #500/#501/#504). Ranking when
                                capped is fact-kind-dependent, not one uniform
                                direction (Issue #506) — see
                                brief_common.cap_canon_facts's own docstring for
                                the authoritative rule (also referenced by the
                                ``canon_log_facts, size-capped`` code comment
                                below), and canon_log_facts_truncated/
                                _total_count below
        canon_log_facts_truncated — True if canon_log_facts was capped for size
        canon_log_facts_total_count — untruncated fact count (== len(canon_log_facts)
                                when not truncated)
        character_index      — all character files as flat list. Unbounded —
                                entry count is small and bounded by cast size,
                                though per-entry description text is not
                                itself size-limited (Issue #504)
        chapter_timelines    — timeline grids for chapters that have a
                                parseable grid (any status), size-bounded
                                earliest-chapter-first (Issue #504) — see
                                chapter_timelines_truncated/_total_count below
        chapter_timelines_truncated — True if chapter_timelines was capped for size
        chapter_timelines_total_count — count of chapters with a parseable
                                timeline grid before capping (== len(chapter_timelines)
                                when not truncated) — NOT the total chapter count,
                                chapters without a parseable grid are excluded upstream
        character_snapshots  — latest per-character state from the
                                character_snapshots DB table (Issue #281).
                                Unbounded — entry count is small and bounded by
                                cast size, though per-entry state text is not
                                itself size-limited (Issue #504)
        errors               — component → error map for graceful degrade
    """
    recorder = _Recorder(errors=[])

    # ----- canonical calendar, size-capped (#504) ----------------------------
    # One entry per story-day with a free-text key_events field
    # (CalendarEvent.to_dict(), tools/analysis/timeline_validator.py) — this
    # scales with book length the same way chapter_timelines does, not with a
    # roughly-fixed per-book quantity, so it gets the same defensive cap
    # rather than being left unbounded on the (wrong) assumption that it's
    # inherently small. Sorted by story_day ascending before capping — parsed
    # row order isn't guaranteed to already be chronological — so truncation
    # keeps the EARLIEST story days first, same rationale as chapter_timelines.
    canonical_calendar_raw: list[dict[str, Any]] = []
    calendar = recorder.run(
        "canonical_calendar",
        lambda: parse_plot_timeline(book_root),
        None,
    )
    if calendar is not None:
        canonical_calendar_raw = sorted(
            (e.to_dict() for e in calendar.events), key=lambda e: e["story_day"]
        )
    canonical_calendar, canonical_calendar_truncated = recorder.run(
        "canonical_calendar_cap",
        lambda: _cap_group(canonical_calendar_raw, _CANONICAL_CALENDAR_CHAR_BUDGET),
        ([], True),
    )
    canonical_calendar_total_count = len(canonical_calendar_raw)

    # ----- travel matrix ----------------------------------------------------
    travel_matrix: list[dict[str, str]] = []
    setting_path = book_root / "world" / "setting.md"
    if setting_path.is_file():
        setting_text = recorder.run(
            "setting.read",
            lambda: setting_path.read_text(encoding="utf-8"),
            "",
        )
        if setting_text:
            travel_matrix = recorder.run(
                "travel_matrix",
                lambda: _parse_travel_matrix(setting_text),
                [],
            )

    # ----- canon log facts, size-capped (#280, #500, #501, #504) ------------
    # Unbounded, this carries the same risk that blew get_review_brief's MCP
    # output limit on Firelight (330K chars, #500) — and worse, since this
    # brief also loads chapter timeline grids and calendar events on top of
    # it, so the cap here uses a QUARTER of review_brief's budget
    # (_CANON_FACTS_BUDGET_DIVISOR — see its own comment for the worst-case
    # math across all three capped fields) to leave headroom for those. Read
    # from the module (not a copied
    # constant) so tests can still monkeypatch brief_common.CANON_FACTS_CHAR_
    # BUDGET and see it reflected here (Issue #505 — this used to read
    # review_brief's copy of the constant, before the truncation helpers
    # moved to their own shared module). Reuse brief_common.cap_canon_facts()
    # rather than domain-filtering; see its docstring for why an entire domain
    # (e.g. "timeline") is never assumed safe to drop.
    #
    # oldest_first=True: unlike review_brief, this assembler has no single
    # "current chapter" to rank around — it covers the whole manuscript — so
    # the newest-chapter-first fallback would systematically drop the
    # earliest, most foundational canon (the facts late chapters are most
    # likely to accidentally contradict). Applies to ACTIVE facts only.
    #
    # CHANGED facts and chapter-unattributed facts are both exceptions to
    # this flag, for different reasons — see brief_common.cap_canon_facts's
    # own docstring for the current, authoritative behavior of each rather
    # than re-deriving it here (Issue #506 code review: an earlier version
    # of this comment claimed oldest_first still applied to the
    # chapter-unattributed subset, which drifted out of sync with the code
    # once CHANGED facts got their own rank direction — don't repeat that).
    #
    # current_book_num ranking (inherited from #500) is applied ABOVE
    # oldest_first in the sort order — deliberately: in a series, this book's
    # own canon always wins the budget over an earlier book's, even though
    # that means an earlier book's canon can be fully dropped first. Accepted
    # tradeoff, same as for the per-chapter review_brief case.
    canon_log_facts_raw: list[dict] = recorder.run(
        "canon_log_facts",
        lambda: load_canon_facts_for_brief(book_root),
        [],
    )
    current_book_num = recorder.run(
        "book_num",
        lambda: get_book_num(book_root),
        None,
    )
    # Fallback on error is an empty list, not canon_log_facts_raw — falling
    # back to the raw uncapped list would reintroduce the exact size failure
    # this cap exists to prevent.
    canon_log_facts, canon_log_facts_truncated, canon_log_facts_total_count = recorder.run(
        "canon_log_facts_cap",
        lambda: _cap_canon_facts(
            canon_log_facts_raw,
            current_book_num=current_book_num,
            current_chapter_num=None,
            oldest_first=True,
            char_budget=_brief_common_module.CANON_FACTS_CHAR_BUDGET // _CANON_FACTS_BUDGET_DIVISOR,
        ),
        ([], True, len(canon_log_facts_raw)),
    )

    # ----- character index --------------------------------------------------
    character_index = recorder.run(
        "character_index",
        lambda: _build_character_index(book_root),
        [],
    )

    # ----- all chapter timelines, size-capped (#504) -------------------------
    # Named in #504 as the field most likely to grow with book length. Real
    # measurement on Firelight (34 chapters, the reference project from #500)
    # put the unbounded field at 5,132 chars — nowhere near a problem today,
    # but chapter count is the one axis here that scales with book length
    # rather than character/event count, so this still gets a defensive cap
    # rather than staying unbounded on faith. _get_all_chapter_timelines()
    # already returns chapters in ascending chapter-number order, so
    # cap_group() naturally keeps the EARLIEST chapters first when truncating
    # — same "protect foundational canon" rationale already applied to
    # canon_log_facts's oldest_first=True above, extended here since a
    # whole-manuscript continuity scan has no single "current chapter" to
    # anchor a newest-first cap on either.
    chapter_timelines_raw: list[dict[str, Any]] = recorder.run(
        "chapter_timelines",
        lambda: _get_all_chapter_timelines(book_root),
        [],
    )
    # Fallback on error is an empty (truncated) list, not chapter_timelines_raw
    # — same fail-safe as canon_log_facts_cap above, so a failure in the cap
    # itself can't reintroduce an unbounded payload.
    chapter_timelines, chapter_timelines_truncated = recorder.run(
        "chapter_timelines_cap",
        lambda: _cap_group(chapter_timelines_raw, _CHAPTER_TIMELINES_CHAR_BUDGET),
        ([], True),
    )
    chapter_timelines_total_count = len(chapter_timelines_raw)

    # ----- character snapshots from DB (Issue #281) -------------------------
    def _load_character_snapshots() -> list[dict]:
        db_slug = get_db_slug_for_book(book_root)
        conn = open_canon_db(db_slug)
        try:
            return get_all_latest_snapshots(conn)
        finally:
            conn.close()

    character_snapshots: list[dict] = recorder.run(
        "character_snapshots",
        _load_character_snapshots,
        [],
    )

    return {
        "book_slug": book_slug,
        "canonical_calendar": canonical_calendar,
        "canonical_calendar_truncated": canonical_calendar_truncated,
        "canonical_calendar_total_count": canonical_calendar_total_count,
        "travel_matrix": travel_matrix,
        "canon_log_facts": canon_log_facts,
        "canon_log_facts_truncated": canon_log_facts_truncated,
        "canon_log_facts_total_count": canon_log_facts_total_count,
        "character_index": character_index,
        "chapter_timelines": chapter_timelines,
        "chapter_timelines_truncated": chapter_timelines_truncated,
        "chapter_timelines_total_count": chapter_timelines_total_count,
        "character_snapshots": character_snapshots,
        "errors": list(recorder.errors),
    }
