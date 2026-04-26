"""StoryForge MCP Server — FastMCP-based tool server for book writing workflow."""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

# Ensure plugin root is on path so `tools` can be imported as a package
plugin_root = os.environ.get(
    "CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent.parent)
)
if plugin_root not in sys.path:
    sys.path.insert(0, plugin_root)

from mcp.server.fastmcp import FastMCP

from tools.shared.config import load_config, get_content_root, get_genres_dir, get_reference_dir, get_review_handle
from tools.shared.paths import slugify, resolve_project_path, resolve_chapter_path, resolve_character_path, resolve_author_path, find_chapters, resolve_series_path, resolve_world_dir
from tools.state.indexer import StateCache, rebuild
from tools.state.parsers import parse_frontmatter, count_words_in_file, is_chapter_drafted, parse_chapter_readme
from tools.analysis.manuscript_checker import scan_repetitions, render_report
from tools.analysis.tactical_checker import (
    verify_tactical_setup as _verify_tactical_setup_impl,
)
from tools.state.chapter_timeline_parser import (
    get_recent_chapter_timelines as _get_recent_chapter_timelines_impl,
)
from tools.timeline_anchor import get_story_anchor
from tools.claudemd.manager import (
    append_callback as _append_callback_impl,
    append_rule as _append_rule_impl,
    append_workflow as _append_workflow_impl,
    get_claudemd as _get_claudemd_impl,
    init_claudemd as _init_claudemd_impl,
    update_book_facts as _update_book_facts_impl,
)
from tools.claudemd.parser import extract_prefixed_lines as _extract_prefixed_lines

mcp = FastMCP("storyforge-mcp")
_cache = StateCache()


# ============================================================
# State Management Tools
# ============================================================


@mcp.tool()
def list_books() -> str:
    """List all book projects with status and word count."""
    state = _cache.get()
    books = state.get("books", {})
    if not books:
        return json.dumps({"books": [], "count": 0})

    result = []
    for slug, book in books.items():
        result.append({
            "slug": slug,
            "title": book.get("title", slug),
            "status": book.get("status", "Idea"),
            "genres": book.get("genres", []),
            "author": book.get("author", ""),
            "book_type": book.get("book_type", "novel"),
            "chapter_count": book.get("chapter_count", 0),
            "total_words": book.get("total_words", 0),
        })
    return json.dumps({"books": result, "count": len(result)})


@mcp.tool()
def find_book(query: str) -> str:
    """Find a book by slug or title (partial match)."""
    state = _cache.get()
    query_lower = query.lower()
    matches = []

    for slug, book in state.get("books", {}).items():
        if query_lower in slug or query_lower in book.get("title", "").lower():
            matches.append({"slug": slug, "title": book.get("title", slug)})

    return json.dumps({"matches": matches, "count": len(matches)})


@mcp.tool()
def get_book_full(slug: str) -> str:
    """Get complete book data including all chapters and characters.

    Returns effective_author_writing_mode: book-level override takes precedence
    over the author profile value; falls back to "outliner" if neither is set.
    """
    state = _cache.get()
    book = state.get("books", {}).get(slug)
    if not book:
        return json.dumps({"error": f"Book '{slug}' not found"})

    author_slug = book.get("author", "")
    author = state.get("authors", {}).get(author_slug, {})
    book_override = book.get("author_writing_mode", "")
    effective = book_override or author.get("author_writing_mode", "outliner")
    book = {**book, "effective_author_writing_mode": effective}

    return json.dumps(book)


@mcp.tool()
def get_book_progress(slug: str) -> str:
    """Get book progress: chapter statuses, word counts, completion percentage."""
    state = _cache.get()
    book = state.get("books", {}).get(slug)
    if not book:
        return json.dumps({"error": f"Book '{slug}' not found"})

    chapters = book.get("chapters_data", {})
    total = len(chapters)
    # Issue #19: tolerate non-canonical chapter statuses ("review", etc.) —
    # anything past "Outline" counts as drafted. Final stays strict.
    final = sum(1 for c in chapters.values() if c.get("status") == "Final")
    drafted = sum(1 for c in chapters.values() if is_chapter_drafted(c.get("status", "")))
    total_words = book.get("total_words", 0)
    target = book.get("target_word_count", 0)

    return json.dumps({
        "slug": slug,
        "title": book.get("title", slug),
        # Indexer already derived this from chapter state (Issue #19).
        "status": book.get("status", "Idea"),
        "status_disk": book.get("status_disk", book.get("status", "Idea")),
        "chapters_total": total,
        "chapters_drafted": drafted,
        "chapters_final": final,
        # Issue #19: completion tracks forward progress (drafted), not sign-off (final).
        "completion_percent": round(drafted / total * 100) if total else 0,
        "total_words": total_words,
        "target_words": target,
        "word_progress_percent": round(total_words / target * 100) if target else 0,
        "chapters": {
            slug: {"status": ch.get("status"), "words": ch.get("word_count", 0)}
            for slug, ch in chapters.items()
        },
    })


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

    book_root = resolve_project_path(load_config(), book_slug)
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
    book_root = resolve_project_path(load_config(), book_slug)
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
    book_root = resolve_project_path(load_config(), book_slug)
    if not book_root.is_dir():
        return json.dumps({
            "error": f"Book directory missing on disk: {book_root}"
        })

    return json.dumps(
        _verify_tactical_setup_impl(
            book_root,
            scene_outline_text=scene_outline_text,
            characters_present=characters_present,
        )
    )


@mcp.tool()
def list_chapters(book_slug: str) -> str:
    """List all chapters of a book with status and word count."""
    state = _cache.get()
    book = state.get("books", {}).get(book_slug)
    if not book:
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    chapters = book.get("chapters_data", {})
    result = [
        {"slug": slug, "number": ch.get("number", 0), "title": ch.get("title", slug),
         "status": ch.get("status", "Outline"), "words": ch.get("word_count", 0)}
        for slug, ch in sorted(chapters.items(), key=lambda x: x[1].get("number", 0))
    ]
    return json.dumps({"chapters": result, "count": len(result)})


