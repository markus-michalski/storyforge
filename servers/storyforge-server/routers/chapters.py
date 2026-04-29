"""Chapter-level tools: read state, briefs, anchors, draft transition.

Includes the keystone briefs (chapter_writing/review/continuity) plus the
``start_chapter_draft`` transition that flips Outline → Draft and migrates
chapter metadata into the canonical ``chapter.yaml`` (Issue #16).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from tools.analysis.tactical_checker import (
    verify_tactical_setup as _verify_tactical_setup_impl,
)
from tools.shared.gate_derivation import derive_from_tactical_setup
from tools.shared.gate_result import wrap_legacy
from tools.shared.paths import resolve_chapter_path, resolve_project_path
from tools.state.chapter_timeline_parser import (
    get_recent_chapter_timelines as _get_recent_chapter_timelines_impl,
)
from tools.state.chapter_writing_brief import (
    build_chapter_writing_brief as _build_chapter_writing_brief_impl,
)
from tools.state.continuity_brief import (
    build_continuity_brief as _build_continuity_brief_impl,
)
from tools.state.parsers import (
    is_chapter_drafted,
    parse_chapter_readme,
    parse_frontmatter,
)
from tools.state.review_brief import build_review_brief as _build_review_brief_impl
from tools.timeline_anchor import get_story_anchor

from . import _app
from ._app import _cache, mcp


@mcp.tool()
def get_chapter(book_slug: str, chapter_slug: str) -> str:
    """Get chapter metadata and word count."""
    state = _cache.get()
    book = state.get("books", {}).get(book_slug)
    if not book:
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    chapter = book.get("chapters_data", {}).get(chapter_slug)
    if not chapter:
        return json.dumps({"error": f"Chapter '{chapter_slug}' not found in '{book_slug}'"})

    return json.dumps(chapter)


@mcp.tool()
def get_current_story_anchor(book_slug: str, chapter_slug: str = "") -> str:
    """Resolve the current story-time anchor for a chapter.

    Loads the chapter's `## Chapter Timeline` section (Start / End points)
    plus the previous chapter's anchor, and returns a structured payload
    that maps common relative phrases (`yesterday`, `this morning`,
    `last week`, etc.) to their implied story-calendar dates.

    Use this from `chapter-writer` instead of computing date math by
    hand — it's the fix for the cross-chapter time-anchor drift that
    surfaced in the Blood & Binary Ch 22 review (#72).

    Args:
        book_slug: book identifier (`get_book_full` slug).
        chapter_slug: chapter identifier. When empty, uses the current
            session's `last_chapter` if set, otherwise returns an error.

    Returns JSON with keys ``current_chapter``, ``previous_chapter`` and
    ``available_relative_phrases``.
    """
    state = _cache.get()
    book = state.get("books", {}).get(book_slug)
    if not book:
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    if not chapter_slug:
        session = state.get("session", {}) or {}
        chapter_slug = session.get("last_chapter") or ""
    if not chapter_slug:
        return json.dumps({
            "error": (
                "chapter_slug not provided and no last_chapter in session. "
                "Pass chapter_slug explicitly or call update_session first."
            )
        })

    book_root = resolve_project_path(_app.load_config(), book_slug)
    if not book_root.is_dir():
        return json.dumps({
            "error": f"Book directory missing on disk: {book_root}"
        })

    anchor = get_story_anchor(book_root, chapter_slug)
    return json.dumps(anchor.to_dict())


@mcp.tool()
def get_recent_chapter_timelines(book_slug: str, n: int = 3) -> str:
    """Load the last N chapters' intra-day timeline grids as structured JSON.

    Returns the most recent ``n`` chapters that have reached review
    status or later (drafts and outlines are filtered out), in
    chronological order. Each grid carries the chapter's number, slug,
    title, status, story-time start/end anchor, and the list of scenes
    with their clock times.

    Use this from `chapter-writer` (Prerequisite 14) to anchor against
    three real intra-day grids instead of remembering times across
    chapters — the cross-chapter cascade-drift fix from beta-feedback
    on Blood & Binary chapter 22 (#77).

    Args:
        book_slug: book identifier.
        n: number of recent eligible chapters to return (default 3).
            Returns fewer when the book has fewer eligible chapters.

    Returns JSON with ``chapters`` list, each entry containing
    ``number``, ``slug``, ``title``, ``status``, ``start``, ``end``,
    and ``scenes``.
    """
    book_root = resolve_project_path(_app.load_config(), book_slug)
    if not book_root.is_dir():
        return json.dumps({
            "error": f"Book directory missing on disk: {book_root}"
        })

    grids = _get_recent_chapter_timelines_impl(book_root, n=n)
    return json.dumps({"chapters": [g.to_dict() for g in grids]})


@mcp.tool()
def verify_tactical_setup(
    book_slug: str,
    scene_outline_text: str,
    characters_present: list[str],
) -> str:
    """Pre-write sanity check for combat/travel scenes (#75).

    Cross-references each character's optional ``tactical`` frontmatter
    block (`protector_role`, `protected_role`, `combat_skill`,
    `movement_lead`, `movement_rear`) with the scene outline and
    surfaces walking-order or formation problems.

    Use this from `chapter-writer` and `rolling-planner` BEFORE writing
    a scene that involves group movement through dangerous space or
    combat. The tool produces a JSON brief: ``passes`` (false when
    any warn-severity rule fires), ``warnings`` (severity + message),
    ``questions_for_writer`` (always at least 3 — universal pre-write
    questions, specialized per protected/vulnerable character), and
    ``detected_positions`` (map of character to ``lead`` / ``rear`` /
    ``middle`` / ``unknown``).

    Args:
        book_slug: book identifier.
        scene_outline_text: free-text outline or first-pass paragraph
            describing the scene's group movement.
        characters_present: character slugs (matching the
            ``characters/{slug}.md`` filename without the suffix) that
            participate in the scene.

    Returns JSON with ``passes``, ``warnings``, ``questions_for_writer``,
    ``detected_positions``.
    """
    book_root = resolve_project_path(_app.load_config(), book_slug)
    if not book_root.is_dir():
        return json.dumps({
            "error": f"Book directory missing on disk: {book_root}"
        })

    result = _verify_tactical_setup_impl(
        book_root,
        scene_outline_text=scene_outline_text,
        characters_present=characters_present,
    )
    gate = derive_from_tactical_setup(result)
    return json.dumps(wrap_legacy(result, gate))


@mcp.tool()
def get_chapter_writing_brief(book_slug: str, chapter_slug: str) -> str:
    """Architectural keystone for chapter-writer (#78).

    Replaces the 16 prose prereq-loads in `chapter-writer` with a
    single structured JSON brief. Gathers data from every Sprint 1/2
    sub-tool (story anchor, recent chapter timelines, banlist, tactical
    setup, POV knowledge boundary) plus the older book-context sources
    (book CLAUDE.md rules + callbacks, tone litmus questions, character
    profiles) into one deterministic payload.

    Each sub-component is wrapped in try/except so a single failure
    records itself in the ``errors`` list and the brief still ships
    with partial data.

    Use this from `chapter-writer` as the FIRST tool call in the
    prerequisite phase. Honor every populated field while writing.
    Empty fields and entries in ``errors`` mean "data not available
    for this chapter" — degrade gracefully, do not invent.

    Args:
        book_slug: book identifier.
        chapter_slug: chapter identifier (e.g. "22-the-night-before").

    Returns JSON with:
        - chapter (metadata + outline path)
        - pov_character (name)
        - story_anchor (current + previous + relative-phrase mapping)
        - recent_chapter_timelines (last 3 review-or-later grids)
        - recent_chapter_endings (last paragraph of each)
        - characters_present (POV + scanned roster, full profiles +
          knowledge + tactical when set)
        - rules_to_honor (book CLAUDE.md ## Rules with severity)
        - callbacks_in_register (book CLAUDE.md ## Callback Register)
        - banned_phrases (deduplicated book + author + global banlist)
        - recent_simile_count_per_chapter
        - tone_litmus_questions (from plot/tone.md if present)
        - tactical_constraints (only when outline triggers combat/travel)
        - review_handle (configured inline-review name)
        - errors (component → error map for graceful degrade)
    """
    book_root = resolve_project_path(_app.load_config(), book_slug)
    if not book_root.is_dir():
        return json.dumps({
            "error": f"Book directory missing on disk: {book_root}"
        })

    plugin_root = Path(
        os.environ.get(
            "CLAUDE_PLUGIN_ROOT",
            str(Path(__file__).resolve().parent.parent.parent.parent),
        )
    )
    config = _app.load_config()
    review_handle = _app.get_review_handle(config) or "Markus"

    return json.dumps(_build_chapter_writing_brief_impl(
        book_root=book_root,
        book_slug=book_slug,
        chapter_slug=chapter_slug,
        plugin_root=plugin_root,
        review_handle=review_handle,
    ))


@mcp.tool()
def get_review_brief(book_slug: str, chapter_slug: str) -> str:
    """Structured brief for chapter-reviewer — Issue #99 (ADR-0001).

    Replaces direct file reads in ``chapter-reviewer`` with a single
    structured JSON payload. The brief bundles every piece of project-state
    metadata the reviewer needs: chapter timelines, canonical timeline,
    travel matrix, canon log facts, tonal rules, and book CLAUDE.md rules.

    Chapter draft text is intentionally NOT included — the reviewer reads
    that directly as the primary content under review.

    Args:
        book_slug: Book identifier.
        chapter_slug: Chapter identifier (e.g. "22-the-night-before").

    Returns JSON with:
        chapter_timeline        — start/end/scenes for the target chapter
        previous_chapter_timeline — same for the preceding chapter (or null)
        canonical_timeline_entries — parsed plot/timeline.md events
        travel_matrix           — parsed world/setting.md Travel Matrix rows
        canon_log_facts         — parsed plot/canon-log.md Established Facts
        tonal_rules             — non-negotiable rules, litmus, banned patterns
        active_rules            — book CLAUDE.md ## Rules with severity
        active_callbacks        — book CLAUDE.md ## Callback Register items
        errors                  — partial failures (brief ships with degraded data)
    """
    book_root = resolve_project_path(_app.load_config(), book_slug)
    if not book_root.is_dir():
        return json.dumps({"error": f"Book directory missing on disk: {book_root}"})

    return json.dumps(_build_review_brief_impl(
        book_root=book_root,
        book_slug=book_slug,
        chapter_slug=chapter_slug,
    ))


@mcp.tool()
def get_continuity_brief(book_slug: str) -> str:
    """Structured brief for continuity-checker — Issue #100 (ADR-0001).

    Replaces direct file reads in ``continuity-checker`` with a single
    structured JSON payload. Bundles canonical calendar, travel matrix,
    canon log facts, character index, and all chapter timeline grids.

    Chapter draft texts are intentionally NOT included — they are the data
    being checked, not project-state metadata (ADR-0001).

    Args:
        book_slug: Book identifier.

    Returns JSON with:
        canonical_calendar  — parsed plot/timeline.md events
        travel_matrix       — parsed world/setting.md Travel Matrix rows
        canon_log_facts     — parsed plot/canon-log.md Established Facts
        character_index     — all character files as flat list
        chapter_timelines   — all chapter timeline grids (any status)
        errors              — partial failures (brief ships with degraded data)
    """
    book_root = resolve_project_path(_app.load_config(), book_slug)
    if not book_root.is_dir():
        return json.dumps({"error": f"Book directory missing on disk: {book_root}"})

    return json.dumps(_build_continuity_brief_impl(
        book_root=book_root,
        book_slug=book_slug,
    ))


@mcp.tool()
def start_chapter_draft(book_slug: str, chapter_slug: str) -> str:
    """Mark a chapter as actively being drafted.

    Flips chapter status ``Outline → Draft`` (writes to ``chapter.yaml`` if
    present, otherwise to README frontmatter). Only moves forward — a
    chapter already at Draft, Revision/review, Polished, or Final is left
    untouched.

    The chapter-writer skill should call this BEFORE writing the first
    scene so ``get_book_progress`` and the book-tier derivation reflect
    active work immediately, not just after Step 7 when the chapter is
    complete. Later transitions (Draft → Review/Final) still go through
    ``update_field``.

    Args:
        book_slug: Book project slug
        chapter_slug: Chapter directory name (e.g. "01-invisible")

    Returns JSON with before/after status and whether an update occurred.
    """
    import yaml as _yaml

    config = _app.load_config()
    ch_dir = resolve_chapter_path(config, book_slug, chapter_slug)

    if not ch_dir.exists():
        return json.dumps({
            "error": f"Chapter '{chapter_slug}' not found in book '{book_slug}'"
        })

    # Respect the Issue #16 convention: chapter.yaml is the preferred source
    # of truth. parse_chapter_readme already merges yaml + README frontmatter.
    chapter_meta = parse_chapter_readme(ch_dir / "README.md")
    current_status = chapter_meta.get("status") or "Outline"

    # No-op if the chapter has already moved past Outline — we never regress.
    if is_chapter_drafted(current_status):
        return json.dumps({
            "success": True,
            "book_slug": book_slug,
            "chapter_slug": chapter_slug,
            "chapter_status_before": current_status,
            "chapter_status_after": current_status,
            "chapter_updated": False,
            "message": f"Chapter already at '{current_status}' — no change.",
        })

    # Flip Outline → Draft. Prefer chapter.yaml; migrate from README
    # frontmatter to chapter.yaml on first touch (canonical source of
    # truth per #16).
    chapter_yaml = ch_dir / "chapter.yaml"
    migrated = False

    if chapter_yaml.exists():
        try:
            loaded = _yaml.safe_load(chapter_yaml.read_text(encoding="utf-8"))
            meta = loaded if isinstance(loaded, dict) else {}
        except _yaml.YAMLError:
            meta = {}
        meta["status"] = "Draft"
        chapter_yaml.write_text(
            _yaml.safe_dump(meta, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    else:
        # No chapter.yaml — migrate metadata out of README frontmatter
        # into a fresh chapter.yaml, then strip the frontmatter from
        # README so we don't carry two stale sources forward.
        readme = ch_dir / "README.md"
        text = readme.read_text(encoding="utf-8")
        fm_meta, body = parse_frontmatter(text)
        fm_meta["status"] = "Draft"
        chapter_yaml.write_text(
            _yaml.safe_dump(fm_meta, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        # Remove the frontmatter block; keep the body intact.
        readme.write_text(body.lstrip("\n") if body else "", encoding="utf-8")
        migrated = True

    _cache.invalidate()
    return json.dumps({
        "success": True,
        "book_slug": book_slug,
        "chapter_slug": chapter_slug,
        "chapter_status_before": current_status,
        "chapter_status_after": "Draft",
        "chapter_updated": True,
        "migrated_to_chapter_yaml": migrated,
    })
