"""Unified loader for banned-phrase patterns.

The PostToolUse hook (#70) needs to enforce three independent banlists:

1. **Book-scoped** rules from the active book's ``CLAUDE.md`` (#70).
2. **Author-scoped** banned-vocabulary from
   ``~/.storyforge/authors/{slug}/vocabulary.md``. Surfaces an explicit
   "this author never uses these words" list maintained per voice.
3. **Globally curated** AI-tells from
   ``reference/craft/anti-ai-patterns.md``. Default warn-severity so
   merging this on top of an existing book does not break drafts.

Each loader returns ``BannedPattern`` records with severity, source, and
human-readable reason so the hook can produce attributed block messages.

The module is dependency-free (stdlib only) so the hook can call it
inline without additional setup.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

SEVERITY_BLOCK = "block"
SEVERITY_WARN = "warn"


@dataclass(frozen=True)
class BannedPattern:
    """A single banned phrase or regex that the hook can scan against."""

    label: str  # human-readable display label
    pattern: re.Pattern[str]  # compiled regex
    severity: str  # SEVERITY_BLOCK | SEVERITY_WARN
    source: str  # provenance shown in block message
    reason: str = ""  # short explanation (truncated for display)
    chapter_limit: int = 0  # 0 = block on first hit; >0 = scaled limit


# ---------------------------------------------------------------------------
# Author-vocabulary loader
# ---------------------------------------------------------------------------

# Section markers the loader treats as banned-phrase sources. Each is a
# subsection (### heading) inside the ``## Banned Words`` block.
_AUTHOR_BANNED_SECTION_RE = re.compile(
    r"^###\s+(Absolutely\s+Forbidden|Forbidden\s+Hedging\s+Phrases|"
    r"Forbidden\s+Emotional\s+Tells|Forbidden\s+Structural\s+Patterns)\s*$",
    re.MULTILINE | re.IGNORECASE,
)

_BOOK_AUTHOR_LINE_RE = re.compile(
    r"^\s*-\s*\*\*Author:\*\*\s*(?P<name>[^\n(]+?)(?:\s*\(.*\))?\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def _slugify(text: str) -> str:
    """Local copy of ``tools.shared.paths.slugify`` to avoid a hard import
    dependency from the hook (which adds plugin_root to sys.path lazily)."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def author_slug_from_book(book_root: Path) -> str | None:
    """Extract the author slug from a book's ``CLAUDE.md`` Book Facts.

    Looks for a line shaped like ``- **Author:** Ethan Cole (...)`` and
    slugifies the display name. Returns ``None`` if the line is missing
    or unparseable.
    """
    claudemd = book_root / "CLAUDE.md"
    if not claudemd.is_file():
        return None
    try:
        text = claudemd.read_text(encoding="utf-8")
    except OSError:
        return None
    match = _BOOK_AUTHOR_LINE_RE.search(text)
    if not match:
        return None
    name = match.group("name").strip()
    if not name:
        return None
    return _slugify(name)


def _strip_parenthetical(text: str) -> str:
    """Remove trailing parenthetical clarifications like '(metaphorical)'."""
    return re.sub(r"\s*\([^)]+\)\s*", " ", text).strip()


def _author_vocab_path(
    author_slug: str, storyforge_home: Path | None = None
) -> Path:
    home = storyforge_home or (Path.home() / ".storyforge")
    return home / "authors" / author_slug / "vocabulary.md"


def load_author_vocab(
    author_slug: str,
    *,
    storyforge_home: Path | None = None,
) -> list[BannedPattern]:
    """Load forbidden-word patterns from an author's ``vocabulary.md``.

    Parses the four ``### Forbidden ...`` subsections, splits aliases on
    `` / ``, strips parentheticals, and emits one ``BannedPattern`` per
    unique cleaned phrase. Severity is always ``block`` — author-scoped
    bans express the user's voice intent and are non-negotiable.
    """
    vocab_path = _author_vocab_path(author_slug, storyforge_home)
    if not vocab_path.is_file():
        return []
    try:
        text = vocab_path.read_text(encoding="utf-8")
    except OSError:
        return []

    patterns: list[BannedPattern] = []
    seen: set[str] = set()

    sections = list(_AUTHOR_BANNED_SECTION_RE.finditer(text))
    for index, match in enumerate(sections):
        section_name = re.sub(r"\s+", " ", match.group(1)).strip().title()
        body_start = match.end()
        body_end = (
            sections[index + 1].start()
            if index + 1 < len(sections)
            else len(text)
        )
        # Stop early if we hit a higher-level (## or # only) heading.
        higher_heading = re.search(
            r"^##\s+\S", text[body_start:body_end], re.MULTILINE
        )
        if higher_heading:
            body_end = body_start + higher_heading.start()

        body = text[body_start:body_end]
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped.startswith("- "):
                continue
            entry = stripped[2:].strip()
            if not entry:
                continue
            for raw_alias in entry.split(" / "):
                cleaned = _strip_parenthetical(raw_alias).strip()
                if len(cleaned) < 2:
                    continue
                key = cleaned.lower()
                if key in seen:
                    continue
                seen.add(key)
                pattern = _build_inflection_pattern(cleaned)
                patterns.append(
                    BannedPattern(
                        label=cleaned,
                        pattern=pattern,
                        severity=SEVERITY_BLOCK,
                        source=f"author-vocab ({section_name})",
                        reason="banned for this author voice",
                    )
                )
    return patterns