@mcp.tool()
def get_session() -> str:
    """Get current session context."""
    state = _cache.get()
    return json.dumps(state.get("session", {}))


@mcp.tool()
def update_session(
    last_book: str = "",
    last_chapter: str = "",
    last_phase: str = "",
    active_author: str = "",
) -> str:
    """Update session context with current work info."""
    state = _cache.get()
    session = state.get("session", {})

    if last_book:
        session["last_book"] = last_book
    if last_chapter:
        session["last_chapter"] = last_chapter
    if last_phase:
        session["last_phase"] = last_phase
    if active_author:
        session["active_author"] = active_author

    state["session"] = session
    from tools.state.indexer import _write_state
    _write_state(state)
    _cache.invalidate()

    return json.dumps({"success": True, "session": session})


@mcp.tool()
def get_review_handle_config() -> str:
    """Return the configured review comment handle from config.

    Used by chapter-writer to replace the hardcoded author name in
    inline review comment blocks (e.g. 'Author: this feels off').
    Configurable via defaults.review_handle in ~/.storyforge/config.yaml.
    """
    config = load_config()
    handle = get_review_handle(config)
    return json.dumps({"review_handle": handle})


@mcp.tool()
def rebuild_state() -> str:
    """Force rebuild of the state cache from filesystem.

    Also runs the Issue #25 auto-sync: any book whose derived status
    (from chapter aggregates) is a forward move from its on-disk README
    frontmatter gets its README updated in place. Floor rule — never
    downgrades a user-set higher tier. Sync events are returned in the
    ``synced`` list so the user can see what changed.
    """
    state = rebuild(preserve_session=True)
    _cache.invalidate()
    books_count = len(state.get("books", {}))
    authors_count = len(state.get("authors", {}))
    synced = state.get("sync_log", [])
    msg = f"Rebuilt state: {books_count} books, {authors_count} authors"
    if synced:
        msg += f"; synced {len(synced)} book status(es) to disk"
    return json.dumps({
        "success": True,
        "books": books_count,
        "authors": authors_count,
        "synced": synced,
        "message": msg,
    })


@mcp.tool()
def scan_manuscript(
    book_slug: str,
    min_occurrences: int = 2,
    write_report: bool = True,
    max_findings_per_category: int = 40,
) -> str:
    """Scan all chapter drafts of a book for prose-quality issues that only
    surface when the whole manuscript is read in one pass.

    Detects:
    - Violations of rules from the book's CLAUDE.md (highest priority)
    - Curated fiction clichés ("blood ran cold", "time stood still", ...)
    - Dialogue punctuation anomalies (Q-word opener + trailing period)
    - POV filter-word overuse per chapter ("felt", "noticed", "saw that", ...)
    - Per-chapter `-ly` adverb density
    - Cross-chapter repeated phrases: similes, character tells, blocking tics,
      structural patterns, signature phrases

    Returns the structured findings as JSON. When `write_report` is true,
    also writes a human-readable Markdown report to
    `<book>/research/manuscript-report.md` and returns the path.

    Args:
        book_slug: The book project slug.
        min_occurrences: Minimum number of times a phrase must appear to count
            as a repetition. Default 2.
        write_report: When true, also writes the Markdown report file.
        max_findings_per_category: Cap per category to keep the report focused.
    """
    config = load_config()
    book_path = resolve_project_path(config, book_slug)
    if not book_path.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found at {book_path}"})

    result = scan_repetitions(
        book_path=book_path,
        min_occurrences=min_occurrences,
        max_findings_per_category=max_findings_per_category,
    )

    report_path: str | None = None
    if write_report:
        research_dir = book_path / "research"
        research_dir.mkdir(parents=True, exist_ok=True)
        report_file = research_dir / "manuscript-report.md"
        report_file.write_text(render_report(result), encoding="utf-8")
        report_path = str(report_file)

    return json.dumps({
        "book_slug": book_slug,
        "chapters_scanned": result["chapters_scanned"],
        "findings_count": len(result["findings"]),
        "summary": result["summary"],
        "report_path": report_path,
        "findings": result["findings"],
    })


# ============================================================
# Author Management Tools
# ============================================================


@mcp.tool()
def list_authors() -> str:
    """List all author profiles."""
    state = _cache.get()
    authors = state.get("authors", {})
    result = [
        {"slug": slug, "name": a.get("name", slug),
         "genres": a.get("primary_genres", []),
         "studied_works": a.get("studied_works_count", 0)}
        for slug, a in authors.items()
    ]
    return json.dumps({"authors": result, "count": len(result)})


@mcp.tool()
def get_author(slug: str) -> str:
    """Get full author profile data."""
    state = _cache.get()
    author = state.get("authors", {}).get(slug)
    if not author:
        return json.dumps({"error": f"Author '{slug}' not found"})

    # Also load vocabulary if exists
    config = load_config()
    vocab_path = resolve_author_path(config, slug) / "vocabulary.md"
    if vocab_path.exists():
        author["vocabulary"] = vocab_path.read_text(encoding="utf-8")

    return json.dumps(author)


