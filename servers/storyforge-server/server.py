"""StoryForge MCP Server — FastMCP-based tool server for book writing workflow."""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

# Ensure tools directory is on path
plugin_root = os.environ.get(
    "CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent.parent)
)
tools_path = str(Path(plugin_root) / "tools")
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

from mcp.server.fastmcp import FastMCP

from tools.shared.config import load_config, get_content_root, get_authors_root, get_genres_dir, get_reference_dir, get_templates_dir
from tools.shared.paths import slugify, resolve_project_path, resolve_chapter_path, resolve_author_path, find_projects, find_chapters, find_authors, find_series, resolve_series_path
from tools.state.indexer import StateCache, build_state, rebuild
from tools.state.parsers import parse_frontmatter, count_words_in_file
from tools.analysis.repetition_checker import scan_repetitions, render_report

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
    """Get complete book data including all chapters and characters."""
    state = _cache.get()
    book = state.get("books", {}).get(slug)
    if not book:
        return json.dumps({"error": f"Book '{slug}' not found"})
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
    final = sum(1 for c in chapters.values() if c.get("status") == "Final")
    drafted = sum(1 for c in chapters.values() if c.get("status") in ("Draft", "Revision", "Polished", "Final"))
    total_words = book.get("total_words", 0)
    target = book.get("target_word_count", 0)

    return json.dumps({
        "slug": slug,
        "title": book.get("title", slug),
        "status": book.get("status", "Idea"),
        "chapters_total": total,
        "chapters_drafted": drafted,
        "chapters_final": final,
        "completion_percent": round(final / total * 100) if total else 0,
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
def rebuild_state() -> str:
    """Force rebuild of the state cache from filesystem."""
    state = rebuild(preserve_session=True)
    _cache.invalidate()
    books_count = len(state.get("books", {}))
    authors_count = len(state.get("authors", {}))
    return json.dumps({
        "success": True,
        "books": books_count,
        "authors": authors_count,
        "message": f"Rebuilt state: {books_count} books, {authors_count} authors",
    })


@mcp.tool()
def scan_book_repetitions(
    book_slug: str,
    min_occurrences: int = 2,
    write_report: bool = True,
    max_findings_per_category: int = 40,
) -> str:
    """Scan all chapter drafts of a book for repeated phrases, similes,
    character tells, blocking tics, and structural patterns.

    Returns the structured findings as JSON. When `write_report` is true,
    also writes a human-readable Markdown report to
    `<book>/research/repetition-report.md` and returns the path.

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
        report_file = research_dir / "repetition-report.md"
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
    (project_dir / "export" / "back-matter.md").write_text(f"# About the Author\n\n*Author bio.*\n\n# Also by [Author Name]\n\n*Other books.*\n", encoding="utf-8")

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
def update_field(file_path: str, field: str, value: str) -> str:
    """Update a frontmatter field in any markdown file."""
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    meta[field] = value

    import yaml
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
    """
    config = load_config()
    base = resolve_project_path(config, book_slug)

    if component:
        base = base / component
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


@mcp.tool()
def create_idea(title: str, genres: str = "", concept: str = "") -> str:
    """Save a book idea to IDEAS.md."""
    config = load_config()
    ideas_file = get_content_root(config) / "IDEAS.md"
    ideas_file.parent.mkdir(parents=True, exist_ok=True)

    entry = f"\n## {title}\n\n"
    if genres:
        entry += f"**Genres:** {genres}\n\n"
    if concept:
        entry += f"{concept}\n"
    entry += f"\n*Added: {date.today().isoformat()}*\n"

    if ideas_file.exists():
        content = ideas_file.read_text(encoding="utf-8")
    else:
        content = "# Book Ideas\n"

    content += entry
    ideas_file.write_text(content, encoding="utf-8")

    _cache.invalidate()
    return json.dumps({"success": True, "title": title})


@mcp.tool()
def list_ideas() -> str:
    """List all book ideas from IDEAS.md."""
    state = _cache.get()
    ideas = state.get("ideas", [])
    return json.dumps({"ideas": ideas, "count": len(ideas)})


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

    # Required files
    for name, path in [
        ("README.md", project_dir / "README.md"),
        ("synopsis.md", project_dir / "synopsis.md"),
        ("plot/outline.md", project_dir / "plot" / "outline.md"),
        ("characters/INDEX.md", project_dir / "characters" / "INDEX.md"),
        ("world/setting.md", project_dir / "world" / "setting.md"),
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
# Entry point
# ============================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")
