#!/usr/bin/env python3
"""PostToolUse hook: validate character / people files after Write / Edit / MultiEdit.

Runs on writes to ``characters/*.md`` (fiction) and ``people/*.md`` (memoir).
Skips ``INDEX.md``. Two-tier severity:

- **block** — missing or invalid YAML frontmatter, missing required frontmatter
  fields. Hook exits 2 and Claude Code rejects the write.
- **warn**  — missing recommended sections, unknown role. Hook exits 0 and
  prints diagnostics to stdout.

The two-tier shape mirrors ``validate_chapter.py``: structural integrity is a
hard gate, content completeness is a soft signal so authors stay free to
diverge from the template when the story warrants it.

Required sections come from the post-#41 character template
(`templates/character.md`) but the matcher accepts BOTH ``## Section`` (level 2)
and ``### Section`` (level 3) headers — the template puts ``The Ghost`` under
``## Backstory`` as level 3, while older character files often use it as
level 2. Both are valid.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WATCHED_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})

# Path fragments that mark a character / people file. The hook ignores any
# write whose path does not contain at least one of these.
WATCHED_PATH_FRAGMENTS = ("/characters/", "/people/")

# Path marker for series-character-trackers. Files under
# ``series/{slug}/characters/`` document evolution across books and follow a
# different schema (Snapshot / Evolution per Band / Beziehungen / Updates Log)
# with roles like ``love-interest`` that the book-level validator does not
# recognize. They must be skipped to avoid false-positive warnings (Issue #192).
SERIES_PATH_MARKER = "/series/"

# Frontmatter — block on missing.
REQUIRED_FRONTMATTER = ("name", "role", "status")

# Valid roles (fiction). Memoir person files use a different schema and are
# skipped for the role check (see _is_memoir_person_file).
VALID_ROLES = frozenset(
    {"protagonist", "antagonist", "deuteragonist", "supporting", "minor"}
)

# Recommended sections — warn on missing (only for non-minor characters).
# Each entry is a tuple of acceptable section titles (any one matches).
# Aligns with the post-PR #41 character template plus tolerance for legacy
# files that use level-2 placement of currently-level-3 sections.
RECOMMENDED_SECTIONS: tuple[tuple[str, ...], ...] = (
    ("Want vs. Need",),
    ("Fatal Flaw",),
    ("The Ghost", "Backstory / The Wound", "Backstory"),  # level 2 or 3
    ("Motivation Chain", "GMC", "GMC (Goal / Motivation / Conflict)"),
)

# Memoir-specific frontmatter — when present, role validation is skipped
# (memoir files use person_category / consent_status instead).
MEMOIR_FIELD_MARKERS = ("person_category", "consent_status", "real_name")


# ---------------------------------------------------------------------------
# Hook payload + path resolution (mirrors validate_chapter.py)
# ---------------------------------------------------------------------------


def _read_payload() -> dict[str, Any] | None:
    if sys.stdin.isatty():
        return None
    raw = sys.stdin.read().strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _extract_file_path(payload: dict[str, Any]) -> str | None:
    """Find the file path in the hook payload — schema differs across tools."""
    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input, dict):
        fp = tool_input.get("file_path")
        if isinstance(fp, str) and fp:
            return fp
    tool_response = payload.get("tool_response") or {}
    if isinstance(tool_response, dict):
        for key in ("filePath", "file_path"):
            fp = tool_response.get(key)
            if isinstance(fp, str) and fp:
                return fp
    return None


def _is_character_or_people_file(path: Path) -> bool:
    """True for `characters/*.md` or `people/*.md` (excluding INDEX.md and
    series-character-trackers under ``series/{slug}/characters/``)."""
    if path.suffix != ".md":
        return False
    if path.name == "INDEX.md":
        return False
    if SERIES_PATH_MARKER in str(path):
        return False
    return any(frag in str(path) for frag in WATCHED_PATH_FRAGMENTS)


def _is_memoir_person_file(meta: dict[str, Any]) -> bool:
    """Memoir person files carry consent-related frontmatter; skip role validation."""
    return any(field in meta for field in MEMOIR_FIELD_MARKERS)


# ---------------------------------------------------------------------------
# Section matching — accepts level 2 OR level 3
# ---------------------------------------------------------------------------


def _section_present(text: str, alternatives: tuple[str, ...]) -> bool:
    """Check whether any of the section title alternatives appears as a
    level-2 (``##``) or level-3 (``###``) header in the file body."""
    for title in alternatives:
        # Match `## Title` or `### Title` at the start of a line, allowing
        # trailing whitespace / closing hashes / inline markup.
        pattern = re.compile(
            rf"^#{{2,3}}\s+{re.escape(title)}\b", re.MULTILINE | re.IGNORECASE
        )
        if pattern.search(text):
            return True
    return False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_character(file_path: str) -> tuple[list[str], list[str]]:
    """Return ``(blocking_issues, warning_issues)``."""
    path = Path(file_path)
    blocking: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return blocking, warnings
    if not _is_character_or_people_file(path):
        return blocking, warnings

    text = path.read_text(encoding="utf-8")

    # ---- frontmatter (BLOCK on structural issues) -------------------------
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not fm_match:
        blocking.append(f"{path.name} — Missing YAML frontmatter")
        return blocking, warnings

    try:
        meta = yaml.safe_load(fm_match.group(1)) or {}
    except yaml.YAMLError as exc:
        blocking.append(f"{path.name} — Invalid YAML frontmatter: {exc}")
        return blocking, warnings

    if not isinstance(meta, dict):
        blocking.append(f"{path.name} — Frontmatter is not a YAML mapping")
        return blocking, warnings

    for field in REQUIRED_FRONTMATTER:
        if field not in meta:
            blocking.append(f"{path.name} — Missing frontmatter field: '{field}'")

    # ---- role check (WARN, fiction only) ----------------------------------
    if not _is_memoir_person_file(meta):
        role = str(meta.get("role", "")).lower()
        if role and role not in VALID_ROLES:
            warnings.append(
                f"{path.name} — Unknown role '{role}'. "
                f"Valid: {', '.join(sorted(VALID_ROLES))}"
            )

    # ---- recommended sections (WARN, non-minor fiction characters only) ---
    role = str(meta.get("role", "")).lower()
    if role != "minor" and not _is_memoir_person_file(meta):
        for alternatives in RECOMMENDED_SECTIONS:
            if not _section_present(text, alternatives):
                primary = alternatives[0]
                if len(alternatives) > 1:
                    msg = (
                        f"{path.name} — Missing recommended section "
                        f"'## {primary}' (or one of: "
                        f"{', '.join(alternatives[1:])})"
                    )
                else:
                    msg = f"{path.name} — Missing recommended section '## {primary}'"
                warnings.append(msg)

    return blocking, warnings


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Hook entry point. Returns 0 (continue / warn) or 2 (block).

    The hook differentiates structural problems (frontmatter) from content
    completeness (sections). Structural problems exit 2 so Claude Code
    rejects the write; content warnings exit 0 with diagnostics on stdout.
    """
    payload = _read_payload()

    file_path: str = ""
    if payload is not None:
        tool_name = payload.get("tool_name")
        if isinstance(tool_name, str) and tool_name not in WATCHED_TOOLS:
            return 0
        file_path = _extract_file_path(payload) or ""
    else:
        # Legacy fallback: positional argv (tests, manual invocation).
        if len(sys.argv) > 1:
            file_path = sys.argv[1]

    if not file_path:
        return 0

    blocking, warnings = validate_character(file_path)

    if blocking:
        print(
            "StoryForge linter blocked this character-file write:",
            file=sys.stderr,
        )
        for msg in blocking:
            print(f"  [BLOCK] {msg}", file=sys.stderr)
        if warnings:
            print(
                f"Plus {len(warnings)} non-blocking warning(s):", file=sys.stderr
            )
            for msg in warnings:
                print(f"  [WARN] {msg}", file=sys.stderr)
        print(
            "Fix the blocking frontmatter issues and try again.",
            file=sys.stderr,
        )
        return 2

    for msg in warnings:
        print(f"[WARN] {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