@mcp.tool()
def create_author(name: str, genres: str = "", tone: str = "", voice: str = "third-limited", tense: str = "past") -> str:
    """Create a new author profile directory with template files.

    Args:
        name: Author pen name
        genres: Comma-separated primary genres
        tone: Comma-separated tone descriptors (e.g. "sarcastic, dark-humor")
        voice: Narrative voice (first-person, third-limited, third-omniscient, second-person)
        tense: Narrative tense (past, present)
    """
    config = load_config()
    slug = slugify(name)
    author_dir = resolve_author_path(config, slug)

    if author_dir.exists():
        return json.dumps({"error": f"Author '{slug}' already exists"})

    author_dir.mkdir(parents=True)
    (author_dir / "studied-works").mkdir()
    (author_dir / "examples").mkdir()

    genre_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []
    tone_list = [t.strip() for t in tone.split(",") if t.strip()] if tone else []

    today = date.today().isoformat()
    profile = f"""---
name: "{name}"
slug: "{slug}"
created: "{today}"
updated: "{today}"
primary_genres: {json.dumps(genre_list)}
narrative_voice: "{voice}"
tense: "{tense}"
tone: {json.dumps(tone_list)}
sentence_style: "varied"
vocabulary_level: "moderate"
dialog_style: "naturalistic"
pacing: "tension-driven"
themes: []
influences: []
avoid: ["purple-prose", "info-dumps", "deus-ex-machina"]
---

# {name}

## Writing Style

*Style description will be refined through the study-author skill.*

## Signature Techniques

- *To be defined*

## Voice Notes

*Notes on this author's distinctive voice characteristics.*
"""

    (author_dir / "profile.md").write_text(profile, encoding="utf-8")
    (author_dir / "vocabulary.md").write_text(
        f"# {name} — Vocabulary\n\n## Preferred Words\n\n*To be defined*\n\n## Banned Words\n\n- delve\n- tapestry\n- nuanced\n- vibrant\n- resonate\n- pivotal\n- multifaceted\n- realm\n- testament\n- intricate\n- myriad\n- unprecedented\n- foster\n- beacon\n- juxtaposition\n- paradigm\n- synergy\n- interplay\n- ever-evolving\n- navigate (metaphorical)\n\n## Signature Phrases\n\n*To be defined through study-author*\n",
        encoding="utf-8",
    )

    _cache.invalidate()
    return json.dumps({
        "success": True,
        "slug": slug,
        "path": str(author_dir),
        "message": f"Author profile '{name}' created at {author_dir}",
    })


@mcp.tool()
def update_author(slug: str, field: str, value: str) -> str:
    """Update a field in an author's profile frontmatter."""
    config = load_config()
    profile_path = resolve_author_path(config, slug) / "profile.md"

    if not profile_path.exists():
        return json.dumps({"error": f"Author '{slug}' not found"})

    text = profile_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    meta[field] = value
    meta["updated"] = date.today().isoformat()

    import yaml
    new_text = "---\n" + yaml.dump(meta, default_flow_style=False, allow_unicode=True) + "---\n" + body
    profile_path.write_text(new_text, encoding="utf-8")

    _cache.invalidate()
    return json.dumps({"success": True, "field": field, "value": value})


# ============================================================
# Content Operations Tools
# ============================================================


