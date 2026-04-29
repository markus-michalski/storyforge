"""Content-creation tools: scaffold a book project, chapter directory, character file.

Memoir-specific creators (``create_person``, ``set_memoir_structure_type``)
live in :mod:`memoir` because they share the memoir-only validation
machinery.
"""

from __future__ import annotations

import json
from datetime import date

from tools.shared.paths import (
    resolve_chapter_path,
    resolve_project_path,
    slugify,
)

from . import _app
from ._app import _cache, mcp

# Path E (#54): allowed book_category values for create_book_structure.
# Phase 1 only ships fiction + memoir. Other non-fiction subtypes
# (biography, how-to, academic, history) are deferred per #49 / #97.
_ALLOWED_BOOK_CATEGORIES = ("fiction", "memoir")


@mcp.tool()
def create_book_structure(
    title: str,
    author: str = "",
    genres: str = "",
    book_type: str = "novel",
    book_category: str = "fiction",
    language: str = "en",
    target_word_count: int = 80000,
) -> str:
    """Create a new book project with full directory scaffold.

    Args:
        title: Book title
        author: Author profile slug
        genres: Comma-separated genres (e.g. "horror, supernatural")
        book_type: Length class (short-story, novelette, novella, novel, epic)
        book_category: Broad category (fiction, memoir). Default: fiction.
        language: Writing language
        target_word_count: Target word count
    """
    if book_category not in _ALLOWED_BOOK_CATEGORIES:
        allowed = ", ".join(_ALLOWED_BOOK_CATEGORIES)
        return json.dumps({"error": (f"Invalid book_category '{book_category}'. Allowed values: {allowed}.")})

    config = _app.load_config()
    slug = slugify(title)
    project_dir = resolve_project_path(config, slug)

    if project_dir.exists():
        return json.dumps({"error": f"Book '{slug}' already exists"})

    genre_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []
    today = date.today().isoformat()
    is_memoir = book_category == "memoir"

    # Create directory structure. Memoir scaffolds `people/` instead of
    # `characters/` and skips `world/` entirely (per #63 spec) — real-life
    # settings are documented via research, not invented.
    common_subdirs = ["plot", "research/notes", "chapters", "cover/art", "export/output", "translations"]
    if is_memoir:
        subdirs = common_subdirs + ["people"]
    else:
        subdirs = common_subdirs + ["characters", "world"]
    for subdir in subdirs:
        (project_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Book README
    readme = f"""---
title: "{title}"
slug: "{slug}"
author: "{author}"
genres: {json.dumps(genre_list)}
book_type: "{book_type}"
book_category: "{book_category}"
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
    (project_dir / "synopsis.md").write_text(
        f"# {title} — Synopsis\n\n*To be written after plot is outlined.*\n", encoding="utf-8"
    )

    # Plot files. Memoir uses structure-types instead of three-act / character
    # arcs; fiction keeps the existing scaffold.
    (project_dir / "plot" / "timeline.md").write_text(
        f"# {title} — Timeline\n\n*Chronological events.*\n", encoding="utf-8"
    )
    (project_dir / "plot" / "tone.md").write_text(
        f"# {title} — Tonal Document\n\n*Use /storyforge:plot-architect to develop after plot outline is complete.*\n",
        encoding="utf-8",
    )
    if is_memoir:
        (project_dir / "plot" / "outline.md").write_text(
            f"# {title} — Narrative Arc\n\n"
            "*The angle on the lived material — not invented events. "
            "Use /storyforge:plot-architect (memoir mode) to develop.*\n\n"
            "## Structure type\n\n"
            "*Pick one: chronological / thematic / braided / vignette. "
            "See `book_categories/memoir/craft/memoir-structure-types.md`.*\n\n"
            "## Through-line\n\n"
            "*The unifying question or theme that ties the chosen scenes together.*\n",
            encoding="utf-8",
        )
        (project_dir / "plot" / "structure.md").write_text(
            f"# {title} — Memoir Structure\n\n"
            "*Selected structure type and its scaffolding (chapter spine, "
            "thematic chapters, braid threads, or vignette index). "
            "Use /storyforge:plot-architect (memoir mode) to develop.*\n",
            encoding="utf-8",
        )
    else:
        (project_dir / "plot" / "outline.md").write_text(
            f"# {title} — Plot Outline\n\n## Act 1: Setup\n\n## Act 2: Confrontation\n\n## Act 3: Resolution\n",
            encoding="utf-8",
        )
        (project_dir / "plot" / "acts.md").write_text(
            f"# {title} — Act Structure\n\n*Use /storyforge:plot-architect to develop.*\n", encoding="utf-8"
        )
        (project_dir / "plot" / "arcs.md").write_text(
            f"# {title} — Character Arcs\n\n*Use /storyforge:character-creator to develop.*\n", encoding="utf-8"
        )

    # Characters / People
    if is_memoir:
        (project_dir / "people" / "INDEX.md").write_text(
            f"# {title} — Real People\n\n"
            "*Real people who appear in this memoir. Track consent and "
            "anonymization status per person. See "
            "`book_categories/memoir/craft/real-people-ethics.md`.*\n\n"
            "## Family\n\n"
            "## Friends & relationships\n\n"
            "## Public figures\n\n"
            "## Pseudonymized / composite\n",
            encoding="utf-8",
        )
    else:
        (project_dir / "characters" / "INDEX.md").write_text(
            f"# {title} — Characters\n\n## Protagonists\n\n## Antagonists\n\n## Supporting\n", encoding="utf-8"
        )

    # World — fiction only. Memoir documents real settings via research.
    if not is_memoir:
        (project_dir / "world" / "setting.md").write_text(
            f"# {title} — Setting\n\n*Where and when does the story take place?*\n", encoding="utf-8"
        )
        (project_dir / "world" / "rules.md").write_text(
            f"# {title} — Rules\n\n*Magic system, physics, society rules.*\n", encoding="utf-8"
        )
        (project_dir / "world" / "history.md").write_text(
            f"# {title} — History\n\n*Background history of the world.*\n", encoding="utf-8"
        )
        (project_dir / "world" / "glossary.md").write_text(
            f"# {title} — Glossary\n\n*Terms, places, concepts.*\n", encoding="utf-8"
        )

    # Research
    (project_dir / "research" / "sources.md").write_text(
        f"# {title} — Sources\n\n*Research materials and references.*\n", encoding="utf-8"
    )

    # Cover
    (project_dir / "cover" / "brief.md").write_text(
        f"# {title} — Cover Brief\n\n*Use /storyforge:cover-artist to develop.*\n", encoding="utf-8"
    )
    (project_dir / "cover" / "prompts.md").write_text(
        f"# {title} — Cover Prompts\n\n*AI art prompts will go here.*\n", encoding="utf-8"
    )

    # Export
    (project_dir / "export" / "front-matter.md").write_text(
        f'---\ntitle: "{title}"\nauthor: ""\ncopyright_year: {date.today().year}\n---\n\n# {title}\n\n*by [Author Name]*\n\nCopyright {date.today().year}\n\nAll rights reserved.\n',
        encoding="utf-8",
    )
    (project_dir / "export" / "back-matter.md").write_text(
        "# About the Author\n\n*Author bio.*\n\n# Also by [Author Name]\n\n*Other books.*\n", encoding="utf-8"
    )

    _cache.invalidate()
    return json.dumps(
        {
            "success": True,
            "slug": slug,
            "path": str(project_dir),
            "message": f"Book '{title}' created at {project_dir}",
        }
    )


@mcp.tool()
def create_chapter(book_slug: str, title: str, number: int, pov_character: str = "", summary: str = "") -> str:
    """Create a new chapter directory with README and empty draft."""
    config = _app.load_config()
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
    return json.dumps(
        {
            "success": True,
            "slug": slug,
            "path": str(ch_dir),
            "message": f"Chapter {number}: '{title}' created",
        }
    )


@mcp.tool()
def create_character(book_slug: str, name: str, role: str = "supporting", description: str = "") -> str:
    """Create a new character file in a book project (fiction mode).

    For memoir books (`book_category: memoir`), use `create_person` instead —
    the schema is different (no role/arc, instead relationship/consent_status).

    Args:
        book_slug: Book project slug
        name: Character name
        role: Role (protagonist, antagonist, supporting, minor)
        description: Brief description
    """
    config = _app.load_config()
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
    return json.dumps(
        {
            "success": True,
            "slug": slug,
            "path": str(char_path),
            "message": f"Character '{name}' created",
        }
    )
