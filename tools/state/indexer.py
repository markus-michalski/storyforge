"""State indexer for StoryForge — builds and maintains the state cache.

Scans the content directory for books, chapters, characters, and authors,
then writes a consolidated state.json for fast MCP tool queries.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.shared.config import CACHE_DIR, CONFIG_PATH, STATE_PATH, load_config
from tools.state.parsers import (
    count_words_in_file,
    derive_book_status,
    parse_author_profile,
    parse_book_readme,
    parse_chapter_readme,
    parse_character_file,
    parse_frontmatter,
    parse_series_readme,
)

SCHEMA_VERSION = "1.0.0"
PLUGIN_VERSION = "0.1.0-dev"


class StateCache:
    """Thread-safe in-memory state cache with staleness detection."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, Any] | None = None
        self._state_mtime: float = 0.0
        self._config_mtime: float = 0.0

    def get(self) -> dict[str, Any]:
        """Get current state, rebuilding if stale."""
        with self._lock:
            if self._is_stale():
                self._state = self._load_or_rebuild()
            return self._state or {}

    def invalidate(self) -> None:
        """Force a full rebuild on next access.

        Clears the in-memory state AND removes the on-disk cache file.
        Without deleting the file, ``_load_or_rebuild`` would reload the
        stale snapshot and silently serve pre-mutation data — the exact
        opposite of what callers expect after writing to disk.
        """
        with self._lock:
            self._state = None
            self._state_mtime = 0.0
            try:
                STATE_PATH.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                # Don't let a permissions / filesystem quirk block the cache clear.
                pass

    def _is_stale(self) -> bool:
        """Check if cached state is stale."""
        if self._state is None:
            return True

        if STATE_PATH.exists():
            mtime = STATE_PATH.stat().st_mtime
            if mtime > self._state_mtime:
                return True

        if CONFIG_PATH.exists():
            mtime = CONFIG_PATH.stat().st_mtime
            if mtime > self._config_mtime:
                return True

        return False

    def _load_or_rebuild(self) -> dict[str, Any]:
        """Load from cache file or rebuild from scratch."""
        if STATE_PATH.exists():
            try:
                data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
                if data.get("schema_version") == SCHEMA_VERSION:
                    self._state_mtime = STATE_PATH.stat().st_mtime
                    if CONFIG_PATH.exists():
                        self._config_mtime = CONFIG_PATH.stat().st_mtime
                    return data
            except (json.JSONDecodeError, KeyError):
                pass

        state = build_state()
        self._state_mtime = STATE_PATH.stat().st_mtime if STATE_PATH.exists() else 0.0
        return state


def build_state() -> dict[str, Any]:
    """Build complete state from content directory and write to cache."""
    config = load_config()
    content_root = Path(config["paths"]["content_root"])
    authors_root = Path(config["paths"]["authors_root"])

    state: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "plugin_version": PLUGIN_VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "books": {},
        "authors": {},
        "series": {},
        "ideas": [],
        "session": {
            "last_book": "",
            "last_chapter": "",
            "last_phase": "",
            "active_author": "",
        },
    }

    # Scan books
    projects_dir = content_root / "projects"
    if projects_dir.exists():
        state["books"] = _scan_books(projects_dir)

    # Scan authors
    if authors_root.exists():
        state["authors"] = _scan_authors(authors_root)

    # Scan series
    series_dir = content_root / "series"
    if series_dir.exists():
        state["series"] = _scan_series(series_dir)

    # Scan ideas
    ideas_dir = content_root / "ideas"
    state["ideas"] = _scan_ideas_dir(ideas_dir)

    _write_state(state)
    return state


def rebuild(preserve_session: bool = True) -> dict[str, Any]:
    """Rebuild state, optionally preserving session data."""
    old_session = {}
    if preserve_session and STATE_PATH.exists():
        try:
            old = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            old_session = old.get("session", {})
        except (json.JSONDecodeError, KeyError):
            pass

    state = build_state()

    if preserve_session and old_session:
        state["session"] = old_session

    _write_state(state)
    return state


# --- Scanners ---