@mcp.tool()
def create_book_structure(
    title: str,
    author: str = "",
    genres: str = "",
    book_type: str = "novel",
    language: str = "en",
    target_word_count: int = 80000,
) -> str:
    """Create a new book project with full directory scaffold.

    Args:
        title: Book title
        author: Author profile slug
        genres: Comma-separated genres (e.g. "horror, supernatural")
        book_type: Type (short-story, novelette, novella, novel, epic)
        language: Writing language
        target_word_count: Target word count
    """
    config = load_config()
    slug = slugify(title)
    project_dir = resolve_project_path(config, slug)

    if project_dir.exists():
        return json.dumps({"error": f"Book '{slug}' already exists"})

    genre_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []
    today = date.today().isoformat()

    # Create directory structure
    for subdir in [
        "plot", "characters", "world", "research/notes",
        "chapters", "cover/art", "export/output", "translations",
    ]:
        (project_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Book README
    readme = f"""---
title: "{title}"
slug: "{slug}"
author: "{author}"
genres: {json.dumps(genre_list)}
book_type: "{book_type}"
status: "Idea"
language: "{language}"
target_word_count: {target_word_count}
series: ""
series_number: 0
description: ""
created: "{today}"
updated: "{today}"
---

# {title}

## Premise

*What is this story about? One paragraph.*

## Logline

*One sentence that captures the core conflict and stakes.*

## Target Audience

*Who is this book for?*
"""

    (project_dir / "README.md").write_text(readme, encoding="utf-8")
    (project_dir / "synopsis.md").write_text(f"# {title} — Synopsis\n\n*To be written after plot is outlined.*\n", encoding="utf-8")

    # Plot files
    (project_dir / "plot" / "outline.md").write_text(f"# {title} — Plot Outline\n\n## Act 1: Setup\n\n## Act 2: Confrontation\n\n## Act 3: Resolution\n", encoding="utf-8")
    (project_dir / "plot" / "acts.md").write_text(f"# {title} — Act Structure\n\n*Use /storyforge:plot-architect to develop.*\n", encoding="utf-8")
    (project_dir / "plot" / "timeline.md").write_text(f"# {title} — Timeline\n\n*Chronological events.*\n", encoding="utf-8")
    (project_dir / "plot" / "tone.md").write_text(f"# {title} — Tonal Document\n\n*Use /storyforge:plot-architect to develop after plot outline is complete.*\n", encoding="utf-8")
    (project_dir / "plot" / "arcs.md").write_text(f"# {title} — Character Arcs\n\n*Use /storyforge:character-creator to develop.*\n", encoding="utf-8")

    # Characters
    (project_dir / "characters" / "INDEX.md").write_text(f"# {title} — Characters\n\n## Protagonists\n\n## Antagonists\n\n## Supporting\n", encoding="utf-8")

    # World
    (project_dir / "world" / "setting.md").write_text(f"# {title} — Setting\n\n*Where and when does the story take place?*\n", encoding="utf-8")
    (project_dir / "world" / "rules.md").write_text(f"# {title} — Rules\n\n*Magic system, physics, society rules.*\n", encoding="utf-8")
    (project_dir / "world" / "history.md").write_text(f"# {title} — History\n\n*Background history of the world.*\n", encoding="utf-8")
    (project_dir / "world" / "glossary.md").write_text(f"# {title} — Glossary\n\n*Terms, places, concepts.*\n", encoding="utf-8")

    # Research
    (project_dir / "research" / "sources.md").write_text(f"# {title} — Sources\n\n*Research materials and references.*\n", encoding="utf-8")

    # Cover
    (project_dir / "cover" / "brief.md").write_text(f"# {title} — Cover Brief\n\n*Use /storyforge:cover-artist to develop.*\n", encoding="utf-8")
    (project_dir / "cover" / "prompts.md").write_text(f"# {title} — Cover Prompts\n\n*AI art prompts will go here.*\n", encoding="utf-8")

    # Export
    (project_dir / "export" / "front-matter.md").write_text(f"---\ntitle: \"{title}\"\nauthor: \"\"\ncopyright_year: {date.today().year}\n---\n\n# {title}\n\n*by [Author Name]*\n\nCopyright {date.today().year}\n\nAll rights reserved.\n", encoding="utf-8")
    (project_dir / "export" / "back-matter.md").write_text("# About the Author\n\n*Author bio.*\n\n# Also by [Author Name]\n\n*Other books.*\n", encoding="utf-8")

    _cache.invalidate()
    return json.dumps({
        "success": True,
        "slug": slug,
        "path": str(project_dir),
        "message": f"Book '{title}' created at {project_dir}",
    })


@mcp.tool()
def create_chapter(book_slug: str, title: str, number: int, pov_character: str = "", summary: str = "") -> str:
    """Create a new chapter directory with README and empty draft."""
    config = load_config()
    slug = f"{number:02d}-{slugify(title)}"
    ch_dir = resolve_chapter_path(config, book_slug, slug)

    if ch_dir.exists():
        return json.dumps({"error": f"Chapter '{slug}' already exists"})

    ch_dir.mkdir(parents=True)

    readme = f"""---
title: "{title}"
number: {number}
slug: "{slug}"
status: "Outline"
pov_character: "{pov_character}"
summary: "{summary}"
word_count_target: 3000
---

# Chapter {number}: {title}

## Outline

*What happens in this chapter?*

## Scene Beats

1. *Beat 1*
2. *Beat 2*
3. *Beat 3*

## Notes

*Writing notes, research needed, etc.*
"""
    (ch_dir / "README.md").write_text(readme, encoding="utf-8")
    (ch_dir / "draft.md").write_text(f"# Chapter {number}: {title}\n\n", encoding="utf-8")

    # Issue #16: write chapter.yaml as the canonical metadata source so the
    # parser's preferred lookup target stays consistent with what we created.
    chapter_yaml = (
        f'title: "{title}"\n'
        f"number: {number}\n"
        f'slug: "{slug}"\n'
        f'status: "Outline"\n'
        f'pov_character: "{pov_character}"\n'
        f'summary: "{summary}"\n'
        f"word_count_target: 3000\n"
    )
    (ch_dir / "chapter.yaml").write_text(chapter_yaml, encoding="utf-8")

    _cache.invalidate()
    return json.dumps({
        "success": True,
        "slug": slug,
        "path": str(ch_dir),
        "message": f"Chapter {number}: '{title}' created",
    })


@mcp.tool()
def create_character(book_slug: str, name: str, role: str = "supporting", description: str = "") -> str:
    """Create a new character file in a book project.

    Args:
        book_slug: Book project slug
        name: Character name
        role: Role (protagonist, antagonist, supporting, minor)
        description: Brief description
    """
    config = load_config()
    slug = slugify(name)
    char_path = resolve_project_path(config, book_slug) / "characters" / f"{slug}.md"

    if char_path.exists():
        return json.dumps({"error": f"Character '{slug}' already exists"})

    char_path.parent.mkdir(parents=True, exist_ok=True)

    char_file = f"""---
name: "{name}"
role: "{role}"
status: "Concept"
age: ""
gender: ""
description: "{description}"
---

# {name}

## Role
{role.capitalize()}

## Physical Appearance

*Describe appearance — be specific, not generic.*

## Personality

*Core traits, quirks, habits.*

## Backstory / Wound

*What happened before the story? What shaped them?*

## Want vs. Need

- **Want (external):** *What they consciously pursue*
- **Need (internal):** *What they actually need to grow/change*

## Fatal Flaw

*The flaw that causes problems and connects to theme.*

## Character Arc

*Lie they believe → Truth they must learn (positive arc)*
*Or: Truth → Lie (negative arc)*

## Voice

*How do they speak? Vocabulary, patterns, tics.*

## Relationships

*Key relationships with other characters.*
"""
    char_path.write_text(char_file, encoding="utf-8")

    _cache.invalidate()
    return json.dumps({
        "success": True,
        "slug": slug,
        "path": str(char_path),
        "message": f"Character '{name}' created",
    })


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

    config = load_config()
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


@mcp.tool()
def update_field(file_path: str, field: str, value: str) -> str:
    """Update a field in a markdown frontmatter block or a plain YAML file.

    For ``.yaml``/``.yml`` files (e.g. ``chapter.yaml``) the file is treated
    as pure YAML — no frontmatter delimiters are written. For all other files
    the standard ``---`` frontmatter format is used.
    """
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    import yaml

    if path.suffix in (".yaml", ".yml"):
        # Pure YAML file — chapter.yaml and similar; never use frontmatter markers.
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            meta = loaded if isinstance(loaded, dict) else {}
        except yaml.YAMLError:
            meta = {}
        meta[field] = value
        path.write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True), encoding="utf-8")
    else:
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        meta[field] = value
        new_text = "---\n" + yaml.dump(meta, default_flow_style=False, allow_unicode=True) + "---\n" + body
        path.write_text(new_text, encoding="utf-8")

    _cache.invalidate()
    return json.dumps({"success": True, "file": file_path, "field": field, "value": value})


@mcp.tool()
def resolve_path(book_slug: str, component: str = "", sub_path: str = "") -> str:
    """Resolve filesystem path for a book component.

    Args:
        book_slug: Book project slug
        component: Component type (chapters, characters, plot, world, cover, export, research)
        sub_path: Optional sub-path within the component

    Note: ``world`` resolves to the first existing of ``world/``,
    ``worldbuilding/``, or ``world-building/`` (Issue #17). When no world dir
    exists, the canonical ``world/`` path is returned with ``exists: false``.
    """
    config = load_config()
    project = resolve_project_path(config, book_slug)

    if component == "world":
        world_dir = resolve_world_dir(project)
        base = world_dir if world_dir is not None else project / "world"
    elif component:
        base = project / component
    else:
        base = project

    if sub_path:
        base = base / sub_path

    return json.dumps({"path": str(base), "exists": base.exists()})


# ============================================================
# Analysis Tools
# ============================================================


