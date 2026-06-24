#!/usr/bin/env python3
"""Migration script: Phase 3 — profile.md Writing Discoveries + character YAML → SQLite.

Reads existing author profile.md files (Writing Discoveries section) and
character *.md YAML frontmatter (dynamic state fields) and inserts them into
the new SQLite tables (author_discoveries, character_snapshots).

Safe to re-run: INSERT OR IGNORE on discoveries, INSERT OR REPLACE on snapshots.

Usage:
    python scripts/migrate_phase3.py [--dry-run] [--storyforge-home PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Ensure the tools package is importable when run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "servers" / "storyforge-server"))

import yaml

from tools.db.author_discoveries import insert_discovery
from tools.db.character_snapshots import upsert_snapshot
from tools.db.connection import (
    ensure_authors_schema,
    get_authors_db_path,
    get_book_num,
    get_db_slug_for_book,
    open_canon_db,
    open_db,
)
from tools.state.parsers import parse_frontmatter


# ---------------------------------------------------------------------------
# Author discoveries migration
# ---------------------------------------------------------------------------

_RE_DISCOVERIES_SECTION = re.compile(
    r"^##\s+Writing\s+Discoveries\s*$(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
_RE_ORIGIN = re.compile(
    r"_\(\s*emerged\s+from\s+(?P<book>[a-z0-9][a-z0-9_-]*)\s*,\s*(?P<date>\d{4}-\d{2})\s*\)_",
    re.IGNORECASE,
)
_BUCKET_RE: list[tuple[str, re.Pattern[str]]] = [
    ("recurring_tics", re.compile(r"^###\s+Recurring\s+Tics\s*$", re.IGNORECASE)),
    ("style_principles", re.compile(r"^###\s+Style\s+Principles\s*$", re.IGNORECASE)),
    ("donts", re.compile(r"^###\s+Don[''`´]?ts.*$", re.IGNORECASE)),
]
_RE_PLACEHOLDER = re.compile(r"^_(?:frei|free|empty|tba|tbd)\.?_\s*$", re.IGNORECASE)
_RE_WHEN = re.compile(r"`when:\s*([^`\n]+)`")
_RE_EXAMPLE = re.compile(r"`example:`\s*\n((?:[ \t]*>[ \t]*.+\n?)+)", re.MULTILINE)


def _parse_discoveries_from_body(body: str) -> list[dict]:
    """Extract discoveries from profile.md body. Returns flat list of dicts."""
    section_m = _RE_DISCOVERIES_SECTION.search(body)
    if not section_m:
        return []

    section_text = section_m.group(1)
    entries: list[dict] = []
    current_type: str | None = None
    pending: list[str] = []

    def _flush() -> None:
        if not pending or current_type is None:
            return
        raw = "\n".join(pending)
        pending.clear()

        source_genres = ""
        when_m = _RE_WHEN.search(raw)
        if when_m:
            source_genres = when_m.group(1).strip()
            raw = _RE_WHEN.sub("", raw).strip()

        example = ""
        ex_m = _RE_EXAMPLE.search(raw)
        if ex_m:
            example = "\n".join(
                ln.strip().lstrip(">").strip()
                for ln in ex_m.group(1).splitlines()
                if ln.strip()
            )
            raw = raw[: ex_m.start()].strip()

        origins = [
            {"book": m.group("book"), "date": m.group("date")}
            for m in _RE_ORIGIN.finditer(raw)
        ]
        cleaned = _RE_ORIGIN.sub("", raw).rstrip(" \t_").strip()
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        if not cleaned:
            return

        book_slug = origins[0]["book"] if origins else ""
        date_added = origins[0]["date"] if origins else ""

        entries.append({
            "discovery_type": current_type,
            "text": cleaned,
            "book_slug": book_slug,
            "date_added": date_added,
            "source_genres": source_genres,
            "example": example,
        })

    for line in section_text.splitlines():
        stripped = line.strip()
        matched_bucket = next(
            (key for key, pat in _BUCKET_RE if pat.match(stripped)), None
        )
        if matched_bucket is not None:
            _flush()
            current_type = matched_bucket
            continue
        if current_type is None or _RE_PLACEHOLDER.match(stripped):
            continue
        if stripped.startswith("- "):
            _flush()
            pending.append(stripped[2:].strip())
        elif stripped and pending:
            pending.append(stripped)

    _flush()
    return entries


def migrate_author_discoveries(authors_root: Path, dry_run: bool) -> None:
    print(f"\n[author_discoveries] Scanning {authors_root} ...")
    if not authors_root.is_dir():
        print("  authors_root not found — skipping.")
        return

    db_path = get_authors_db_path()
    if not dry_run:
        conn = open_db(db_path)
        ensure_authors_schema(conn)
    else:
        conn = None

    total_inserted = 0
    total_skipped = 0

    for author_dir in sorted(authors_root.iterdir()):
        if not author_dir.is_dir():
            continue
        profile = author_dir / "profile.md"
        if not profile.is_file():
            continue

        author_slug = author_dir.name
        text = profile.read_text(encoding="utf-8")
        _, body = parse_frontmatter(text)
        entries = _parse_discoveries_from_body(body)

        for e in entries:
            label = f"  [{author_slug}] {e['discovery_type']}: {e['text'][:60]!r}"
            if dry_run:
                print(f"  [DRY] {label}")
                total_inserted += 1
            else:
                assert conn is not None
                inserted = insert_discovery(
                    conn,
                    author_slug=author_slug,
                    discovery_type=e["discovery_type"],
                    text=e["text"],
                    book_slug=e["book_slug"],
                    source_genres=e["source_genres"],
                    example=e["example"],
                    date_added=e["date_added"],
                )
                if inserted:
                    print(f"  INSERTED {label}")
                    total_inserted += 1
                else:
                    total_skipped += 1

    if conn is not None:
        conn.close()

    print(f"  Done: {total_inserted} inserted, {total_skipped} skipped (duplicates).")


# ---------------------------------------------------------------------------
# Character snapshots migration
# ---------------------------------------------------------------------------

_SNAPSHOT_MAP = {
    "current_injuries": "injuries",
    "current_clothing": "clothing",
    "current_inventory": "inventory",
    "altered_states": "altered_states",
    "environmental_limiters": "environmental_limiters",
    "as_of_chapter": "as_of_chapter",
}
_SNAPSHOT_LIST_FIELDS = {"injuries", "clothing", "inventory", "altered_states"}


def _read_char_snapshot_from_file(char_file: Path) -> dict | None:
    """Read dynamic state fields from character file frontmatter."""
    try:
        text = char_file.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(text)
    except (OSError, ValueError):
        return None

    snapshot = {}
    for src_key, dst_key in _SNAPSHOT_MAP.items():
        if src_key in meta:
            snapshot[dst_key] = meta[src_key]

    return snapshot if snapshot else None


def _parse_chapter_num(as_of: str) -> int:
    try:
        return int(str(as_of).split("-")[0])
    except (ValueError, IndexError):
        return 0


def migrate_character_snapshots(content_root: Path, dry_run: bool) -> None:
    print(f"\n[character_snapshots] Scanning {content_root} ...")
    projects_dir = content_root / "projects"
    if not projects_dir.is_dir():
        print("  projects/ not found — skipping.")
        return

    total_inserted = 0

    for book_dir in sorted(projects_dir.iterdir()):
        if not book_dir.is_dir():
            continue

        db_slug = get_db_slug_for_book(book_dir)
        book_num = get_book_num(book_dir)

        conn = open_canon_db(db_slug) if not dry_run else None
        try:
            for subdir in ("characters", "people"):
                chars_dir = book_dir / subdir
                if not chars_dir.is_dir():
                    continue

                for char_file in sorted(chars_dir.glob("*.md")):
                    if char_file.name.upper() == "INDEX.MD":
                        continue
                    snap = _read_char_snapshot_from_file(char_file)
                    if snap is None:
                        continue

                    char_slug = char_file.stem
                    chapter_num = _parse_chapter_num(snap.get("as_of_chapter", "0"))

                    # Normalize list fields (YAML may have already parsed them)
                    for field in _SNAPSHOT_LIST_FIELDS:
                        val = snap.get(field)
                        if isinstance(val, str):
                            snap[field] = [val] if val else []
                        elif not isinstance(val, list):
                            snap[field] = []

                    env = snap.get("environmental_limiters", "")
                    if isinstance(env, list):
                        env = ", ".join(env)

                    label = f"  [{db_slug}] {char_slug} ch{chapter_num}"
                    if dry_run:
                        print(f"  [DRY] {label}: inventory={snap.get('inventory', [])}")
                        total_inserted += 1
                    else:
                        assert conn is not None
                        upsert_snapshot(
                            conn,
                            char_slug=char_slug,
                            book_num=book_num,
                            chapter_num=chapter_num,
                            injuries=snap.get("injuries"),
                            clothing=snap.get("clothing"),
                            inventory=snap.get("inventory"),
                            altered_states=snap.get("altered_states"),
                            environmental_limiters=env or None,
                        )
                        print(f"  UPSERTED {label}")
                        total_inserted += 1
        finally:
            if conn is not None:
                conn.close()

    print(f"  Done: {total_inserted} snapshots written.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done, write nothing.")
    parser.add_argument(
        "--storyforge-home",
        default=str(Path.home() / ".storyforge"),
        help="Path to ~/.storyforge (default: %(default)s)",
    )
    parser.add_argument(
        "--content-root",
        default=None,
        help="Override content_root (default: read from config.yaml)",
    )
    args = parser.parse_args()

    storyforge_home = Path(args.storyforge_home)
    authors_root = storyforge_home / "authors"

    if args.content_root:
        content_root = Path(args.content_root)
    else:
        config_path = storyforge_home / "config.yaml"
        if not config_path.is_file():
            print(f"Config not found at {config_path}. Pass --content-root explicitly.")
            sys.exit(1)
        try:
            with config_path.open() as f:
                config = yaml.safe_load(f)
            content_root = Path(config["paths"]["content_root"])
        except (KeyError, TypeError) as exc:
            print(f"Could not read content_root from config: {exc}")
            sys.exit(1)

    print(f"StoryForge home : {storyforge_home}")
    print(f"Authors root    : {authors_root}")
    print(f"Content root    : {content_root}")
    print(f"Dry run         : {args.dry_run}")

    migrate_author_discoveries(authors_root, dry_run=args.dry_run)
    migrate_character_snapshots(content_root, dry_run=args.dry_run)

    print("\nMigration complete.")


if __name__ == "__main__":
    main()
