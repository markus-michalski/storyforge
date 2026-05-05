"""POV character body-state extractor for the chapter-writing brief (Issue #160).

Deterministic extraction of the POV character's physical state at the start of
a chapter across four independent categories:

- ``clothing``            — what the character is wearing / carrying on their body
- ``injuries``            — wounds, pain, mobility limitations
- ``altered_states``      — fatigue, intoxication, drugs, hunger, shock
- ``environmental_limiters`` — sensory dampeners currently on the character
                               (mask, helmet, ear protection, etc.)

Replaces "model remembers whether the character is wearing boots" with a
structured payload that the Pre-Scene Logic Audit (category 5: sensory
plausibility) can verify mechanically.

Priority per category (first hit wins):

1. Frontmatter field in ``characters/{pov_slug}.md``:
   ``current_clothing``, ``current_injuries``, ``altered_states``,
   ``environmental_limiters``.
2. Timeline regex on chapter README timeline sections — each category has its
   own keyword set.
3. Draft heuristic — best-effort regex over the last review-or-later draft.
4. ``"none"`` with a warning when the chapter outline references the missing
   category.

Each category extracts independently — partial coverage (e.g. clothing from
frontmatter, injuries from timeline) is fine.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.shared.paths import slugify
from tools.state.parsers import _chapter_rank, parse_chapter_readme, parse_frontmatter


# ---------------------------------------------------------------------------
# Per-category timeline-beat regexes
# Capture the descriptive phrase after the keyword up to period / newline.
# ---------------------------------------------------------------------------

_TIMELINE_RES: dict[str, re.Pattern[str]] = {
    "clothing": re.compile(
        r"(?:clothing|wearing|dressed\s+in|geared\s+up)\s*:\s*(?P<items>[^.\n]+)",
        re.IGNORECASE,
    ),
    "injuries": re.compile(
        r"(?:injury|wound|injured|hurt)\s*:\s*(?P<items>[^.\n]+)",
        re.IGNORECASE,
    ),
    "altered_states": re.compile(
        r"(?:state|condition|fatigue|intoxicated)\s*:\s*(?P<items>[^.\n]+)",
        re.IGNORECASE,
    ),
    "environmental_limiters": re.compile(
        r"(?:limiter|sense\s+limited|masked|helmeted)\s*:\s*(?P<items>[^.\n]+)",
        re.IGNORECASE,
    ),
}

# Per-category draft heuristics — surfaces sentences that imply a state.
_DRAFT_RES: dict[str, re.Pattern[str]] = {
    "clothing": re.compile(
        r"(?:wore|wearing|had\s+on|dressed\s+in)\s+(?P<phrase>[^.]{4,60})",
        re.IGNORECASE,
    ),
    "injuries": re.compile(
        r"(?:injured|hurt\s+(?:his|her|their)|limped|staggered|bleeding|bandaged)\s*(?P<phrase>[^.]{0,50})",
        re.IGNORECASE,
    ),
    "altered_states": re.compile(
        r"(?:exhausted|fatigued|drunk|drugged|hungr(?:y|ier)|in\s+shock|running\s+on\s+[0-9])\s*(?P<phrase>[^.]{0,50})",
        re.IGNORECASE,
    ),
    "environmental_limiters": re.compile(
        r"(?:mask\s+on|helmet\s+on|blindfold|ear\s+protection|noise-cancell|hearing\s+damp)\s*(?P<phrase>[^.]{0,50})",
        re.IGNORECASE,
    ),
}

# Frontmatter field names per category.
_FRONTMATTER_FIELDS: dict[str, str] = {
    "clothing": "current_clothing",
    "injuries": "current_injuries",
    "altered_states": "altered_states",
    "environmental_limiters": "environmental_limiters",
}

# Keywords in the chapter outline that indicate the category is referenced.
# If the outline mentions these AND the category is "none", a warning is emitted.
_OUTLINE_KEYWORDS: dict[str, list[str]] = {
    "clothing": ["wearing", "clothes", "clothed", "dressed", "gear", "jacket", "boots", "coat", "gloves"],
    "injuries": ["injured", "injury", "wound", "hurt", "limp", "stagger", "bleed", "bandage", "pain"],
    "altered_states": [
        "tired", "exhausted", "fatigue", "drunk", "drugged", "hungr",
        "in shock", "dehydrat", "sleep-depriv", "hours sleep",
    ],
    "environmental_limiters": [
        "mask", "helmet", "blindfold", "ear protection", "hearing damp",
        "sense limit", "noise-cancel",
    ],
}

_CATEGORIES: tuple[str, ...] = ("clothing", "injuries", "altered_states", "environmental_limiters")

# Shared with pov_inventory.
_REVIEW_RANK_THRESHOLD = 2
_PRIOR_CHAPTER_LIMIT = 3
_CHAPTER_DIR_RE = re.compile(r"^(?P<num>\d{1,3})-")
_TIME_ANCHOR_RE = re.compile(r"~?\d{1,2}:\d{2}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_pov_state(
    book_root: Path,
    pov_character: str,
    chapter_slug: str,
    *,
    chars_dir: Path | None = None,
    outline_text: str = "",
) -> dict[str, Any]:
    """Extract the POV character's current physical state.

    Args:
        book_root: Project directory containing ``chapters/`` and ``characters/``.
        pov_character: Display name of the POV character (slugified internally).
        chapter_slug: Chapter being written (used to anchor the chapter scan).
        chars_dir: Optional override for the characters directory (memoir books
            pass their ``people/`` directory here).
        outline_text: Raw text of the chapter README / outline, used for
            outline-aware warnings when a category has no source.

    Returns:
        Dict with the four category lists (each item has ``item`` + ``source``),
        ``as_of`` (most-recent chapter that contributed chapter-based data, or
        ``None`` when all data is from frontmatter or all categories are ``none``),
        ``extraction_methods`` dict per category, and ``warnings`` list.
    """
    if chars_dir is None:
        chars_dir = book_root / "characters"

    pov_slug = slugify(pov_character) if pov_character else ""
    chapters = _chapters_for_scan(book_root, chapter_slug)

    results: dict[str, list[dict[str, str]]] = {}
    methods: dict[str, str] = {}

    for cat in _CATEGORIES:
        items, method = _extract_category(cat, pov_slug, chars_dir, chapters)
        results[cat] = items
        methods[cat] = method

    # as_of: most-recent chapter that contributed chapter-based data
    as_of = _compute_as_of(results, methods, chapters)

    warnings = _build_warnings(methods, outline_text)

    return {
        "clothing": results["clothing"],
        "injuries": results["injuries"],
        "altered_states": results["altered_states"],
        "environmental_limiters": results["environmental_limiters"],
        "as_of": as_of,
        "extraction_methods": methods,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Per-category extraction
# ---------------------------------------------------------------------------


def _extract_category(
    category: str,
    pov_slug: str,
    chars_dir: Path,
    chapters: list[Path],
) -> tuple[list[dict[str, str]], str]:
    """Return (items, extraction_method) for a single category."""
    if pov_slug:
        items = _from_frontmatter(category, chars_dir, pov_slug)
        if items:
            return items, "frontmatter"

    for ch_dir in chapters:
        items = _from_timeline(category, ch_dir)
        if items:
            return items, "timeline_regex"

    for ch_dir in chapters:
        items = _from_draft(category, ch_dir)
        if items:
            return items, "draft_heuristic"

    return [], "none"


def _from_frontmatter(
    category: str,
    chars_dir: Path,
    pov_slug: str,
) -> list[dict[str, str]]:
    field = _FRONTMATTER_FIELDS[category]
    path = chars_dir / f"{pov_slug}.md"
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    meta, _body = parse_frontmatter(text)
    raw = meta.get(field)
    if not isinstance(raw, list) or not raw:
        return []
    source = f"character:{pov_slug}:frontmatter:{field}"
    return [{"item": str(entry).strip(), "source": source} for entry in raw if str(entry).strip()]


def _from_timeline(category: str, chapter_dir: Path) -> list[dict[str, str]]:
    readme = chapter_dir / "README.md"
    if not readme.is_file():
        return []
    try:
        text = readme.read_text(encoding="utf-8")
    except OSError:
        return []
    pattern = _TIMELINE_RES[category]
    matches = list(pattern.finditer(text))
    if not matches:
        return []
    best = matches[-1]
    items_str = best.group("items").strip()
    source = _timeline_source(text, best, chapter_dir.name)
    return [_make_item(piece, source) for piece in _split(items_str)]


def _from_draft(category: str, chapter_dir: Path) -> list[dict[str, str]]:
    draft = chapter_dir / "draft.md"
    if not draft.is_file():
        return []
    try:
        text = draft.read_text(encoding="utf-8")
    except OSError:
        return []
    _meta, body = parse_frontmatter(text)
    pattern = _DRAFT_RES[category]
    source = f"chapter:{chapter_dir.name}:draft"
    items: list[dict[str, str]] = []
    for m in pattern.finditer(body):
        phrase = (m.group("phrase") or "").strip()
        # Use the full match when phrase is empty (injury-type patterns)
        raw = phrase if phrase else m.group(0).strip()
        cleaned = _make_item(raw, source)
        if cleaned["item"]:
            items.append(cleaned)
    return items


# ---------------------------------------------------------------------------
# Chapter scan list (mirrors pov_inventory)
# ---------------------------------------------------------------------------


def _chapters_for_scan(book_root: Path, chapter_slug: str) -> list[Path]:
    """Current chapter + last N review-or-later prior chapters, newest first."""
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
        m = _CHAPTER_DIR_RE.match(entry.name)
        if not m:
            continue
        numbered.append((int(m.group("num")), entry))
    numbered.sort(key=lambda pair: pair[0])

    current_num: int | None = None
    for num, path in numbered:
        if path.name == chapter_slug:
            current_num = num
            break

    priors: list[Path] = []
    for num, path in numbered:
        if current_num is not None and num >= current_num:
            continue
        if _is_review_or_later(path):
            priors.append(path)

    out.extend(reversed(priors[-_PRIOR_CHAPTER_LIMIT:]))
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


def _compute_as_of(
    results: dict[str, list[dict[str, str]]],
    methods: dict[str, str],
    chapters: list[Path],
) -> str | None:
    """Return the slug of the most-recent chapter that contributed data."""
    chapter_based = {"timeline_regex", "draft_heuristic"}
    chapter_slugs: set[str] = set()
    for cat in _CATEGORIES:
        if methods[cat] in chapter_based:
            for item in results[cat]:
                source = item.get("source", "")
                # source format: "chapter:{slug}:timeline:~HH:MM" or "chapter:{slug}:draft"
                parts = source.split(":")
                if len(parts) >= 2 and parts[0] == "chapter":
                    chapter_slugs.add(parts[1])

    if not chapter_slugs:
        return None

    # Return the numerically latest chapter from those that contributed.
    best: tuple[int, str] | None = None
    for ch_dir in chapters:
        if ch_dir.name in chapter_slugs:
            m = _CHAPTER_DIR_RE.match(ch_dir.name)
            num = int(m.group("num")) if m else 0
            if best is None or num > best[0]:
                best = (num, ch_dir.name)

    return best[1] if best else next(iter(chapter_slugs))


def _build_warnings(methods: dict[str, str], outline_text: str) -> list[str]:
    """Emit a warning only when a category is 'none' AND the outline references it."""
    warnings: list[str] = []
    outline_lower = outline_text.lower()
    for cat in _CATEGORIES:
        if methods[cat] != "none":
            continue
        keywords = _OUTLINE_KEYWORDS[cat]
        if any(kw in outline_lower for kw in keywords):
            warnings.append(
                f"{cat}: referenced in chapter outline but no source found"
                " — surface gap to user, do not invent"
            )
    return warnings


def _split(items_str: str) -> list[str]:
    return [p.strip() for p in items_str.split(",") if p.strip()]


def _make_item(raw: str, source: str) -> dict[str, str]:
    cleaned = raw.strip().strip(".").strip()
    return {"item": cleaned, "source": source}


def _timeline_source(text: str, match: re.Match[str], chapter_slug: str) -> str:
    """Build source pointer with time anchor when present on the same line."""
    line_start = text.rfind("\n", 0, match.start()) + 1
    prefix = text[line_start : match.start()]
    anchor = _TIME_ANCHOR_RE.search(prefix)
    if anchor:
        return f"chapter:{chapter_slug}:timeline:{anchor.group(0)}"
    return f"chapter:{chapter_slug}:timeline"


__all__ = ["extract_pov_state"]
