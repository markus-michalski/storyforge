"""SQLite connection management for StoryForge — Issues #280 / #281.

DB layout:
  ~/.storyforge/db/{series-slug}.db  — canon_facts + character_snapshots per series
  ~/.storyforge/db/storyforge.db     — global sessions table
  ~/.storyforge/db/authors.db        — author_discoveries (global, cross-series)

All tables are created lazily via ensure_schema() / ensure_authors_schema().
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tools.shared.config import CACHE_DIR

DB_DIR = CACHE_DIR.parent / "db"


def open_db(db_path: Path) -> sqlite3.Connection:
    """Open (and create) a SQLite DB at db_path, return connection."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create series/session tables and indexes if they don't exist yet (idempotent)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS canon_facts (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            book_num         INTEGER NOT NULL,
            chapter_num      INTEGER NOT NULL,
            subject          TEXT NOT NULL,
            fact             TEXT NOT NULL,
            domain           TEXT DEFAULT '',
            is_revision      BOOLEAN DEFAULT FALSE,
            old_value        TEXT,
            revision_impacts TEXT,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(book_num, chapter_num, subject, fact)
        );

        CREATE INDEX IF NOT EXISTS idx_cf
            ON canon_facts(book_num, chapter_num);

        CREATE INDEX IF NOT EXISTS idx_cf_subject
            ON canon_facts(book_num, subject);

        CREATE TABLE IF NOT EXISTS sessions (
            user_id           TEXT PRIMARY KEY,
            current_book_slug TEXT DEFAULT '',
            current_chapter   TEXT DEFAULT '',
            next_beat         TEXT DEFAULT '',
            notes             TEXT DEFAULT '{}',
            last_updated      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS character_snapshots (
            char_slug               TEXT NOT NULL,
            book_num                INTEGER NOT NULL,
            chapter_num             INTEGER NOT NULL,
            injuries                TEXT,
            clothing                TEXT,
            inventory               TEXT,
            altered_states          TEXT,
            environmental_limiters  TEXT DEFAULT '',
            updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (char_slug, book_num, chapter_num)
        );

        CREATE INDEX IF NOT EXISTS idx_cs
            ON character_snapshots(char_slug, book_num, chapter_num);
    """)
    conn.commit()


def ensure_authors_schema(conn: sqlite3.Connection) -> None:
    """Create the author_discoveries table and index (idempotent) — Issue #281."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS author_discoveries (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            author_slug    TEXT NOT NULL,
            discovery_type TEXT NOT NULL,
            text           TEXT NOT NULL,
            book_slug      TEXT DEFAULT '',
            source_genres  TEXT DEFAULT '',
            universal      BOOLEAN DEFAULT FALSE,
            example        TEXT DEFAULT '',
            date_added     TEXT DEFAULT '',
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(author_slug, discovery_type, text)
        );

        CREATE INDEX IF NOT EXISTS idx_ad
            ON author_discoveries(author_slug, discovery_type);
    """)
    conn.commit()


def get_authors_db_path() -> Path:
    """Return the path to the global author_discoveries database."""
    return DB_DIR / "authors.db"


def open_authors_db() -> sqlite3.Connection:
    """Open the global authors DB (author_discoveries table)."""
    path = get_authors_db_path()
    conn = open_db(path)
    try:
        ensure_authors_schema(conn)
    except sqlite3.Error:
        conn.close()
        raise
    return conn


def get_canon_db_path(series_or_book_slug: str) -> Path:
    """Return the DB path for a given series or standalone book slug."""
    return DB_DIR / f"{series_or_book_slug}.db"


def get_session_db_path() -> Path:
    """Return the path to the global sessions database."""
    return DB_DIR / "storyforge.db"


def open_canon_db(series_or_book_slug: str) -> sqlite3.Connection:
    """Open the canon_facts DB for a series or standalone book."""
    path = get_canon_db_path(series_or_book_slug)
    conn = open_db(path)
    try:
        ensure_schema(conn)
    except sqlite3.Error:
        conn.close()
        raise
    return conn


def open_session_db() -> sqlite3.Connection:
    """Open the global sessions DB."""
    path = get_session_db_path()
    conn = open_db(path)
    try:
        ensure_schema(conn)
    except sqlite3.Error:
        conn.close()
        raise
    return conn


def _read_book_meta(book_root: Path) -> dict:
    """Read and return parsed frontmatter for a book's README.md, or {}."""
    readme = book_root / "README.md"
    if not readme.exists():
        return {}
    try:
        from tools.state.parsers import parse_frontmatter
        text = readme.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(text)
        return meta if isinstance(meta, dict) else {}
    except (OSError, ValueError):
        return {}


def get_book_series_slug(book_root: Path) -> str:
    """Read the series slug from a book's README.md frontmatter.

    Returns empty string if the book has no series or the file can't be read.
    """
    return str(_read_book_meta(book_root).get("series", "")).strip()


def get_book_num(book_root: Path) -> int:
    """Read series_number from a book's README.md frontmatter (default 1).

    Used by both the migration script and brief assemblers so book_num is
    always derived the same way from the same source (Issue #280 H1 fix).
    """
    try:
        return int(_read_book_meta(book_root).get("series_number", 1)) or 1
    except (TypeError, ValueError):
        return 1


def get_db_slug_for_book(book_root: Path) -> str:
    """Return the DB name (series slug or book slug) for a book directory."""
    series = get_book_series_slug(book_root)
    return series if series else book_root.name
