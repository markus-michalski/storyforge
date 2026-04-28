"""Loader for recent-chapter signals: endings + simile counts (Issue #121).

Both signals are per-chapter heuristics over ``draft.md``. They live in
the same module because they share input (the previous chapter's draft)
and the same frontmatter-stripping step.
"""

from __future__ import annotations

import re
from pathlib import Path

from tools.state.parsers import parse_frontmatter

# Same heuristic as manuscript-checker — keep regex local so we never
# import private helpers from the checker.
_SIMILE_RE = re.compile(
    r"\b(?:like\s+a|like\s+the|as\s+if|as\s+though|"
    r"as\s+\w+\s+as)\b",
    re.IGNORECASE,
)


def count_similes(draft_path: Path) -> int:
    """Count simile markers in a chapter draft. Returns 0 on any I/O error."""
    if not draft_path.is_file():
        return 0
    try:
        text = draft_path.read_text(encoding="utf-8")
    except OSError:
        return 0
    _, body = parse_frontmatter(text)
    return len(_SIMILE_RE.findall(body))


def last_paragraph(draft_path: Path, *, max_length: int = 600) -> str:
    """Return the last paragraph of a chapter draft, truncated to ``max_length``.

    Returns ``""`` when the file is missing, unreadable, or contains no
    non-empty paragraph after frontmatter stripping.
    """
    if not draft_path.is_file():
        return ""
    try:
        text = draft_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    _, body = parse_frontmatter(text)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not paragraphs:
        return ""
    last = paragraphs[-1]
    if len(last) > max_length:
        last = last[:max_length].rstrip() + " ..."
    return last


def collect_recent_chapters(
    chapters_dir: Path, current_slug: str, *, n: int = 3,
) -> list[Path]:
    """Return up to ``n`` chapter directories strictly before ``current_slug``.

    When ``current_slug`` is not yet on disk (new chapter), returns the
    last ``n`` chapters that *are* on disk. Sorted by chapter number
    ascending.
    """
    if not chapters_dir.is_dir():
        return []
    all_chapters: list[tuple[int, Path]] = []
    current_number: int | None = None
    for entry in chapters_dir.iterdir():
        if not entry.is_dir():
            continue
        m = re.match(r"^(\d{1,3})-", entry.name)
        if not m:
            continue
        num = int(m.group(1))
        all_chapters.append((num, entry))
        if entry.name == current_slug:
            current_number = num
    all_chapters.sort()
    if current_number is not None:
        return [ch for num, ch in all_chapters if num < current_number][-n:]
    return [ch for _, ch in all_chapters][-n:]


__all__ = ["collect_recent_chapters", "count_similes", "last_paragraph"]
