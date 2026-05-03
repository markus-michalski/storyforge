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


def _author_vocab_path(author_slug: str, storyforge_home: Path | None = None) -> Path:
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
        body_end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
        # Stop early if we hit a higher-level (## or # only) heading.
        higher_heading = re.search(r"^##\s+\S", text[body_start:body_end], re.MULTILINE)
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
# Author Writing Discoveries (block-severity) — Issue #151 follow-up
# ---------------------------------------------------------------------------
#
# Discoveries promoted via /storyforge:harvest-author-rules land under
# `## Writing Discoveries / ### Recurring Tics` in the author profile. The
# bullets are bold-titled (` - **Title** — rationale`); the scannable phrase
# is typically wrapped in double-quotes inside the bold title (e.g.
# `**Vague-noun "thing" als Fallback**`). Without this loader, those tics
# were invisible to the chapter-writing brief and the manuscript-checker
# (#151 follow-up).

_DISCOVERIES_SECTION_RE = re.compile(
    r"^##\s+Writing\s+Discoveries\s*$(?P<body>.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
_RECURRING_TICS_HEADER_RE = re.compile(
    r"^###\s+Recurring\s+Tics\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_BOLD_TITLE_BULLET_RE = re.compile(r"^-\s+(\*\*[^*]+\*\*)", re.MULTILINE)
_DOUBLE_QUOTE_RE = re.compile(r'[“„”"]([^“„”"]{2,})[”"]')


def _extract_phrases_from_bold_title(title: str) -> list[str]:
    """Extract scannable phrases from a Writing-Discoveries bullet's bold title.

    The bold title may carry one or more double-quoted phrases that are the
    actual scannable patterns; if no quotes are present, the whole title text
    (sans asterisks and whitespace) is the pattern.

    Both ASCII (``"x"``) and German typographic (``„x"``) double-quote pairs
    are recognized. Single-character quoted phrases are skipped (noise);
    in that case the function falls back to the bold-title text.

    Returns a deduplicated, order-preserving list. Empty/missing bold titles
    return ``[]``.
    """
    if not title:
        return []
    cleaned = title.strip()
    bold_match = re.match(r"\*\*(?P<inner>.+)\*\*\s*$", cleaned)
    if not bold_match:
        return []
    inner = bold_match.group("inner").strip()
    if not inner:
        return []

    quoted = [m.group(1).strip() for m in _DOUBLE_QUOTE_RE.finditer(inner)]
    quoted = [q for q in quoted if len(q) >= 2]
    if quoted:
        # Dedup while preserving order.
        seen: set[str] = set()
        out: list[str] = []
        for q in quoted:
            key = q.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(q)
        return out
    return [inner] if len(inner) >= 2 else []


def _author_profile_path(author_slug: str, storyforge_home: Path | None = None) -> Path:
    home = storyforge_home or (Path.home() / ".storyforge")
    return home / "authors" / author_slug / "profile.md"


def load_author_writing_discoveries(
    author_slug: str,
    *,
    storyforge_home: Path | None = None,
) -> list[BannedPattern]:
    """Load scannable phrases from ``profile.md`` ``## Writing Discoveries``.

    Walks the ``### Recurring Tics`` sub-section only. ``### Style Principles``
    and ``### Don'ts`` are prose-level rules, not phrase bans, so they're
    out of scope for this loader.

    Severity is always ``block`` — discoveries are user-asserted author voice
    intent and were explicitly promoted via the harvest skill.

    Returns ``[]`` when the profile is missing, has no Writing Discoveries
    section, or the Recurring Tics sub-section is empty.
    """
    profile_path = _author_profile_path(author_slug, storyforge_home)
    if not profile_path.is_file():
        return []
    try:
        text = profile_path.read_text(encoding="utf-8")
    except OSError:
        return []

    section_match = _DISCOVERIES_SECTION_RE.search(text)
    if not section_match:
        return []
    body = section_match.group("body")

    tics_match = _RECURRING_TICS_HEADER_RE.search(body)
    if not tics_match:
        return []
    tics_body = body[tics_match.end():]
    next_subsection = re.search(r"^###\s+\S", tics_body, re.MULTILINE)
    if next_subsection:
        tics_body = tics_body[: next_subsection.start()]

    patterns: list[BannedPattern] = []
    seen: set[str] = set()

    for bullet_match in _BOLD_TITLE_BULLET_RE.finditer(tics_body):
        bold_title = bullet_match.group(1)
        for phrase in _extract_phrases_from_bold_title(bold_title):
            cleaned = _strip_parenthetical(phrase).strip()
            if len(cleaned) < 2:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            pattern = _build_discovery_pattern(cleaned)
            patterns.append(
                BannedPattern(
                    label=cleaned,
                    pattern=pattern,
                    severity=SEVERITY_BLOCK,
                    source="author profile (## Writing Discoveries / Recurring Tics)",
                    reason="recurring tic promoted from a finished book",
                )
            )
    return patterns


def _build_discovery_pattern(text: str) -> re.Pattern[str]:
    """Compile a tolerant pattern for Writing-Discoveries phrases.

    Single-word phrases reuse :func:`_build_inflection_pattern` (so that
    promoted single tics like ``thing`` still match ``things`` etc.).
    Multi-word or punctuation-containing phrases use ``(?<!\\w)PHRASE(?!\\w)``
    look-arounds — these match correctly even when the phrase ends with a
    period (``\\b...\\b`` fails there because ``.`` is non-word and EOL/space
    is also non-word, so no word-boundary fires).
    """
    is_simple_single_word = " " not in text and "-" not in text and not any(
        c in text for c in ".,!?;:'\""
    )
    if is_simple_single_word:
        return _build_inflection_pattern(text)
    escaped = re.escape(text)
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


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
    section_text = text[section_match.end() :]
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