@mcp.tool()
def count_words(book_slug: str, chapter_slug: str = "") -> str:
    """Count words in a chapter draft or entire book."""
    config = load_config()

    if chapter_slug:
        draft = resolve_chapter_path(config, book_slug, chapter_slug) / "draft.md"
        words = count_words_in_file(draft)
        return json.dumps({"book": book_slug, "chapter": chapter_slug, "words": words})

    # Count entire book
    state = _cache.get()
    book = state.get("books", {}).get(book_slug)
    if not book:
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    total = book.get("total_words", 0)
    target = book.get("target_word_count", 0)
    chapters = {
        slug: ch.get("word_count", 0)
        for slug, ch in book.get("chapters_data", {}).items()
    }
    return json.dumps({
        "book": book_slug,
        "total_words": total,
        "target_words": target,
        "progress_percent": round(total / target * 100) if target else 0,
        "per_chapter": chapters,
    })


# ============================================================
# Series Tools
# ============================================================


@mcp.tool()
def create_series(title: str, genres: str = "", planned_books: int = 3) -> str:
    """Create a new series directory."""
    config = load_config()
    slug = slugify(title)
    series_dir = resolve_series_path(config, slug)

    if series_dir.exists():
        return json.dumps({"error": f"Series '{slug}' already exists"})

    genre_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []

    series_dir.mkdir(parents=True)
    (series_dir / "characters").mkdir()
    (series_dir / "world").mkdir()
    (series_dir / "books").mkdir()

    readme = f"""---
title: "{title}"
slug: "{slug}"
genres: {json.dumps(genre_list)}
planned_books: {planned_books}
status: "Planning"
description: ""
---

# {title} — Series

## Series Arc

*The overarching story across all books.*

## Books

*Use /storyforge:series-planner to develop.*
"""
    (series_dir / "README.md").write_text(readme, encoding="utf-8")
    (series_dir / "series-arc.md").write_text(f"# {title} — Series Arc\n\n*The big picture.*\n", encoding="utf-8")
    (series_dir / "timeline.md").write_text(f"# {title} — Timeline\n\n*Chronology across all books.*\n", encoding="utf-8")
    (series_dir / "world" / "canon.md").write_text(f"# {title} — Canon\n\n*Established facts that cannot be contradicted.*\n", encoding="utf-8")

    _cache.invalidate()
    return json.dumps({"success": True, "slug": slug, "path": str(series_dir)})


@mcp.tool()
def get_series(slug: str) -> str:
    """Get series data."""
    state = _cache.get()
    series = state.get("series", {}).get(slug)
    if not series:
        return json.dumps({"error": f"Series '{slug}' not found"})
    return json.dumps(series)


@mcp.tool()
def add_book_to_series(series_slug: str, book_slug: str, number: int) -> str:
    """Link a book to a series."""
    config = load_config()
    series_dir = resolve_series_path(config, series_slug)
    book_dir = resolve_project_path(config, book_slug)

    if not series_dir.exists():
        return json.dumps({"error": f"Series '{series_slug}' not found"})
    if not book_dir.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    # Update book's frontmatter
    book_readme = book_dir / "README.md"
    text = book_readme.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    meta["series"] = series_slug
    meta["series_number"] = number

    import yaml
    new_text = "---\n" + yaml.dump(meta, default_flow_style=False, allow_unicode=True) + "---\n" + body
    book_readme.write_text(new_text, encoding="utf-8")

    # Create reference in series/books/
    ref_file = series_dir / "books" / f"{number:02d}-{book_slug}.md"
    ref_file.parent.mkdir(parents=True, exist_ok=True)
    ref_file.write_text(f"# Book {number}: {book_slug}\n\nPath: {book_dir}\n", encoding="utf-8")

    _cache.invalidate()
    return json.dumps({"success": True, "series": series_slug, "book": book_slug, "number": number})


# ============================================================
# Ideas Tools
# ============================================================


def _get_ideas_dir(config: dict) -> Path:
    """Return the ideas directory path for the current content root."""
    return get_content_root(config) / "ideas"


def _idea_path(ideas_dir: Path, slug: str) -> Path:
    """Return the file path for a given idea slug."""
    return ideas_dir / f"{slug}.md"


def _read_idea(ideas_dir: Path, slug: str) -> tuple[dict, str] | None:
    """Read and parse an idea file. Returns (meta, body) or None if not found."""
    path = _idea_path(ideas_dir, slug)
    if not path.exists():
        return None
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def _write_idea(path: Path, meta: dict, body: str) -> None:
    """Write frontmatter + body back to an idea file."""
    frontmatter = yaml.dump(meta, allow_unicode=True, sort_keys=False, default_flow_style=False)
    path.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")


@mcp.tool()
def create_idea(title: str, genres: str = "", logline: str = "", concept: str = "") -> str:
    """Create a new idea file in ideas/{slug}.md with YAML frontmatter.

    Args:
        title:   Human-readable title of the idea.
        genres:  Comma-separated genre names (e.g. "fantasy,mystery").
        logline: One-sentence pitch.
        concept: Free-text body content describing the idea.
    """
    config = load_config()
    ideas_dir = _get_ideas_dir(config)
    ideas_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify(title)
    genres_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []
    today = date.today().isoformat()

    meta: dict[str, Any] = {
        "title": title,
        "slug": slug,
        "status": "raw",
        "genres": genres_list,
        "logline": logline,
        "created": today,
        "last_touched": today,
        "promoted_to": None,
    }

    path = _idea_path(ideas_dir, slug)
    _write_idea(path, meta, concept)

    _cache.invalidate()
    return json.dumps({"slug": slug, "title": title, "file_path": str(path)})


