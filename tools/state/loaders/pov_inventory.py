"""POV character inventory extractor for the chapter-writing brief (Issue #157).

Deterministic extraction of the POV character's last established physical
inventory. Replaces the implicit "model remembers what the character was
carrying" behavior that produces invented items under context pressure
with a structured list and a source pointer the chapter-writer can verify.

Priority (first hit wins):

1. ``current_inventory`` field in ``characters/{pov_slug}.md`` frontmatter.
2. Inventory regex (``inventory:``, ``tactical inventory:``, ``gear:``,
   ``loadout:``, ``carrying:``) on the chapter README's timeline section,
   scanning the current chapter first, then the last 3 review-or-later
   prior chapters.
3. Draft heuristic (``carried`` / ``had X in his pocket``) over the same
   chapter set.
4. ``extraction_method: "none"`` with a warning surfacing the gap so the
   caller can ask the user instead of inventing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.shared.paths import slugify
from tools.state.parsers import _chapter_rank, parse_chapter_readme, parse_frontmatter


# Inventory beat — matches lines like:
#   "tactical inventory: compass, silver knife, no-signal phone."
#   "inventory: compass, knife"
#   "Gear: backpack, headlamp"
#   "loadout: ..."
#   "carrying: ..."
# Stops at the first period or newline so it doesn't swallow the rest of
# the paragraph.
INVENTORY_BEAT_RE = re.compile(
    r"(?:tactical\s+)?(?:inventory|gear|loadout|carrying)\s*:\s*"
    r"(?P<items>[^.\n]+)",
    re.IGNORECASE,
)

# Time anchor like ~12:55 or 12:55. Used to enrich the source pointer
# when the inventory beat sits next to a chapter-timeline time stamp.
TIME_ANCHOR_RE = re.compile(r"~?\d{1,2}:\d{2}")

# Best-effort draft heuristic — surfaces sentences that imply carrying.
# Captures the noun-phrase between the verb and either a body-location
# preposition or a sentence terminator.
DRAFT_HEURISTIC_RE = re.compile(
    r"(?:carried|had)\s+(?P<phrase>[^.]+?)"
    r"(?:\s+in\s+(?:his|her|their)\s+(?:pocket|pack|bag|jacket|coat)|\s*\.)",
    re.IGNORECASE,
)

# Same threshold as `chapter_timeline_parser` — review/reviewed/revision
# rank at 2; drafts and outlines are excluded from the prior-scan set.
_REVIEW_RANK_THRESHOLD = 2

# Number of prior review-or-later chapters to scan.
_PRIOR_CHAPTER_LIMIT = 3

# Chapter directory name pattern (e.g. "27-the-meet").
_CHAPTER_DIR_RE = re.compile(r"^(?P<num>\d{1,3})-")


def extract_pov_inventory(
    book_root: Path,
    pov_character: str,
    chapter_slug: str,
    *,
    chars_dir: Path | None = None,
) -> dict[str, Any]:
    """Extract the POV character's last established physical inventory.

    Args:
        book_root: Project directory containing ``chapters/`` and ``characters/``.
        pov_character: Display name of the POV character (slugified internally).
        chapter_slug: Chapter being written.
        chars_dir: Optional override for the characters directory (memoir
            books pass their ``people/`` directory here).

    Returns:
        Dict with the structured inventory schema. ``items`` is always a
        list (possibly empty), ``extraction_method`` is one of
        ``frontmatter`` / ``timeline_regex`` / ``draft_heuristic`` /
        ``none``, ``as_of`` is the chapter slug for chapter-tied sources
        or ``None`` for frontmatter and ``none``, ``warnings`` is a
        non-empty list when the gap should be surfaced to the user.
    """
    if chars_dir is None:
        chars_dir = book_root / "characters"

    pov_slug = slugify(pov_character) if pov_character else ""

    if pov_slug:
        items = _from_frontmatter(chars_dir, pov_slug)
        if items:
            return _wrap(items, "frontmatter", as_of=None)

    chapters = _chapters_for_inventory_scan(book_root, chapter_slug)

    for chapter_dir in chapters:
        items = _from_timeline(chapter_dir)
        if items:
            return _wrap(items, "timeline_regex", as_of=chapter_dir.name)

    for chapter_dir in chapters:
        items = _from_draft_heuristic(chapter_dir)
        if items:
            return _wrap(items, "draft_heuristic", as_of=chapter_dir.name)

    return _wrap(
        [],
        "none",
        as_of=None,
        warnings=[
            "no inventory beat found in last 4 chapters — surface the gap to the user, do not invent items",
        ],
    )


# ---------------------------------------------------------------------------
# Source extractors
# ---------------------------------------------------------------------------


def _from_frontmatter(chars_dir: Path, pov_slug: str) -> list[dict[str, str]]:
    path = chars_dir / f"{pov_slug}.md"
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    meta, _body = parse_frontmatter(text)
    raw = meta.get("current_inventory")
    if not isinstance(raw, list) or not raw:
        return []
    source = f"character:{pov_slug}:frontmatter:current_inventory"
    return [
        {"item": str(item).strip(), "source": source}
        for item in raw
        if str(item).strip()
    ]


def _from_timeline(chapter_dir: Path) -> list[dict[str, str]]:
    readme = chapter_dir / "README.md"
    if not readme.is_file():
        return []
    try:
        text = readme.read_text(encoding="utf-8")
    except OSError:
        return []
    matches = list(INVENTORY_BEAT_RE.finditer(text))
    if not matches:
        return []
    # Most recent beat in the chapter wins (last regex hit).
    best = matches[-1]
    items_str = best.group("items").strip()
    source = _timeline_source(text, best, chapter_dir.name)
    return [_clean_item(piece, source) for piece in _split_items(items_str)]


def _from_draft_heuristic(chapter_dir: Path) -> list[dict[str, str]]:
    draft = chapter_dir / "draft.md"
    if not draft.is_file():
        return []
    try:
        text = draft.read_text(encoding="utf-8")
    except OSError:
        return []
    _meta, body = parse_frontmatter(text)
    matches = DRAFT_HEURISTIC_RE.finditer(body)
    source = f"chapter:{chapter_dir.name}:draft"
    items: list[dict[str, str]] = []
    for match in matches:
        phrase = match.group("phrase").strip()
        for piece in _split_items(phrase):
            cleaned = _clean_item(piece, source)
            if cleaned["item"]:
                items.append(cleaned)
    return items


# ---------------------------------------------------------------------------
# Chapter scan list (current + prior review-or-later)
# ---------------------------------------------------------------------------


def _chapters_for_inventory_scan(
    book_root: Path,
    chapter_slug: str,
) -> list[Path]:
    """Current chapter + last N review-or-later prior chapters, newest first.

    Chapter ordering: the current chapter is scanned first because it
    may already carry a fresh inventory beat from the writer's outline.
    Prior chapters are filtered to review-status-or-later so drafts and
    outlines (which are still mutable) don't pollute the source pointer.
    """
    chapters_dir = book_root / "chapters"
    if not chapters_dir.is_dir():
        return []

    out: list[Path] = []
    current = chapters_dir / chapter_slug
    if current.is_dir():
        out.append(current)

    numbered: list[tuple[int, Path]] = []
    for entry in chapters_dir.iterdir():
        if not entry.is_dir():
            continue
        match = _CHAPTER_DIR_RE.match(entry.name)
        if not match:
            continue
        numbered.append((int(match.group("num")), entry))
    numbered.sort(key=lambda pair: pair[0])

    current_num: int | None = None
    for num, path in numbered:
        if path.name == chapter_slug:
            current_num = num
            break

    review_priors: list[Path] = []
    for num, path in numbered:
        if current_num is not None and num >= current_num:
            continue
        if _is_review_or_later(path):
            review_priors.append(path)

    # Take the most-recent N priors and scan newest first.
    out.extend(reversed(review_priors[-_PRIOR_CHAPTER_LIMIT:]))
    return out


def _is_review_or_later(chapter_dir: Path) -> bool:
    readme = chapter_dir / "README.md"
    if not readme.is_file():
        return False
    try:
        meta = parse_chapter_readme(readme)
    except Exception:  # pylint: disable=broad-except
        return False
    return _chapter_rank(str(meta.get("status", "Outline"))) >= _REVIEW_RANK_THRESHOLD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wrap(
    items: list[dict[str, str]],
    method: str,
    *,
    as_of: str | None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "items": items,
        "as_of": as_of,
        "extraction_method": method,
        "warnings": list(warnings) if warnings else [],
    }


def _split_items(items_str: str) -> list[str]:
    return [piece.strip() for piece in items_str.split(",") if piece.strip()]


def _clean_item(raw: str, source: str) -> dict[str, str]:
    cleaned = raw.strip().strip(".").strip()
    return {"item": cleaned, "source": source}


def _timeline_source(text: str, match: re.Match[str], chapter_slug: str) -> str:
    """Build a source pointer that includes the time anchor when present.

    Looks for a HH:MM-style time on the same line as the inventory beat
    and to the left of the keyword. Falls back to a chapter-only pointer
    when no anchor is on that line.
    """
    line_start = text.rfind("\n", 0, match.start()) + 1
    prefix_in_line = text[line_start : match.start()]
    anchor = TIME_ANCHOR_RE.search(prefix_in_line)
    if anchor:
        return f"chapter:{chapter_slug}:timeline:{anchor.group(0)}"
    return f"chapter:{chapter_slug}:timeline"


__all__ = ["extract_pov_inventory"]
