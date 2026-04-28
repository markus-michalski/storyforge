"""Book-state readers for the manuscript checker.

Each function reads a single piece of state from disk:

- ``_read_book_genres`` — frontmatter genres list (inline or block).
- ``_read_book_category`` — frontmatter book_category, defaults to fiction.
- ``_read_people_profiles`` — memoir people/ files.
- ``_read_allowed_repetitions`` — book CLAUDE.md ## Allowed Repetitions.
- ``_read_snapshot_threshold`` — book CLAUDE.md ## Linter Config snapshot_threshold.

All readers tolerate missing files / sections by returning a safe default.
"""

from __future__ import annotations

import re
from pathlib import Path

from tools.analysis.manuscript.text_utils import _tokenise
from tools.analysis.manuscript.vocabularies import SNAPSHOT_THRESHOLD_DEFAULT

# ---------------------------------------------------------------------------
# Book frontmatter (genres + category)
# ---------------------------------------------------------------------------

_FRONTMATTER_BLOCK_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_GENRES_INLINE_RE = re.compile(r"^\s*genres:\s*\[([^\]]*)\]", re.MULTILINE)
_GENRES_KEY_RE = re.compile(r"^\s*genres:\s*$", re.MULTILINE)
_GENRES_ITEM_RE = re.compile(r"^[ \t]+-[ \t]+['\"]?([^'\"#\n]+?)['\"]?\s*$")

_BOOK_CATEGORY_RE = re.compile(
    r"^\s*book_category:\s*['\"]?(\w+)['\"]?\s*$", re.MULTILINE
)


def _read_book_genres(book_path: Path) -> list[str]:
    """Parse the genres list from book README.md YAML frontmatter.

    Handles both inline ( genres: ["a", "b"] ) and block ( genres:\\n  - a )
    formats without requiring a yaml library.
    """
    readme = book_path / "README.md"
    if not readme.is_file():
        return []

    text = readme.read_text(encoding="utf-8")
    fm_match = _FRONTMATTER_BLOCK_RE.match(text)
    if not fm_match:
        return []
    frontmatter = fm_match.group(1)

    inline = _GENRES_INLINE_RE.search(frontmatter)
    if inline:
        raw = inline.group(1)
        return [
            g.strip().strip("\"'")
            for g in raw.split(",")
            if g.strip().strip("\"'")
        ]

    if _GENRES_KEY_RE.search(frontmatter):
        genres: list[str] = []
        in_genres = False
        for line in frontmatter.splitlines():
            if re.match(r"^\s*genres:\s*$", line):
                in_genres = True
                continue
            if in_genres:
                m = _GENRES_ITEM_RE.match(line)
                if m:
                    genres.append(m.group(1).strip())
                elif line.strip() and not line.startswith(" ") and not line.startswith("\t"):
                    break
        return genres

    return []


def _read_book_category(book_path: Path) -> str:
    """Parse book_category from book README.md frontmatter. Defaults to 'fiction'."""
    readme = book_path / "README.md"
    if not readme.is_file():
        return "fiction"
    text = readme.read_text(encoding="utf-8")
    fm_match = _FRONTMATTER_BLOCK_RE.match(text)
    if not fm_match:
        return "fiction"
    m = _BOOK_CATEGORY_RE.search(fm_match.group(1))
    return m.group(1).strip() if m else "fiction"


# ---------------------------------------------------------------------------
# People profiles (memoir)
# ---------------------------------------------------------------------------

_PERSON_NAME_RE = re.compile(
    r"^\s*name:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", re.MULTILINE
)
_PERSON_ANONYMIZATION_RE = re.compile(
    r"^\s*anonymization:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", re.MULTILINE
)
_PERSON_REAL_NAME_RE = re.compile(
    r"^\s*real_name:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", re.MULTILINE
)


def _read_people_profiles(book_path: Path) -> list[dict[str, str]]:
    """Read person profiles from book's people/ directory.

    Returns a list of dicts with keys: slug, name, anonymization, real_name.
    """
    people_dir = book_path / "people"
    if not people_dir.is_dir():
        return []

    people: list[dict[str, str]] = []
    for person_file in sorted(people_dir.glob("*.md")):
        if person_file.name == "INDEX.md":
            continue
        try:
            text = person_file.read_text(encoding="utf-8")
        except OSError:
            continue
        fm_match = _FRONTMATTER_BLOCK_RE.match(text)
        if not fm_match:
            continue
        fm = fm_match.group(1)
        name_m = _PERSON_NAME_RE.search(fm)
        anon_m = _PERSON_ANONYMIZATION_RE.search(fm)
        real_m = _PERSON_REAL_NAME_RE.search(fm)
        people.append({
            "slug": person_file.stem,
            "name": name_m.group(1).strip() if name_m else person_file.stem,
            "anonymization": anon_m.group(1).strip() if anon_m else "none",
            "real_name": real_m.group(1).strip() if real_m else "",
        })
    return people


# ---------------------------------------------------------------------------
# Per-book linter knobs (CLAUDE.md)
# ---------------------------------------------------------------------------

_ALLOWED_REPS_RE = re.compile(r"^##\s+Allowed Repetitions\s*$", re.IGNORECASE)
_SNAPSHOT_THRESHOLD_RE = re.compile(
    r"^\s*-\s+snapshot_threshold:\s*(\d+)", re.MULTILINE
)
_LINTER_CONFIG_RE = re.compile(r"^##\s+Linter Config\s*$", re.MULTILINE)


def _read_allowed_repetitions(book_path: Path) -> frozenset[str]:
    """Parse ## Allowed Repetitions from book CLAUDE.md.

    Returns a frozenset of lowercased, tokenised phrases that should be
    excluded from the sentence-level repetition scan.
    """
    claudemd = book_path / "CLAUDE.md"
    if not claudemd.is_file():
        return frozenset()

    allowed: set[str] = set()
    in_section = False
    for line in claudemd.read_text(encoding="utf-8").splitlines():
        if _ALLOWED_REPS_RE.match(line):
            in_section = True
            continue
        if in_section:
            if line.startswith("#"):
                break
            stripped = line.strip().lstrip("- ").strip()
            if stripped:
                normalized = " ".join(_tokenise(stripped))
                if normalized:
                    allowed.add(normalized)
    return frozenset(allowed)


def _read_snapshot_threshold(book_path: Path) -> int:
    """Read per-book snapshot threshold from ## Linter Config in CLAUDE.md."""
    claudemd = book_path / "CLAUDE.md"
    if not claudemd.is_file():
        return SNAPSHOT_THRESHOLD_DEFAULT
    text = claudemd.read_text(encoding="utf-8")
    lc = _LINTER_CONFIG_RE.search(text)
    if not lc:
        return SNAPSHOT_THRESHOLD_DEFAULT
    section = text[lc.start():]
    next_heading = re.search(r"^##\s", section[3:], re.MULTILINE)
    if next_heading:
        section = section[: next_heading.start() + 3]
    m = _SNAPSHOT_THRESHOLD_RE.search(section)
    if m:
        return max(2, int(m.group(1)))
    return SNAPSHOT_THRESHOLD_DEFAULT


__all__ = [
    "_read_allowed_repetitions",
    "_read_book_category",
    "_read_book_genres",
    "_read_people_profiles",
    "_read_snapshot_threshold",
]
