#!/usr/bin/env python3
"""Migrate vocabulary.md banned-word entries → author_discoveries SQLite table.

Issue #293 — vocabulary.md Cluster C consolidation. Parses all
'## Banned Words' sections from each author's vocabulary.md and inserts
them as discovery_type='donts'. Idempotent — re-running silently skips
entries already present (UNIQUE ON CONFLICT IGNORE).

Only banned-word bullets are migrated. Reference tables (Preferred
Vocabulary, Character Voice Templates, Sentence Patterns) remain in
vocabulary.md as read-only reference material.

Usage:
  python scripts/migrate_vocabulary_to_db.py           # dry-run (safe)
  python scripts/migrate_vocabulary_to_db.py --execute # write to DB
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.author.vocabulary_migrator import migrate_author  # noqa: E402
from tools.author.vocabulary_parser import parse_vocabulary_banned_words  # noqa: E402
from tools.shared.config import load_config  # noqa: E402

DRY_RUN = "--execute" not in sys.argv


def _log(msg: str) -> None:
    prefix = "[DRY-RUN] " if DRY_RUN else "[EXEC]    "
    print(f"{prefix}{msg}")


def main() -> None:
    if DRY_RUN:
        print("=" * 60)
        print("DRY-RUN MODE — no DB writes")
        print("Run with --execute to apply")
        print("=" * 60)
    else:
        print("=" * 60)
        print("EXECUTING MIGRATION")
        print("=" * 60)

    config = load_config()
    authors_root = Path(config["paths"]["authors_root"])

    if not authors_root.is_dir():
        print(f"No authors directory found at {authors_root}")
        return

    author_dirs = [d for d in sorted(authors_root.iterdir()) if d.is_dir()]
    print(f"\nFound {len(author_dirs)} author(s):\n")

    total_found = 0
    total_inserted = 0

    for author_dir in author_dirs:
        slug = author_dir.name
        vocab_path = author_dir / "vocabulary.md"

        if not vocab_path.is_file():
            print(f"  SKIP: {slug} — no vocabulary.md")
            continue

        text = vocab_path.read_text(encoding="utf-8")
        entries = parse_vocabulary_banned_words(text)

        if not entries:
            print(f"  SKIP: {slug} — no banned-word entries found")
            continue

        total_found += len(entries)
        inserted = migrate_author(slug, vocab_path, execute=not DRY_RUN)
        total_inserted += inserted

        _log(f"{slug}: {len(entries)} entries found, {inserted} inserted")

    print(f"\n{'=' * 60}")
    if DRY_RUN:
        print(f"Dry-run complete. Would process ~{total_found} entries across all authors.")
        print("Rerun with --execute to write to DB.")
    else:
        print(f"Migration complete. {total_inserted} rows inserted (duplicates silently skipped).")
        print("\nvocabulary.md files are preserved as read-only reference archives.")


if __name__ == "__main__":
    main()
