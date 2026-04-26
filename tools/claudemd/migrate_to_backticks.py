"""One-shot migration: convert ban-cued double-quoted phrases in a book's
``CLAUDE.md`` to backtick form so the PostToolUse hook (issue #70) can
hard-block them.

The validate_chapter hook only honors backtick-wrapped patterns as
hard-block triggers (see ``hooks/validate_chapter.py``). Existing rules
that were persisted before the strictness change use double quotes; this
script rewrites them in-place under the same heuristic that
``tools.claudemd.manager._normalize_banned_phrase`` applies on append, so
new and old rules agree on format.

Usage::

    python -m tools.claudemd.migrate_to_backticks <book_path>           # dry-run
    python -m tools.claudemd.migrate_to_backticks <book_path> --apply   # interactive write

Without ``--apply`` the script prints a unified diff and exits. With
``--apply`` it asks for confirmation before writing.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

# Make the project root importable when run as a script.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.claudemd.manager import _normalize_banned_phrase


def _migrate_text(original: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Apply normalization line-by-line.

    Returns ``(new_content, changes)`` where ``changes`` is a list of
    ``(line_number, before, after)`` tuples for changed lines only.
    """
    new_lines: list[str] = []
    changes: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(original.splitlines(), start=1):
        # Only consider markdown bullets — rules / callbacks / workflows.
        stripped = line.lstrip()
        if stripped.startswith("- "):
            new_line = _normalize_banned_phrase(line)
        else:
            new_line = line
        if new_line != line:
            changes.append((lineno, line, new_line))
        new_lines.append(new_line)

    new_content = "\n".join(new_lines)
    if original.endswith("\n"):
        new_content += "\n"
    return new_content, changes


def _print_diff(original: str, new_content: str, path: Path) -> None:
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=str(path),
        tofile=f"{path} (migrated)",
    )
    sys.stdout.writelines(diff)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert ban-cued double-quoted phrases in a book's CLAUDE.md "
            "to backtick form."
        ),
    )
    parser.add_argument(
        "book_path",
        type=Path,
        help="Path to the book directory (the one containing CLAUDE.md).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Prompt for confirmation, then write changes back to disk.",
    )
    args = parser.parse_args(argv)

    claudemd = args.book_path / "CLAUDE.md"
    if not claudemd.is_file():
        print(f"Error: {claudemd} not found.", file=sys.stderr)
        return 1

    original = claudemd.read_text(encoding="utf-8")
    new_content, changes = _migrate_text(original)

    if not changes:
        print("No changes needed — CLAUDE.md is already in backtick format.")
        return 0

    _print_diff(original, new_content, claudemd)
    print()
    print(f"{len(changes)} line(s) would change.")

    if not args.apply:
        print("Re-run with --apply to write.")
        return 0

    response = input("Apply these changes? [y/N] ").strip().lower()
    if response != "y":
        print("Aborted. No changes written.")
        return 0

    claudemd.write_text(new_content, encoding="utf-8")
    print(f"Wrote {claudemd} ({len(changes)} line(s) changed).")
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI entry point
    sys.exit(main())
