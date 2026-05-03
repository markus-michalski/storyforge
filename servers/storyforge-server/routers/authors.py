"""Author-profile CRUD tools: list/get/create/update.

Issue #151 also adds ``harvest_book_rules`` here — the harvest tool produces
author-level promotion candidates from a book's CLAUDE.md ``## Rules`` section,
so it lives next to the rest of the author state surface.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import yaml

from tools.author.rule_harvester import harvest
from tools.claudemd.rules_editor import (
    MarkersNotFoundError,
    list_rules,
)
from tools.shared.paths import (
    resolve_author_path,
    resolve_project_path,
    slugify,
)
from tools.state.parsers import parse_author_profile, parse_book_readme, parse_frontmatter

from . import _app
from ._app import _cache, mcp


@mcp.tool()
def list_authors() -> str:
    """List all author profiles."""
    state = _cache.get()
    authors = state.get("authors", {})
    result = [
        {
            "slug": slug,
            "name": a.get("name", slug),
            "genres": a.get("primary_genres", []),
            "studied_works": a.get("studied_works_count", 0),
        }
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
    config = _app.load_config()
    vocab_path = resolve_author_path(config, slug) / "vocabulary.md"
    if vocab_path.exists():
        author["vocabulary"] = vocab_path.read_text(encoding="utf-8")

    return json.dumps(author)


@mcp.tool()
def create_author(
    name: str, genres: str = "", tone: str = "", voice: str = "third-limited", tense: str = "past"
) -> str:
    """Create a new author profile directory with template files.

    Args:
        name: Author pen name
        genres: Comma-separated primary genres
        tone: Comma-separated tone descriptors (e.g. "sarcastic, dark-humor")
        voice: Narrative voice (first-person, third-limited, third-omniscient, second-person)
        tense: Narrative tense (past, present)
    """
    config = _app.load_config()
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
    return json.dumps(
        {
            "success": True,
            "slug": slug,
            "path": str(author_dir),
            "message": f"Author profile '{name}' created at {author_dir}",
        }
    )


@mcp.tool()
def harvest_book_rules(book_slug: str, author_slug: str = "") -> str:
    """Collect promotion candidates from a book's findings (Issue #151).

    Walks the book's ``CLAUDE.md ## Rules`` section, classifies each rule as
    ``banned_phrase`` / ``style_principle`` / ``world_rule``, and dedupes
    against the author's profile + vocabulary. Returns a structured candidate
    list with per-entry recommendations (``promote`` / ``keep_book_only``).

    Args:
        book_slug: The book to harvest from.
        author_slug: Optional author slug. If empty, the book's README
            ``author`` field is used.

    Returns the issue-spec'd JSON:
    ``{"book_slug", "author_slug", "candidates": [...], "summary": {...}}``
    Each candidate carries ``id``, ``type``, ``value``, ``context``,
    ``evidence``, ``recommendation``, ``rationale``, ``source``,
    ``target_section``, and (for book-rule sources) ``source_rule_index``.

    On error returns ``{"error": "..."}`` — typical causes: book not found,
    CLAUDE.md missing RULES markers.
    """
    config = _app.load_config()

    book_dir = resolve_project_path(config, book_slug)
    if not book_dir.is_dir():
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    readme = book_dir / "README.md"
    book_meta: dict = {}
    if readme.is_file():
        book_meta = parse_book_readme(readme)

    resolved_author = author_slug.strip() or book_meta.get("author", "")

    try:
        parsed_rules = list_rules(config, book_slug)
    except MarkersNotFoundError as exc:
        return json.dumps({"error": f"Book CLAUDE.md missing RULES markers: {exc}"})
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc)})

    author_profile, vocabulary_text = _load_author_for_dedup(config, resolved_author)
    world_terms = _collect_world_terms(book_dir)

    result = harvest(
        book_slug=book_slug,
        author_slug=resolved_author or None,
        parsed_rules=parsed_rules,
        findings=None,  # manuscript findings integration is a follow-up
        author_profile=author_profile,
        vocabulary_text=vocabulary_text,
        world_terms=world_terms,
    )
    return json.dumps(result)


def _load_author_for_dedup(config: dict, author_slug: str) -> tuple[dict | None, str]:
    """Load author profile + vocabulary text for dedup. Missing files return defaults."""
    if not author_slug:
        return None, ""
    try:
        author_dir = resolve_author_path(config, author_slug)
    except (KeyError, ValueError):
        return None, ""

    profile_path = author_dir / "profile.md"
    profile = parse_author_profile(profile_path) if profile_path.is_file() else None

    vocab_path = author_dir / "vocabulary.md"
    vocab_text = vocab_path.read_text(encoding="utf-8") if vocab_path.is_file() else ""

    return profile, vocab_text


_BOLD_TERM_RE = re.compile(r"\*\*([^*]+)\*\*")
_BULLET_HEADING_RE = re.compile(r"^[-*]\s+\*\*([^*]+)\*\*", re.MULTILINE)


def _collect_world_terms(book_dir: Path) -> set[str]:
    """Build a case-insensitive set of canon/world/character terms.

    Sources walked:

    - ``world/glossary.md`` — bold terms in bullets
    - ``plot/canon-log.md`` — bold terms / headings
    - ``characters/*.md`` and ``people/*.md`` — file slugs and front-matter names

    The set feeds the rule classifier so glossary terms get marked
    ``world_rule`` and are excluded from author-profile promotion.
    """
    terms: set[str] = set()
    for rel in ("world/glossary.md", "plot/canon-log.md"):
        path = book_dir / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        terms.update(m.strip() for m in _BOLD_TERM_RE.findall(text) if m.strip())

    for sub in ("characters", "people"):
        char_dir = book_dir / sub
        if not char_dir.is_dir():
            continue
        for md_file in char_dir.glob("*.md"):
            if md_file.name == "INDEX.md":
                continue
            terms.add(md_file.stem.replace("-", " "))
            try:
                head = md_file.read_text(encoding="utf-8")[:2000]
                meta, _body = parse_frontmatter(head)
                name = meta.get("name") or meta.get("real_name")
                if isinstance(name, str) and name.strip():
                    terms.add(name.strip())
            except OSError:
                continue

    # Drop empty / whitespace-only entries defensively.
    return {t for t in terms if t.strip()}


@mcp.tool()
def update_author(slug: str, field: str, value: str) -> str:
    """Update a field in an author's profile frontmatter."""
    config = _app.load_config()
    profile_path = resolve_author_path(config, slug) / "profile.md"

    if not profile_path.exists():
        return json.dumps({"error": f"Author '{slug}' not found"})

    text = profile_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    meta[field] = value
    meta["updated"] = date.today().isoformat()

    new_text = "---\n" + yaml.dump(meta, default_flow_style=False, allow_unicode=True) + "---\n" + body
    profile_path.write_text(new_text, encoding="utf-8")

    _cache.invalidate()
    return json.dumps({"success": True, "field": field, "value": value})