@mcp.tool()
def list_ideas(status: str = "", genre: str = "") -> str:
    """List all ideas from the ideas/ directory, with optional filters.

    Args:
        status: Filter by exact status value (e.g. "raw", "explored").
        genre:  Filter by genre (partial match against each idea's genres list).
    """
    config = load_config()
    ideas_dir = _get_ideas_dir(config)

    if not ideas_dir.exists():
        return json.dumps({"ideas": [], "count": 0})

    ideas = []
    for md_file in sorted(ideas_dir.glob("*.md")):
        if not md_file.is_file():
            continue
        try:
            meta, _ = parse_frontmatter(md_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not meta:
            continue

        idea_status = meta.get("status", "raw")
        idea_genres = meta.get("genres", [])

        if status and idea_status != status:
            continue
        if genre and genre not in idea_genres:
            continue

        ideas.append({
            "slug": meta.get("slug", md_file.stem),
            "title": meta.get("title", md_file.stem),
            "status": idea_status,
            "genres": idea_genres,
            "logline": meta.get("logline", ""),
            "created": str(meta.get("created", "")),
            "last_touched": str(meta.get("last_touched", "")),
            "promoted_to": meta.get("promoted_to"),
        })

    return json.dumps({"ideas": ideas, "count": len(ideas)})


@mcp.tool()
def get_idea(slug: str) -> str:
    """Return the full content of a single idea file.

    Args:
        slug: The idea's slug (filename without .md extension).
    """
    config = load_config()
    ideas_dir = _get_ideas_dir(config)
    result = _read_idea(ideas_dir, slug)

    if result is None:
        return json.dumps({"error": f"Idea '{slug}' not found"})

    meta, body = result
    return json.dumps({
        "slug": meta.get("slug", slug),
        "title": meta.get("title", slug),
        "status": meta.get("status", "raw"),
        "genres": meta.get("genres", []),
        "logline": meta.get("logline", ""),
        "created": str(meta.get("created", "")),
        "last_touched": str(meta.get("last_touched", "")),
        "promoted_to": meta.get("promoted_to"),
        "body": body.strip(),
    })


@mcp.tool()
def update_idea(slug: str, field: str, value: str) -> str:
    """Update a single frontmatter field of an existing idea.

    Args:
        slug:  The idea's slug.
        field: The frontmatter key to update (e.g. "status", "logline").
        value: The new value as a string.
    """
    config = load_config()
    ideas_dir = _get_ideas_dir(config)
    result = _read_idea(ideas_dir, slug)

    if result is None:
        return json.dumps({"error": f"Idea '{slug}' not found"})

    meta, body = result
    meta[field] = value
    meta["last_touched"] = date.today().isoformat()

    _write_idea(_idea_path(ideas_dir, slug), meta, body)
    _cache.invalidate()
    return json.dumps({"success": True, "slug": slug, "field": field, "value": value})


@mcp.tool()
def promote_idea(slug: str, book_slug: str) -> str:
    """Mark an idea as promoted and link it to a book project.

    Sets status to "promoted" and records the book slug in promoted_to.

    Args:
        slug:      The idea's slug.
        book_slug: The slug of the book project this idea was turned into.
    """
    config = load_config()
    ideas_dir = _get_ideas_dir(config)
    result = _read_idea(ideas_dir, slug)

    if result is None:
        return json.dumps({"error": f"Idea '{slug}' not found"})

    meta, body = result
    meta["status"] = "promoted"
    meta["promoted_to"] = book_slug
    meta["last_touched"] = date.today().isoformat()

    _write_idea(_idea_path(ideas_dir, slug), meta, body)
    _cache.invalidate()
    return json.dumps({"success": True, "slug": slug, "promoted_to": book_slug})


# ============================================================
# Quality Gates
# ============================================================


@mcp.tool()
def validate_book_structure(book_slug: str) -> str:
    """Validate book project structure completeness."""
    config = load_config()
    project_dir = resolve_project_path(config, book_slug)

    if not project_dir.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    checks = []

    # Issue #17: accept aliases (worldbuilding/, world-building/) for the
    # world directory so non-canonical scaffolds still validate.
    world_dir = resolve_world_dir(project_dir) or (project_dir / "world")
    world_setting = world_dir / "setting.md"

    # Required files
    for name, path in [
        ("README.md", project_dir / "README.md"),
        ("synopsis.md", project_dir / "synopsis.md"),
        ("plot/outline.md", project_dir / "plot" / "outline.md"),
        ("characters/INDEX.md", project_dir / "characters" / "INDEX.md"),
        (f"{world_dir.name}/setting.md", world_setting),
    ]:
        checks.append({"check": name, "status": "PASS" if path.exists() else "FAIL"})

    # Chapter checks
    chapters = find_chapters(config, book_slug)
    checks.append({
        "check": "Has chapters",
        "status": "PASS" if chapters else "WARN",
        "detail": f"{len(chapters)} chapters found",
    })

    # Character checks
    chars = list((project_dir / "characters").glob("*.md"))
    char_count = len([c for c in chars if c.name != "INDEX.md"])
    checks.append({
        "check": "Has characters",
        "status": "PASS" if char_count > 0 else "WARN",
        "detail": f"{char_count} characters found",
    })

    passed = sum(1 for c in checks if c["status"] == "PASS")
    total = len(checks)

    return json.dumps({
        "book": book_slug,
        "checks": checks,
        "passed": passed,
        "total": total,
        "verdict": "PASS" if passed == total else "NEEDS WORK",
    })


@mcp.tool()
def run_pre_export_gates(book_slug: str) -> str:
    """Run quality gates before export."""
    state = _cache.get()
    book = state.get("books", {}).get(book_slug)
    if not book:
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    gates = []

    # All chapters must be Final
    chapters = book.get("chapters_data", {})
    non_final = [s for s, c in chapters.items() if c.get("status") != "Final"]
    gates.append({
        "gate": "All chapters Final",
        "status": "FAIL" if non_final else "PASS",
        "blocking": True,
        "detail": f"Not final: {', '.join(non_final)}" if non_final else "All final",
    })

    # Has at least one chapter
    gates.append({
        "gate": "Has chapters",
        "status": "PASS" if chapters else "FAIL",
        "blocking": True,
        "detail": f"{len(chapters)} chapters",
    })

    # Word count check
    total_words = book.get("total_words", 0)
    target = book.get("target_word_count", 0)
    word_ok = total_words >= target * 0.8 if target else total_words > 0
    gates.append({
        "gate": "Word count target",
        "status": "PASS" if word_ok else "WARN",
        "blocking": False,
        "detail": f"{total_words}/{target} words ({round(total_words/target*100) if target else 0}%)",
    })

    # Has synopsis
    config = load_config()
    synopsis = resolve_project_path(config, book_slug) / "synopsis.md"
    synopsis_words = count_words_in_file(synopsis) if synopsis.exists() else 0
    gates.append({
        "gate": "Synopsis written",
        "status": "PASS" if synopsis_words > 50 else "WARN",
        "blocking": False,
        "detail": f"{synopsis_words} words",
    })

    blocking_fails = [g for g in gates if g["blocking"] and g["status"] == "FAIL"]
    verdict = "BLOCKED" if blocking_fails else "READY"

    return json.dumps({
        "book": book_slug,
        "gates": gates,
        "verdict": verdict,
        "message": f"{'Export blocked by ' + str(len(blocking_fails)) + ' gate(s)' if blocking_fails else 'Ready for export'}",
    })


# ============================================================
# Genre Tools
# ============================================================


@mcp.tool()
def list_genres() -> str:
    """List all available genres."""
    genres_dir = get_genres_dir()
    if not genres_dir.exists():
        return json.dumps({"genres": [], "count": 0})

    genres = sorted(
        d.name for d in genres_dir.iterdir()
        if d.is_dir() and (d / "README.md").exists()
    )
    return json.dumps({"genres": genres, "count": len(genres)})


@mcp.tool()
def get_genre(name: str) -> str:
    """Get genre README content."""
    genre_path = get_genres_dir() / name / "README.md"
    if not genre_path.exists():
        return json.dumps({"error": f"Genre '{name}' not found"})
    return genre_path.read_text(encoding="utf-8")


# ============================================================
# Reference Tools
# ============================================================


@mcp.tool()
def get_craft_reference(name: str) -> str:
    """Load a craft reference document (e.g. 'story-structure', 'dialog-craft').

    Args:
        name: Reference filename without .md extension
    """
    ref_path = get_reference_dir() / "craft" / f"{name}.md"
    if not ref_path.exists():
        # Try genre subfolder
        ref_path = get_reference_dir() / "genre" / f"{name}.md"
    if not ref_path.exists():
        return json.dumps({"error": f"Reference '{name}' not found"})
    return ref_path.read_text(encoding="utf-8")


@mcp.tool()
def list_craft_references() -> str:
    """List all available craft and genre reference documents."""
    result = {"craft": [], "genre": []}

    craft_dir = get_reference_dir() / "craft"
    if craft_dir.exists():
        result["craft"] = sorted(f.stem for f in craft_dir.glob("*.md"))

    genre_dir = get_reference_dir() / "genre"
    if genre_dir.exists():
        result["genre"] = sorted(f.stem for f in genre_dir.glob("*.md"))

    return json.dumps(result)


# ============================================================
# Per-Book CLAUDE.md Tools
# ============================================================


@mcp.tool()
def init_book_claudemd(
    book_slug: str,
    book_title: str = "",
    pov: str = "",
    tense: str = "",
    genre: str = "",
    writing_mode: str = "scene-by-scene",
    overwrite: bool = False,
) -> str:
    """Create CLAUDE.md from template in the book project root.

    Called by new-book after scaffolding a project. Populates the Book Facts
    section from the given metadata. Use overwrite=True to regenerate.

    Ephemeral state (current chapter, next beat) is NOT stored here — it
    belongs in the session cache (``update_session``) because it changes
    after every chapter.
    """
    config = load_config()
    facts = {
        "book_title": book_title or book_slug,
        "pov": pov,
        "tense": tense,
        "genre": genre,
        "writing_mode": writing_mode,
    }
    try:
        path = _init_claudemd_impl(
            config, Path(plugin_root), book_slug, facts=facts, overwrite=overwrite
        )
    except FileExistsError as exc:
        return json.dumps({"error": str(exc)})
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"path": str(path), "created": True})


