"""Markdown and YAML frontmatter parsers for StoryForge project files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# Pre-compiled patterns
_RE_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter and body from markdown text.

    Returns (metadata_dict, body_text).
    """
    match = _RE_FRONTMATTER.match(text)
    if not match:
        return {}, text

    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        meta = {}

    body = text[match.end():]
    return meta, body


def parse_book_readme(path: Path) -> dict[str, Any]:
    """Parse a book project README.md into structured data."""
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    return {
        "slug": path.parent.name,
        "title": meta.get("title", path.parent.name),
        "author": meta.get("author", ""),
        "genres": meta.get("genres", []),
        "book_type": meta.get("book_type", "novel"),
        "status": _normalize_book_status(meta.get("status", "Idea")),
        "language": meta.get("language", "en"),
        "target_word_count": meta.get("target_word_count", 0),
        "series": meta.get("series", ""),
        "series_number": meta.get("series_number", 0),
        "description": meta.get("description", ""),
        "created": str(meta.get("created", "")),
        "updated": str(meta.get("updated", "")),
    }


def parse_chapter_readme(path: Path) -> dict[str, Any]:
    """Parse a chapter README.md into structured data."""
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    return {
        "slug": path.parent.name,
        "title": meta.get("title", path.parent.name),
        "number": meta.get("number", _extract_number(path.parent.name)),
        "status": _normalize_chapter_status(meta.get("status", "Outline")),
        "pov_character": meta.get("pov_character", ""),
        "summary": meta.get("summary", ""),
        "word_count_target": meta.get("word_count_target", 0),
    }


def parse_character_file(path: Path) -> dict[str, Any]:
    """Parse a character markdown file into structured data."""
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    return {
        "slug": path.stem,
        "name": meta.get("name", path.stem),
        "role": meta.get("role", "supporting"),
        "status": _normalize_character_status(meta.get("status", "Concept")),
        "age": meta.get("age", ""),
        "gender": meta.get("gender", ""),
        "description": meta.get("description", ""),
    }


def parse_author_profile(path: Path) -> dict[str, Any]:
    """Parse an author profile.md into structured data."""
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    return {
        "slug": path.parent.name,
        "name": meta.get("name", path.parent.name),
        "primary_genres": meta.get("primary_genres", []),
        "narrative_voice": meta.get("narrative_voice", "third-limited"),
        "tense": meta.get("tense", "past"),
        "tone": meta.get("tone", []),
        "sentence_style": meta.get("sentence_style", "varied"),
        "vocabulary_level": meta.get("vocabulary_level", "moderate"),
        "dialog_style": meta.get("dialog_style", "naturalistic"),
        "pacing": meta.get("pacing", "tension-driven"),
        "themes": meta.get("themes", []),
        "influences": meta.get("influences", []),
        "avoid": meta.get("avoid", []),
        "created": str(meta.get("created", "")),
        "updated": str(meta.get("updated", "")),
    }


def parse_series_readme(path: Path) -> dict[str, Any]:
    """Parse a series README.md into structured data."""
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    return {
        "slug": path.parent.name,
        "title": meta.get("title", path.parent.name),
        "genres": meta.get("genres", []),
        "planned_books": meta.get("planned_books", 0),
        "status": meta.get("status", "Planning"),
        "description": meta.get("description", ""),
    }


def count_words_in_file(path: Path) -> int:
    """Count words in a markdown file (body only, no frontmatter)."""
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    return len(body.split())


def _extract_number(dirname: str) -> int:
    """Extract number from dirname like '01-the-beginning'."""
    match = re.match(r"^(\d+)", dirname)
    return int(match.group(1)) if match else 0


# --- Status normalization ---

_BOOK_STATUS_MAP = {
    "idea": "Idea",
    "concept": "Concept",
    "research": "Research",
    "plot outlined": "Plot Outlined",
    "characters created": "Characters Created",
    "world built": "World Built",
    "drafting": "Drafting",
    "revision": "Revision",
    "editing": "Editing",
    "proofread": "Proofread",
    "export ready": "Export Ready",
    "published": "Published",
}

_CHAPTER_STATUS_MAP = {
    "outline": "Outline",
    "draft": "Draft",
    "revision": "Revision",
    "polished": "Polished",
    "final": "Final",
}

_CHARACTER_STATUS_MAP = {
    "concept": "Concept",
    "profile": "Profile",
    "backstory": "Backstory",
    "arc defined": "Arc Defined",
    "final": "Final",
}


def _normalize_book_status(raw: str) -> str:
    """Normalize book status string to canonical form."""
    if not raw:
        return "Idea"
    return _BOOK_STATUS_MAP.get(raw.strip().lower(), raw.strip())


def _normalize_chapter_status(raw: str) -> str:
    """Normalize chapter status string to canonical form."""
    if not raw:
        return "Outline"
    return _CHAPTER_STATUS_MAP.get(raw.strip().lower(), raw.strip())


def _normalize_character_status(raw: str) -> str:
    """Normalize character status string to canonical form."""
    if not raw:
        return "Concept"
    return _CHARACTER_STATUS_MAP.get(raw.strip().lower(), raw.strip())
