"""Parse user messages for CLAUDE.md-relevant prefixes.

Deterministic extraction — no LLM calls. Recognized prefixes:

- ``Regel:`` — a new book-scoped rule
- ``Workflow:`` — a new workflow instruction
- ``Callback:`` — a character, object, or plot thread to recur later

Lines without one of these prefixes are ignored.
"""

from __future__ import annotations

import re
from typing import Literal

EntryKind = Literal["rule", "workflow", "callback"]

PREFIX_MAP: dict[str, EntryKind] = {
    "regel": "rule",
    "rule": "rule",
    "workflow": "workflow",
    "callback": "callback",
}

SECTION_MARKERS: dict[EntryKind, tuple[str, str]] = {
    "rule": ("<!-- RULES:START -->", "<!-- RULES:END -->"),
    "workflow": ("<!-- WORKFLOW:START -->", "<!-- WORKFLOW:END -->"),
    "callback": ("<!-- CALLBACKS:START -->", "<!-- CALLBACKS:END -->"),
}

_PREFIX_RE = re.compile(
    r"^\s*(?P<prefix>regel|rule|workflow|callback)\s*:\s*(?P<body>.+?)\s*$",
    re.IGNORECASE,
)


def parse_prefixed_entry(line: str) -> tuple[EntryKind, str] | None:
    """Parse a single line for a prefix entry.

    Returns ``(kind, text)`` tuple or ``None`` if the line has no recognized
    prefix. The prefix itself is stripped from the returned text.
    """
    match = _PREFIX_RE.match(line)
    if not match:
        return None
    kind = PREFIX_MAP[match.group("prefix").lower()]
    body = match.group("body").strip()
    if not body:
        return None
    return kind, body


def extract_prefixed_lines(text: str) -> list[tuple[EntryKind, str]]:
    """Extract all prefixed entries from a multi-line text block.

    Scans each line independently. Multi-line entries are not supported;
    users must put the entire entry on one line after the prefix.
    """
    results: list[tuple[EntryKind, str]] = []
    for raw_line in text.splitlines():
        entry = parse_prefixed_entry(raw_line)
        if entry is not None:
            results.append(entry)
    return results