@mcp.tool()
def get_book_claudemd(book_slug: str) -> str:
    """Read the current CLAUDE.md for a book."""
    config = load_config()
    try:
        content = _get_claudemd_impl(config, book_slug)
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"content": content})


@mcp.tool()
def get_character(book_slug: str, character_slug: str) -> str:
    """Read the full character file for a book.

    Args:
        book_slug: Book slug (exact match)
        character_slug: Character slug without extension
    """
    config = load_config()
    project_path = resolve_project_path(config, book_slug)
    if not project_path.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    # Primary layout: characters/{slug}.md
    primary = resolve_character_path(config, book_slug, character_slug)
    if primary.exists():
        return json.dumps({"content": primary.read_text(encoding="utf-8")})

    # Legacy layout: characters/{slug}/README.md
    legacy = project_path / "characters" / character_slug / "README.md"
    if legacy.exists():
        return json.dumps({"content": legacy.read_text(encoding="utf-8")})

    return json.dumps({"error": f"Character '{character_slug}' not found in book '{book_slug}'"})


@mcp.tool()
def append_book_rule(book_slug: str, text: str) -> str:
    """Append a rule to the Rules section of a book's CLAUDE.md."""
    config = load_config()
    try:
        path = _append_rule_impl(config, book_slug, text)
    except (FileNotFoundError, ValueError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"path": str(path), "kind": "rule", "text": text})


@mcp.tool()
def append_book_workflow(book_slug: str, text: str) -> str:
    """Append a workflow instruction to a book's CLAUDE.md."""
    config = load_config()
    try:
        path = _append_workflow_impl(config, book_slug, text)
    except (FileNotFoundError, ValueError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"path": str(path), "kind": "workflow", "text": text})


@mcp.tool()
def append_book_callback(book_slug: str, text: str) -> str:
    """Append a callback to the Callback Register of a book's CLAUDE.md."""
    config = load_config()
    try:
        path = _append_callback_impl(config, book_slug, text)
    except (FileNotFoundError, ValueError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"path": str(path), "kind": "callback", "text": text})


