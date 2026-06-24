#!/usr/bin/env python3
"""Migrate blood-and-binary to the new series directory layout (Issue #279).

What this script does:
  1. Converts series/blood-and-binary/README.md frontmatter → series.yaml (plain YAML)
  2. Strips the YAML frontmatter from README.md (keeps narrative content)
  3. Removes the books/ reference-link subdirectory (obsolete)
  4. Moves projects/blood-and-binary-firelight/ → series/blood-and-binary/firelight/
     (world/ travels with the book — series-level world separation is Phase 5)
  5. Updates ~/.storyforge/session.json if it references the old book slug
  6. Updates the broken book link in series/README.md

Usage:
  python scripts/migrate_series_layout.py           # dry-run (safe, no changes)
  python scripts/migrate_series_layout.py --execute # perform the migration
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import yaml

DRY_RUN = "--execute" not in sys.argv

BOOK_PROJECTS = Path("/media/markus-michalski/Projects/book-projects")
SERIES_DIR = BOOK_PROJECTS / "series" / "blood-and-binary"
OLD_BOOK_DIR = BOOK_PROJECTS / "projects" / "blood-and-binary-firelight"
NEW_BOOK_DIR = SERIES_DIR / "firelight"
SESSION_FILE = Path.home() / ".storyforge" / "session.json"


def log(msg: str) -> None:
    prefix = "[DRY-RUN] " if DRY_RUN else "[EXEC]    "
    print(f"{prefix}{msg}")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from body. Returns (meta_dict, body_str)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    yaml_block = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    return yaml.safe_load(yaml_block) or {}, body


# ---------------------------------------------------------------------------
# Step 1 + 2: series/README.md → series.yaml + clean README.md
# ---------------------------------------------------------------------------

def migrate_series_metadata() -> None:
    readme_path = SERIES_DIR / "README.md"
    series_yaml_path = SERIES_DIR / "series.yaml"

    if not readme_path.exists():
        print("  SKIP: series/README.md not found")
        return

    if series_yaml_path.exists():
        print("  SKIP: series.yaml already exists")
        return

    text = readme_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    series_data: dict = {
        "name": meta.get("title", "Blood & Binary"),
        "slug": meta.get("slug", "blood-and-binary"),
        "total_books": meta.get("planned_books", 3),
        "status": meta.get("status", "Planning"),
        "description": meta.get("description", ""),
        "author": "ethan-cole",
        "genres": meta.get("genres", []),
        "books": [
            {"slug": "firelight", "number": 1, "status": "drafting"},
        ],
    }

    log(f"Write series.yaml: {series_yaml_path}")
    if not DRY_RUN:
        series_yaml_path.write_text(
            yaml.dump(series_data, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    log(f"Strip frontmatter from README.md: {readme_path}")
    if not DRY_RUN:
        readme_path.write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# Step 3: Remove books/ subdirectory
# ---------------------------------------------------------------------------

def remove_books_subdir() -> None:
    books_dir = SERIES_DIR / "books"
    if not books_dir.exists():
        print("  SKIP: series/books/ already gone")
        return

    contents = list(books_dir.iterdir())
    log(f"Remove series/books/ ({len(contents)} file(s) inside): {books_dir}")
    if not DRY_RUN:
        shutil.rmtree(books_dir)


# ---------------------------------------------------------------------------
# Step 4: Move projects/blood-and-binary-firelight/ → series/blood-and-binary/firelight/
# ---------------------------------------------------------------------------

def migrate_book_directory() -> None:
    if not OLD_BOOK_DIR.exists():
        print(f"  SKIP: old book dir not found: {OLD_BOOK_DIR}")
        return

    if NEW_BOOK_DIR.exists():
        print(f"  SKIP: new book dir already exists: {NEW_BOOK_DIR}")
        return

    log(f"Move {OLD_BOOK_DIR}")
    log(f"  → {NEW_BOOK_DIR}")
    if not DRY_RUN:
        shutil.move(str(OLD_BOOK_DIR), str(NEW_BOOK_DIR))


# ---------------------------------------------------------------------------
# Step 5: Update ~/.storyforge/session.json
# ---------------------------------------------------------------------------

def update_session() -> None:
    if not SESSION_FILE.exists():
        print("  SKIP: session.json not found")
        return

    raw = SESSION_FILE.read_text(encoding="utf-8")
    if "blood-and-binary-firelight" not in raw:
        print("  SKIP: session.json does not reference old slug")
        return

    updated = raw.replace("blood-and-binary-firelight", "firelight")
    log(f"Update session.json: {SESSION_FILE}")
    if not DRY_RUN:
        SESSION_FILE.write_text(updated, encoding="utf-8")


# ---------------------------------------------------------------------------
# Step 6: Fix book link in series README.md
# ---------------------------------------------------------------------------

def fix_series_readme_link() -> None:
    readme_path = SERIES_DIR / "README.md"
    if not readme_path.exists():
        print("  SKIP: series/README.md not found")
        return

    text = readme_path.read_text(encoding="utf-8")
    old_link = "../../projects/blood-and-binary-firelight/"
    new_link = "firelight/"

    if old_link not in text:
        print("  SKIP: old link not found in README.md")
        return

    updated = text.replace(old_link, new_link)
    log(f"Fix book link in series README.md: {readme_path}")
    if not DRY_RUN:
        readme_path.write_text(updated, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if DRY_RUN:
        print("=" * 60)
        print("DRY-RUN MODE — no changes will be made")
        print("Run with --execute to apply")
        print("=" * 60)
    else:
        print("=" * 60)
        print("EXECUTING MIGRATION")
        print("=" * 60)

    print("\n[Step 1+2] Convert series README.md → series.yaml")
    migrate_series_metadata()

    print("\n[Step 3] Remove series/books/ subdirectory")
    remove_books_subdir()

    print("\n[Step 4] Move book: projects/blood-and-binary-firelight → series/blood-and-binary/firelight/")
    migrate_book_directory()

    print("\n[Step 5] Update ~/.storyforge/session.json")
    update_session()

    print("\n[Step 6] Fix book link in series README.md")
    fix_series_readme_link()

    print("\n" + "=" * 60)
    if DRY_RUN:
        print("Dry-run complete. Rerun with --execute to apply.")
    else:
        print("Migration complete.")
        print()
        print("Next steps:")
        print("  1. Verify: ls series/blood-and-binary/")
        print("  2. Verify: ls series/blood-and-binary/firelight/chapters/ | wc -l")
        print("  3. Restart Claude Code to reload the MCP server cache")


if __name__ == "__main__":
    main()