def _scan_books(projects_dir: Path) -> dict[str, Any]:
    """Scan all book project directories."""
    books = {}

    for book_dir in sorted(projects_dir.iterdir()):
        readme = book_dir / "README.md"
        if not book_dir.is_dir() or not readme.exists():
            continue

        book = parse_book_readme(readme)
        slug = book["slug"]

        # Scan chapters
        chapters_dir = book_dir / "chapters"
        if chapters_dir.exists():
            book["chapters_data"] = _scan_chapters(chapters_dir)
            book["chapter_count"] = len(book["chapters_data"])
            book["total_words"] = sum(
                ch.get("word_count", 0) for ch in book["chapters_data"].values()
            )
        else:
            book["chapters_data"] = {}
            book["chapter_count"] = 0
            book["total_words"] = 0

        # Issue #19: derive effective status from chapter aggregates so the
        # book doesn't stay stuck at "Idea" after drafting begins. Preserve
        # the disk value separately for transparency / future migration.
        book["status_disk"] = book["status"]
        book["status"] = derive_book_status(book["status"], book["chapters_data"])

        # Scan characters
        chars_dir = book_dir / "characters"
        if chars_dir.exists():
            book["characters"] = _scan_characters(chars_dir)
            book["character_count"] = len(book["characters"])
        else:
            book["characters"] = {}
            book["character_count"] = 0

        books[slug] = book

    return books


def _scan_chapters(chapters_dir: Path) -> dict[str, Any]:
    """Scan all chapter directories within a book."""
    chapters = {}

    for ch_dir in sorted(chapters_dir.iterdir()):
        readme = ch_dir / "README.md"
        if not ch_dir.is_dir() or not readme.exists():
            continue

        chapter = parse_chapter_readme(readme)
        slug = chapter["slug"]

        # Count words in draft
        draft = ch_dir / "draft.md"
        chapter["word_count"] = count_words_in_file(draft)
        chapter["has_draft"] = draft.exists()

        chapters[slug] = chapter

    return chapters


def _scan_characters(chars_dir: Path) -> dict[str, Any]:
    """Scan all character files within a book."""
    characters = {}

    for char_file in sorted(chars_dir.glob("*.md")):
        if char_file.name == "INDEX.md":
            continue
        char = parse_character_file(char_file)
        characters[char["slug"]] = char

    return characters


def _scan_authors(authors_dir: Path) -> dict[str, Any]:
    """Scan all author profile directories."""
    authors = {}

    for author_dir in sorted(authors_dir.iterdir()):
        profile = author_dir / "profile.md"
        if not author_dir.is_dir() or not profile.exists():
            continue

        author = parse_author_profile(profile)
        # Count studied works
        studied = author_dir / "studied-works"
        if studied.exists():
            author["studied_works_count"] = len(list(studied.glob("analysis-*.md")))
        else:
            author["studied_works_count"] = 0

        authors[author["slug"]] = author

    return authors


def _scan_series(series_dir: Path) -> dict[str, Any]:
    """Scan all series directories."""
    all_series = {}

    for s_dir in sorted(series_dir.iterdir()):
        readme = s_dir / "README.md"
        if not s_dir.is_dir() or not readme.exists():
            continue

        series = parse_series_readme(readme)
        all_series[series["slug"]] = series

    return all_series


def _scan_ideas_dir(ideas_dir: Path) -> list[dict]:
    """Scan ideas/ directory and return a list of idea metadata dicts.

    Each .md file (excluding _archive/ subdirectory) is parsed for its
    YAML frontmatter. Non-.md files are silently ignored.
    """
    if not ideas_dir.exists():
        return []

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
        ideas.append({
            "slug": meta.get("slug", md_file.stem),
            "title": meta.get("title", md_file.stem),
            "status": meta.get("status", "raw"),
            "genres": meta.get("genres", []),
            "logline": meta.get("logline", ""),
            "created": str(meta.get("created", "")),
            "last_touched": str(meta.get("last_touched", "")),
            "promoted_to": meta.get("promoted_to"),
        })

    return ideas


def _write_state(state: dict[str, Any]) -> None:
    """Write state to cache file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