@mcp.tool()
def update_book_claudemd_facts(
    book_slug: str,
    pov: str = "",
    tense: str = "",
    genre: str = "",
    writing_mode: str = "",
) -> str:
    """Update one or more Book Facts fields in a book's CLAUDE.md.

    Empty strings are ignored (field left unchanged). Only stable facts
    live in CLAUDE.md; per-chapter progress belongs in the session cache.
    """
    config = load_config()
    provided = {
        "pov": pov,
        "tense": tense,
        "genre": genre,
        "writing_mode": writing_mode,
    }
    facts = {k: v for k, v in provided.items() if v}
    if not facts:
        return json.dumps({"error": "No fields provided"})
    try:
        path = _update_book_facts_impl(config, book_slug, facts)
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"path": str(path), "updated": list(facts.keys())})


@mcp.tool()
def sync_book_claudemd_from_text(book_slug: str, text: str) -> str:
    """Extract prefixed entries (Regel:/Workflow:/Callback:) and persist them.

    Used by the PreCompact hook: pass a text blob (e.g. recent session
    messages) and all matching lines are appended to the appropriate
    sections. Returns counts per kind.
    """
    config = load_config()
    entries = _extract_prefixed_lines(text)
    counts = {"rule": 0, "workflow": 0, "callback": 0, "errors": 0}
    errors: list[str] = []

    impl_map = {
        "rule": _append_rule_impl,
        "workflow": _append_workflow_impl,
        "callback": _append_callback_impl,
    }

    for kind, body in entries:
        try:
            impl_map[kind](config, book_slug, body)
            counts[kind] += 1
        except (FileNotFoundError, ValueError) as exc:
            counts["errors"] += 1
            errors.append(f"{kind}: {exc}")

    result: dict[str, Any] = {"counts": counts}
    if errors:
        result["errors"] = errors
    return json.dumps(result)


# ============================================================
# Snowflake Method: Scene List tools
# ============================================================

@mcp.tool()
def create_scene_list(
    book_slug: str,
    scenes: list[dict],
) -> str:
    """Create or overwrite plot/scenes.md with a scene list (Snowflake Step 8).

    Each scene dict may contain:
      - number (int, required): sequential scene number
      - chapter (str): e.g. "Ch. 01"
      - pov (str): POV character name
      - summary (str): one-sentence scene description
      - est_words (int): estimated word count
      - status (str): Planned / Written / Revised / Final

    Args:
        book_slug: Book project slug
        scenes: List of scene dicts describing each scene
    """
    config = load_config()
    project_dir = resolve_project_path(config, book_slug)
    if not project_dir.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    scenes_path = project_dir / "plot" / "scenes.md"

    title = book_slug.replace("-", " ").title()
    readme = project_dir / "README.md"
    if readme.exists():
        fm, _ = parse_frontmatter(readme.read_text(encoding="utf-8"))
        title = fm.get("title", title)

    header = (
        f"# Scene List: {title}\n\n"
        "*Generated by Snowflake Method — Step 8. "
        "Update status via MCP `update_scene()` as you write.*\n\n"
        "## Scene Index\n\n"
        "| # | Chapter | POV | Scene Summary | Est. Words | Status |\n"
        "|---|---------|-----|---------------|------------|--------|\n"
    )
    rows = []
    for s in scenes:
        num = s.get("number", "?")
        chapter = s.get("chapter", "")
        pov = s.get("pov", "")
        summary = s.get("summary", "")
        est_words = s.get("est_words", "")
        status = s.get("status", "Planned")
        rows.append(f"| {num} | {chapter} | {pov} | {summary} | {est_words} | {status} |")

    footer = (
        "\n## Status Key\n\n"
        "- **Planned** — Scene defined, not yet written\n"
        "- **Written** — First draft complete\n"
        "- **Revised** — At least one revision pass done\n"
        "- **Final** — Scene is locked\n\n"
        "## Notes\n\n"
        "*Cross-scene notes: recurring motifs, foreshadowing chains, POV balance.*\n"
    )

    content = header + "\n".join(rows) + "\n" + footer
    scenes_path.write_text(content, encoding="utf-8")
    _cache.invalidate()

    return json.dumps({
        "success": True,
        "path": str(scenes_path),
        "scene_count": len(scenes),
        "message": f"Scene list created with {len(scenes)} scenes at {scenes_path}",
    })


@mcp.tool()
def update_scene(
    book_slug: str,
    scene_number: int,
    chapter: str = "",
    pov: str = "",
    summary: str = "",
    est_words: str = "",
    status: str = "",
) -> str:
    """Update one scene row in plot/scenes.md (Snowflake Method).

    Only pass the fields you want to change — omitted fields are preserved.

    Args:
        book_slug: Book project slug
        scene_number: The scene's sequential number (# column)
        chapter: Chapter assignment, e.g. "Ch. 05"
        pov: POV character name
        summary: One-sentence scene summary
        est_words: Estimated word count (string, e.g. "1200")
        status: Planned / Written / Revised / Final
    """
    config = load_config()
    project_dir = resolve_project_path(config, book_slug)
    scenes_path = project_dir / "plot" / "scenes.md"

    if not scenes_path.exists():
        return json.dumps({"error": f"scenes.md not found for '{book_slug}'. Run create_scene_list first."})

    lines = scenes_path.read_text(encoding="utf-8").splitlines(keepends=True)
    updated = False

    for i, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        if cells[0] == str(scene_number):
            new_chapter = chapter if chapter else cells[1]
            new_pov = pov if pov else cells[2]
            new_summary = summary if summary else cells[3]
            new_est_words = est_words if est_words else cells[4]
            new_status = status if status else cells[5]
            lines[i] = (
                f"| {scene_number} | {new_chapter} | {new_pov} | "
                f"{new_summary} | {new_est_words} | {new_status} |\n"
            )
            updated = True
            break

    if not updated:
        return json.dumps({"error": f"Scene #{scene_number} not found in scenes.md"})

    scenes_path.write_text("".join(lines), encoding="utf-8")
    _cache.invalidate()

    return json.dumps({
        "success": True,
        "scene_number": scene_number,
        "path": str(scenes_path),
        "message": f"Scene #{scene_number} updated",
    })


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")
