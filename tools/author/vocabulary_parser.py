"""Parse vocabulary.md files to extract banned-word entries for DB migration.

Issue #293 — vocabulary.md Cluster C consolidation.

Only the '## Banned Words' sections are extracted. The reference tables
(Preferred Vocabulary, Character Voice Templates, Sentence Patterns) stay
in vocabulary.md as read-only reference material.
"""

from __future__ import annotations

import re

_DATE_ANNOTATION_RE = re.compile(
    r"\s*_\((?:added|emerged)[^)]*\)_",
    re.IGNORECASE,
)


_TRAILING_PERIOD_RE = re.compile(r"\s*\.\s*$")


def _clean_bullet(raw: str) -> str:
    """Return a cleaned entry text, stripping date annotations."""
    text = _DATE_ANNOTATION_RE.sub("", raw).strip()
    # Drop a trailing period left after stripping an annotation, but preserve
    # ellipses (rstrip would destroy them — it treats the arg as a char set).
    text = _TRAILING_PERIOD_RE.sub("", text).strip()
    return text


def parse_vocabulary_banned_words(text: str) -> list[str]:
    """Extract banned-word entries from all '## Banned Words' sections.

    Returns a list of cleaned entry strings ready for DB insertion as
    discovery_type='donts'. Skips table rows, section headers, and blank
    lines. Preserves existing bold formatting; bare phrases are kept as-is.

    Sections outside '## Banned Words' (Preferred Vocabulary, Sentence
    Patterns, Character Voice Templates) are intentionally ignored.
    """
    entries: list[str] = []
    in_banned_section = False

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith("## "):
            in_banned_section = "Banned Words" in stripped
            continue

        if not in_banned_section:
            continue

        # Skip sub-headers, table rows, and blank lines
        if stripped.startswith("#") or stripped.startswith("|") or not stripped:
            continue

        if stripped.startswith("- "):
            raw = stripped[2:].strip()
            if not raw:
                continue
            cleaned = _clean_bullet(raw)
            if cleaned:
                entries.append(cleaned)

    return entries
