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


# Issue #17: book scaffolds occasionally use alternate names for the
# world-building directory. The MCP must recognize them so skill prerequisites
# (e.g. loading `world/setting.md` for the Travel Matrix) keep working without
# forcing users to rename their existing layout.
WORLD_DIR_CANDIDATES: tuple[str, ...] = ("world", "worldbuilding", "world-building")


def resolve_world_dir(project_dir: Path) -> Path | None:
    """Return the existing world-building directory under ``project_dir``.

    Tries the canonical ``world/`` first, then known aliases. Returns ``None``
    when none exists, leaving the caller to decide whether to use the
    canonical default for new content.
    """
    for name in WORLD_DIR_CANDIDATES:
        candidate = project_dir / name
        if candidate.exists():
            return candidate
    return None


def resolve_character_path(
    config: dict[str, Any], book_slug: str, character_slug: str
) -> Path:
    """Resolve path for a character file within a book."""
    return resolve_project_path(config, book_slug) / "characters" / f"{character_slug}.md"


# Path E #59: memoir books store real-people profiles under `people/`
# instead of `characters/`. Scaffolded by `new-book` (#63), populated by
# the memoir-mode branch of `character-creator`. The candidate list runs
# `people/` first so memoir books resolve there even when a stray legacy
# `characters/` directory exists alongside it.
PEOPLE_DIR_CANDIDATES: tuple[str, ...] = ("people", "characters")


def resolve_people_dir(project_dir: Path, book_category: str = "fiction") -> Path:
    """Return the directory holding character / real-person profile files.

    For memoir books, prefers ``people/`` and falls back to ``characters/``
    when the memoir layout has not been scaffolded yet (legacy memoir books
    written before #63 / #59 land). For fiction, always returns
    ``characters/``.

    The returned path may not exist — callers decide whether to create it
    or treat absence as an empty cast.
    """
    if book_category == "memoir":
        for name in PEOPLE_DIR_CANDIDATES:
            candidate = project_dir / name
            if candidate.exists():
                return candidate
        # Neither exists yet — return the canonical memoir path.
        return project_dir / "people"
    return project_dir / "characters"


def resolve_person_path(
    config: dict[str, Any],
    book_slug: str,
    person_slug: str,
    book_category: str = "fiction",
) -> Path:
    """Resolve path for a person / character file within a book.

    Memoir books resolve to ``people/{slug}.md``; fiction books to
    ``characters/{slug}.md``.
    """
    return resolve_people_dir(
        resolve_project_path(config, book_slug), book_category
    ) / f"{person_slug}.md"


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