def _build_inflection_pattern(text: str) -> re.Pattern[str]:
    """Compile a regex that matches the phrase plus common inflections.

    Strategy:

    - Multi-word and hyphenated phrases get an exact ``\\b...\\b`` match.
      They are usually idiomatic; matching inflections has too many edge
      cases to be worth the complexity.
    - Single words ending in a silent ``e`` (``delve``, ``embrace``) drop
      the ``e`` from the stem so suffixes like ``-ed``, ``-ing``, ``-es``
      land on the verbal root and still match (``delved``, ``delving``,
      ``embraced``).
    - Other single words use ``\\b{word}\\w*`` to catch the bare form
      and any added suffix (``embark`` → ``embarked``, ``embarking``).

    A leading ``\\b`` keeps ``redelve`` from matching ``delve``.
    """
    is_single_word = " " not in text and "-" not in text
    if not is_single_word:
        return re.compile(rf"\b{re.escape(text)}\b", re.IGNORECASE)

    stem = text[:-1] if len(text) > 3 and text.endswith("e") else text
    return re.compile(rf"\b{re.escape(stem)}\w*", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Global anti-AI tells (warn-severity)
# ---------------------------------------------------------------------------

_ANTI_AI_SECTION_RE = re.compile(
    r"^###\s+Heavily\s+Flagged\s+Words\s+and\s+Phrases.*$",
    re.MULTILINE | re.IGNORECASE,
)
_NUMBERED_ENTRY_RE = re.compile(r"^\d+\.\s+(?P<line>.+)$", re.MULTILINE)
_BOLD_TERM_RE = re.compile(r"\*\*([^*]+)\*\*")
_DASH_SPLIT_RE = re.compile(r"\s+[—-]\s+")


def load_global_ai_tells(plugin_root: Path) -> list[BannedPattern]:
    """Parse the AI-tell vocabulary from ``reference/craft/anti-ai-patterns.md``.

    Reads the ``### Heavily Flagged Words and Phrases`` section, extracts
    each numbered entry's bolded terms (split on `` / ``), and emits one
    ``BannedPattern`` per unique phrase. Severity is ``warn`` — global
    advisory rather than user-asserted. Promotion to ``block`` is the
    job of the per-author or per-book banlist.
    """
    path = plugin_root / "reference" / "craft" / "anti-ai-patterns.md"
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    section_match = _ANTI_AI_SECTION_RE.search(text)
    if not section_match:
        return []
    section_text = text[section_match.end():]
    next_section = re.search(r"^##+\s+\S", section_text, re.MULTILINE)
    if next_section:
        section_text = section_text[: next_section.start()]

    patterns: list[BannedPattern] = []
    seen: set[str] = set()

    for entry in _NUMBERED_ENTRY_RE.finditer(section_text):
        line = entry.group("line")
        parts = _DASH_SPLIT_RE.split(line, maxsplit=1)
        bold_zone = parts[0]
        explanation = parts[1].strip() if len(parts) > 1 else ""

        bold_terms = [m.group(1) for m in _BOLD_TERM_RE.finditer(bold_zone)]
        for raw in bold_terms:
            cleaned = _strip_parenthetical(raw).strip()
            if len(cleaned) < 2:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            pattern = _build_inflection_pattern(cleaned)
            short_reason = explanation[:120] if explanation else "AI-tell vocabulary"
            patterns.append(
                BannedPattern(
                    label=cleaned,
                    pattern=pattern,
                    severity=SEVERITY_WARN,
                    source="global anti-ai",
                    reason=short_reason,
                )
            )
    return patterns
