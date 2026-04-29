"""Callback register validator.

Parses the ``## Callback Register`` section from a book's CLAUDE.md and
cross-references each callback against all drafted chapter files.

Produces three status buckets:
- ``satisfied``          — callback appears in at least one chapter, no overdue deadline
- ``deferred``           — callback never appeared, or appeared then went silent
                           (without a must-not-forget marker)
- ``potentially_dropped`` — overdue expected-return deadline, OR
                            must-not-forget callback silent for >10 chapters
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

_CALLBACKS_SECTION_RE = re.compile(
    r"<!-- CALLBACKS:START -->(.*?)<!-- CALLBACKS:END -->",
    re.DOTALL,
)
_BOLD_NAME_RE = re.compile(r"\*\*([^*]+)\*\*")
_EXPECTED_RETURN_RE = re.compile(r"expected\s+return\s+by\s+Ch\s+(\d+)", re.IGNORECASE)
_MUST_NOT_FORGET_RE = re.compile(r"_\(must not be forgotten\)_", re.IGNORECASE)
_ADDED_DATE_RE = re.compile(r"\s*_\(added \d{4}-\d{2}-\d{2}\)_")

_STOPWORDS = frozenset(
    [
        "the",
        "a",
        "an",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "and",
        "or",
        "but",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "not",
        "no",
        "so",
        "his",
        "her",
        "its",
        "their",
        "our",
        "your",
        "my",
        "by",
        "as",
        "from",
        "that",
        "this",
        "these",
        "those",
        "which",
        "who",
    ]
)

# Chapters silent for longer than this threshold trigger deferred/dropped
_SILENCE_THRESHOLD = 10


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CallbackEntry:
    name: str
    search_terms: list[str]
    expected_return_ch: int | None = None
    must_not_forget: bool = False
    raw_line: str = ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _extract_search_terms(name: str) -> list[str]:
    """Derive search terms from a callback name.

    Returns the full name plus any significant individual words (≥3 chars,
    non-stopword) so both exact-phrase and partial matching work.
    """
    terms: list[str] = []
    name_clean = name.strip()
    if len(name_clean) >= 3:
        terms.append(name_clean)
    words = re.findall(r"[a-zA-Z'À-ɏ]+", name_clean)
    for word in words:
        w = word.lower().strip("'")
        if len(w) >= 3 and w not in _STOPWORDS and word not in terms:
            terms.append(word)
    return terms


def parse_callback_register(claudemd_text: str) -> list[CallbackEntry]:
    """Parse callback entries from a book's CLAUDE.md content.

    Returns an empty list if the ``## Callback Register`` section is absent
    or contains no bullet entries.
    """
    match = _CALLBACKS_SECTION_RE.search(claudemd_text)
    if not match:
        return []

    section = match.group(1)
    entries: list[CallbackEntry] = []

    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line.startswith("- "):
            continue

        line_clean = _ADDED_DATE_RE.sub("", line).strip()

        bold_match = _BOLD_NAME_RE.search(line_clean)
        if bold_match:
            name = bold_match.group(1).strip()
        else:
            # Plain text: strip the leading "- ", then remove annotations
            name_text = line_clean[2:].strip()
            name_text = _EXPECTED_RETURN_RE.sub("", name_text)
            name_text = _MUST_NOT_FORGET_RE.sub("", name_text)
            name_text = re.sub(r"\s*—\s*.*$", "", name_text)
            name = name_text.strip().rstrip(".")

        if not name:
            continue

        expected_ch: int | None = None
        exp_match = _EXPECTED_RETURN_RE.search(line_clean)
        if exp_match:
            expected_ch = int(exp_match.group(1))

        must_forget = bool(_MUST_NOT_FORGET_RE.search(line_clean))

        entries.append(
            CallbackEntry(
                name=name,
                search_terms=_extract_search_terms(name),
                expected_return_ch=expected_ch,
                must_not_forget=must_forget,
                raw_line=raw_line,
            )
        )

    return entries


def _chapter_number_from_path(chapter_dir: Path) -> int | None:
    """Extract chapter number from directory name like ``03-the-dark-night``."""
    m = re.match(r"^(\d+)", chapter_dir.name)
    return int(m.group(1)) if m else None


def _draft_contains_any(draft_path: Path, terms: list[str]) -> bool:
    """Return True if any search term appears (case-insensitive) in the draft."""
    if not draft_path.exists():
        return False
    text = draft_path.read_text(encoding="utf-8", errors="ignore").lower()
    return any(term.lower() in text for term in terms)


def verify_callbacks(book_path: Path, claudemd_text: str) -> dict:
    """Verify the callback register against all drafted chapters.

    Args:
        book_path: Absolute path to the book project directory.
        claudemd_text: Contents of the book's CLAUDE.md.

    Returns:
        dict with keys: book_slug, callbacks_checked, satisfied,
        deferred, potentially_dropped.
    """
    entries = parse_callback_register(claudemd_text)

    # Collect drafted chapters sorted by chapter number
    chapters_dir = book_path / "chapters"
    drafted: list[tuple[int, Path]] = []
    if chapters_dir.exists():
        for ch_dir in sorted(chapters_dir.iterdir()):
            if not ch_dir.is_dir():
                continue
            draft = ch_dir / "draft.md"
            if not draft.exists():
                continue
            ch_num = _chapter_number_from_path(ch_dir)
            if ch_num is not None:
                drafted.append((ch_num, draft))

    drafted.sort(key=lambda x: x[0])
    total_drafted = len(drafted)
    max_chapter = drafted[-1][0] if drafted else 0

    satisfied: list[dict] = []
    deferred: list[dict] = []
    potentially_dropped: list[dict] = []

    for entry in entries:
        appears_in: list[int] = [ch_num for ch_num, draft in drafted if _draft_contains_any(draft, entry.search_terms)]

        last_ch = appears_in[-1] if appears_in else None

        # Chapters of silence = gap between last appearance and current max
        chapters_silent = (max_chapter - last_ch) if last_ch is not None else max_chapter

        base: dict = {
            "name": entry.name,
            "appears_in": appears_in,
            "last_appeared_ch": last_ch,
        }
        if entry.expected_return_ch is not None:
            base["expected_return_ch"] = entry.expected_return_ch

        # Overdue: expected_return_ch has passed and callback never appeared
        # in or after that chapter
        is_overdue = (
            entry.expected_return_ch is not None
            and max_chapter >= entry.expected_return_ch
            and not any(ch >= entry.expected_return_ch for ch in appears_in)
        )

        if is_overdue:
            warning = (
                f"expected return by Ch {entry.expected_return_ch}"
                f" — {'never appeared' if not appears_in else f'last seen Ch {last_ch}, deadline passed'}"
            )
            potentially_dropped.append(
                {
                    **base,
                    "chapters_since": chapters_silent,
                    "warning": warning,
                }
            )
        elif not appears_in:
            # Never appeared at all
            deferred.append(
                {
                    **base,
                    "registered_in_ch": None,
                    "chapters_since": total_drafted,
                    "status": "pending",
                }
            )
        elif chapters_silent > _SILENCE_THRESHOLD and entry.must_not_forget:
            warning = f"register entry says 'must not be forgotten' — {chapters_silent} chapters of silence"
            potentially_dropped.append(
                {
                    **base,
                    "chapters_since": chapters_silent,
                    "warning": warning,
                }
            )
        elif chapters_silent > _SILENCE_THRESHOLD:
            deferred.append(
                {
                    **base,
                    "registered_in_ch": None,
                    "chapters_since": chapters_silent,
                    "status": "long_silence",
                }
            )
        else:
            satisfied.append(base)

    return {
        "book_slug": book_path.name,
        "callbacks_checked": len(entries),
        "satisfied": satisfied,
        "deferred": deferred,
        "potentially_dropped": potentially_dropped,
    }
