"""Continuity brief assembler — Issue #100.

Bundles canonical_calendar, travel_matrix, canon_log_facts,
character_index, and chapter_timelines into one structured JSON brief.

Chapter draft texts are intentionally NOT included — they are the data
being checked, not project-state metadata (ADR-0001: data-briefs-over-
prompt-instructions).

Design follows ``chapter_writing_brief.py`` (Issue #78).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.analysis.timeline_validator import parse_plot_timeline
from tools.db.brief_helpers import load_canon_facts_for_brief
from tools.db.character_snapshots import get_all_latest_snapshots
from tools.db.connection import get_book_num, get_db_slug_for_book, open_canon_db
from tools.state.chapter_timeline_parser import parse_chapter_timeline_grid
from tools.state.parsers import parse_frontmatter
from tools.state.review_brief import (
    _Recorder,
    _CHAPTER_NUM_RE,
    _cap_canon_facts,
    _parse_travel_matrix,
)
from tools.state import review_brief as _review_brief_module

# Half of review_brief's char budget — this brief also carries every
# chapter's timeline grid on top of canon_log_facts, unlike review_brief.
_CANON_FACTS_BUDGET_DIVISOR = 2


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
    character_index, and all chapter_timelines into a single
    JSON-serializable dict. ``continuity-checker`` calls this once
    instead of reading timeline/setting/canon/character files by hand.

    Chapter draft texts are intentionally excluded — they are the data
    being checked, not project-state metadata (ADR-0001).

    Args:
        book_root: Absolute path to the book project directory.
        book_slug: Book identifier.

    Returns dict with:
        book_slug            — echoes the book_slug argument
        canonical_calendar   — parsed plot/timeline.md events
        travel_matrix        — parsed world/setting.md Travel Matrix rows
        canon_log_facts      — established facts from the canon DB, size-bounded
                                the same way as get_review_brief but earliest-
                                chapter-first and at half the budget (Issue
                                #500/#501) — see the ``canon_log_facts, size-capped``
                                code comment below for the full ranking rationale,
                                and canon_log_facts_truncated/_total_count below
        canon_log_facts_truncated — True if canon_log_facts was capped for size
        canon_log_facts_total_count — untruncated fact count (== len(canon_log_facts)
                                when not truncated)
        character_index      — all character files as flat list
        chapter_timelines    — all chapter timeline grids (any status)
        character_snapshots  — latest per-character state from the
                                character_snapshots DB table (Issue #281)
        errors               — component → error map for graceful degrade
    """
    recorder = _Recorder(errors=[])

    # ----- canonical calendar -----------------------------------------------
    canonical_calendar: list[dict[str, Any]] = []
    calendar = recorder.run(
        "canonical_calendar",
        lambda: parse_plot_timeline(book_root),
        None,
    )
    if calendar is not None:
        canonical_calendar = [e.to_dict() for e in calendar.events]

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

    # ----- canon log facts, size-capped (#280, #500, #501) ------------------
    # Unbounded, this carries the same risk that blew get_review_brief's MCP
    # output limit on Firelight (330K chars, #500) — and worse, since this
    # brief also loads every chapter's timeline grid on top of it, so the cap
    # here uses HALF of review_brief's budget (_CANON_FACTS_BUDGET_DIVISOR) to
    # leave headroom for that fixed cost. Read from the module (not a copied
    # constant) so tests can still monkeypatch review_brief._CANON_FACTS_CHAR_
    # BUDGET and see it reflected here. Reuse review_brief._cap_canon_facts()
    # rather than domain-filtering; see its docstring for why an entire domain
    # (e.g. "timeline") is never assumed safe to drop.
    #
    # oldest_first=True: unlike review_brief, this assembler has no single
    # "current chapter" to rank around — it covers the whole manuscript — so
    # the newest-chapter-first fallback would systematically drop the
    # earliest, most foundational canon (the facts late chapters are most
    # likely to accidentally contradict). Applies to BOTH priority tiers,
    # including CHANGED facts: for a whole-manuscript scan, an earlier
    # revision has had more subsequent chapters to go stale in than a recent
    # one, so oldest-first serves the stale-reference check too, not only the
    # ACTIVE facts.
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
            char_budget=_review_brief_module._CANON_FACTS_CHAR_BUDGET // _CANON_FACTS_BUDGET_DIVISOR,
        ),
        ([], True, len(canon_log_facts_raw)),
    )

    # ----- character index --------------------------------------------------
    character_index = recorder.run(
        "character_index",
        lambda: _build_character_index(book_root),
        [],
    )

    # ----- all chapter timelines (no status filter) -------------------------
    chapter_timelines = recorder.run(
        "chapter_timelines",
        lambda: _get_all_chapter_timelines(book_root),
        [],
    )

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
        "travel_matrix": travel_matrix,
        "canon_log_facts": canon_log_facts,
        "canon_log_facts_truncated": canon_log_facts_truncated,
        "canon_log_facts_total_count": canon_log_facts_total_count,
        "character_index": character_index,
        "chapter_timelines": chapter_timelines,
        "character_snapshots": character_snapshots,
        "errors": list(recorder.errors),
    }
