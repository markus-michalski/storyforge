"""Migrate vocabulary.md banned-word entries into author_discoveries DB.

Issue #293 — vocabulary.md Cluster C consolidation. Callable from both
scripts/migrate_vocabulary_to_db.py and tests.
"""

from __future__ import annotations

from pathlib import Path

from tools.author.vocabulary_parser import parse_vocabulary_banned_words
from tools.db.author_discoveries import insert_discovery
from tools.db.connection import open_authors_db


def migrate_author(author_slug: str, vocab_path: Path, *, execute: bool) -> int:
    """Parse vocab_path and insert banned-word entries into author_discoveries.

    Returns the number of rows actually inserted (0 in dry-run or when all
    entries are already present). Idempotent via UNIQUE ON CONFLICT IGNORE.
    """
    if not vocab_path.is_file():
        return 0

    text = vocab_path.read_text(encoding="utf-8")
    entries = parse_vocabulary_banned_words(text)

    if not entries or not execute:
        return 0

    conn = open_authors_db()
    inserted = 0
    try:
        for entry_text in entries:
            was_inserted = insert_discovery(
                conn,
                author_slug=author_slug,
                discovery_type="donts",
                text=entry_text,
            )
            if was_inserted:
                inserted += 1
    finally:
        conn.close()

    return inserted
