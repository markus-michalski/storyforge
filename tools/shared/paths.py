"""Path resolution utilities for StoryForge."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def resolve_project_path(config: dict[str, Any], book_slug: str) -> Path:
    """Resolve content root for a book project."""
    return Path(config["paths"]["content_root"]) / "projects" / book_slug


def resolve_chapter_path(
    config: dict[str, Any], book_slug: str, chapter_slug: str
) -> Path:
    """Resolve path for a chapter within a book."""
    return resolve_project_path(config, book_slug) / "chapters" / chapter_slug


def resolve_character_path(
    config: dict[str, Any], book_slug: str, character_slug: str
) -> Path:
    """Resolve path for a character file within a book."""
    return resolve_project_path(config, book_slug) / "characters" / f"{character_slug}.md"


def resolve_series_path(config: dict[str, Any], series_slug: str) -> Path:
    """Resolve path for a series directory."""
    return Path(config["paths"]["content_root"]) / "series" / series_slug


def resolve_author_path(config: dict[str, Any], author_slug: str) -> Path:
    """Resolve path for an author profile directory."""
    return Path(config["paths"]["authors_root"]) / author_slug


def find_projects(config: dict[str, Any]) -> list[Path]:
    """Find all book project directories under content root."""
    root = Path(config["paths"]["content_root"]) / "projects"
    if not root.exists():
        return []
    return sorted(
        p for p in root.iterdir() if p.is_dir() and (p / "README.md").exists()
    )


def find_chapters(config: dict[str, Any], book_slug: str) -> list[Path]:
    """Find all chapter directories within a book."""
    chapters_dir = resolve_project_path(config, book_slug) / "chapters"
    if not chapters_dir.exists():
        return []
    return sorted(
        p for p in chapters_dir.iterdir() if p.is_dir() and (p / "README.md").exists()
    )


def find_authors(config: dict[str, Any]) -> list[Path]:
    """Find all author profile directories."""
    root = Path(config["paths"]["authors_root"])
    if not root.exists():
        return []
    return sorted(
        p for p in root.iterdir() if p.is_dir() and (p / "profile.md").exists()
    )


def find_series(config: dict[str, Any]) -> list[Path]:
    """Find all series directories under content root."""
    root = Path(config["paths"]["content_root"]) / "series"
    if not root.exists():
        return []
    return sorted(
        p for p in root.iterdir() if p.is_dir() and (p / "README.md").exists()
    )
