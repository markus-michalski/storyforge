#!/usr/bin/env python3
"""Migration script: Phase 4 — book CLAUDE.md marker sections → book_rules SQLite table.

Reads existing <!-- RULES:START/END -->, <!-- CALLBACKS:START/END -->, and
<!-- WORKFLOW:START/END --> sections from each book's CLAUDE.md and inserts
the bullet entries into the book_rules DB table.

With --clear-markers, the bullet content is removed from the sections (keeping
empty markers), so the file becomes prose-only as expected by Phase 4.

Safe to re-run: INSERT OR IGNORE semantics (exact text duplicates are skipped).

Usage:
    python scripts/migrate_book_rules.py [--dry-run] [--clear-markers]
                                         [--content-root PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "servers" / "storyforge-server"))

from tools.claudemd.manager import append_callback, append_rule, append_workflow, resolve_claudemd_path
from tools.shared.config import load_config

# ---------------------------------------------------------------------------
# Marker pairs per entry type
# ---------------------------------------------------------------------------

_SECTIONS: list[tuple[str, str, str]] = [
    ("rule",     "<!-- RULES:START -->",     "<!-- RULES:END -->"),
    ("callback", "<!-- CALLBACKS:START -->", "<!-- CALLBACKS:END -->"),
    ("workflow", "<!-- WORKFLOW:START -->",  "<!-- WORKFLOW:END -->"),
]


def _extract_bullets(content: str, start_marker: str, end_marker: str) -> list[str]:
    """Return bullet body texts from a marker-delimited section."""
    start = content.find(start_marker)
    end   = content.find(end_marker)
    if start == -1 or end == -1:
        return []
    block = content[start + len(start_marker):end]

    bullets: list[str] = []
    current: list[str] = []
    for line in block.splitlines():
        if line.startswith("- "):
            if current:
                bullets.append("\n".join(current))
            current = [line[2:]]
        elif line.startswith("  ") and current:
            current.append(line[2:])
    if current:
        bullets.append("\n".join(current))
    return bullets


def _clear_section(content: str, start_marker: str, end_marker: str) -> str:
    """Replace the bullet content between markers with a blank line."""
    start = content.find(start_marker)
    end   = content.find(end_marker)
    if start == -1 or end == -1:
        return content
    inner_start = start + len(start_marker)
    return content[:inner_start] + "\n" + content[end:]


def migrate_book(
    book_slug: str,
    config: dict,
    *,
    dry_run: bool,
    clear_markers: bool,
) -> dict[str, int]:
    """Migrate one book's CLAUDE.md marker sections to the DB.

    Returns a dict mapping rule_type → number of entries inserted.
    """
    try:
        path = resolve_claudemd_path(config, book_slug)
    except FileNotFoundError:
        return {}

    if not path.exists():
        return {}

    content = path.read_text(encoding="utf-8")
    counts: dict[str, int] = {}

    _append_fn = {
        "rule":     append_rule,
        "callback": append_callback,
        "workflow": append_workflow,
    }

    for rule_type, start_marker, end_marker in _SECTIONS:
        bullets = _extract_bullets(content, start_marker, end_marker)
        inserted = 0
        for text in bullets:
            text = text.strip()
            if not text:
                continue
            if not dry_run:
                result = _append_fn[rule_type](config, book_slug, text)
                if result.get("inserted"):
                    inserted += 1
            else:
                inserted += 1  # count as would-be-inserted in dry-run
        counts[rule_type] = inserted

    if clear_markers and not dry_run:
        updated = content
        for _, start_marker, end_marker in _SECTIONS:
            updated = _clear_section(updated, start_marker, end_marker)
        if updated != content:
            path.write_text(updated, encoding="utf-8")

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without writing")
    parser.add_argument("--clear-markers", action="store_true", help="Remove bullet content from CLAUDE.md sections after migration")
    parser.add_argument("--content-root", help="Override content_root from config.yaml")
    args = parser.parse_args()

    config = load_config()
    if args.content_root:
        config.setdefault("paths", {})["content_root"] = args.content_root

    content_root = Path(config["paths"]["content_root"])
    projects_dir = content_root / "projects"
    if not projects_dir.exists():
        print(f"projects/ not found at {projects_dir}", file=sys.stderr)
        sys.exit(1)

    book_slugs = [d.name for d in sorted(projects_dir.iterdir()) if d.is_dir()]
    if not book_slugs:
        print("No books found.")
        return

    total_rules = total_callbacks = total_workflows = 0
    prefix = "[DRY RUN] " if args.dry_run else ""

    for slug in book_slugs:
        counts = migrate_book(slug, config, dry_run=args.dry_run, clear_markers=args.clear_markers)
        if not counts:
            continue
        r = counts.get("rule", 0)
        c = counts.get("callback", 0)
        w = counts.get("workflow", 0)
        if r + c + w == 0:
            continue
        total_rules     += r
        total_callbacks += c
        total_workflows += w
        print(f"{prefix}{slug}: {r} rules, {c} callbacks, {w} workflows")

    print(f"\n{prefix}Total: {total_rules} rules, {total_callbacks} callbacks, {total_workflows} workflows")
    if args.clear_markers and not args.dry_run:
        print("Marker sections cleared in CLAUDE.md files.")


if __name__ == "__main__":
    main()
