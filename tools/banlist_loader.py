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
# Author Writing Discoveries — Issue #151 follow-up
# ---------------------------------------------------------------------------
#
# Discoveries promoted via /storyforge:harvest-author-rules are stored in the
# ``author_discoveries`` table (``recurring_tics`` type, since #281). The
# bullets are bold-titled (` - **Title** — rationale`); the scannable phrase
# is typically wrapped in double-quotes inside the bold title (e.g.
# `**Vague-noun "thing" als Fallback**`). Without this loader, those tics
# were invisible to the chapter-writing brief and the manuscript-checker
# (#151 follow-up).
#
# Severity and chapter_limit extensions:
#
# - Adding ``[warn]`` or ``[advisory]`` anywhere in the bullet text downgrades
#   the finding to SEVERITY_WARN — the hook reports it without blocking.
#   Use for tics that are context-dependent (sometimes acceptable).
# - Adding ``Max N per chapter`` / ``Max N–M per chapter`` / ``Max einmal pro
#   Kapitel`` in the bullet text sets a per-chapter cap. The hook allows up to
#   that many hits before emitting a finding. The same German phrasing already
#   used in existing tic bullets is accepted.

# ``[warn]`` / ``[advisory]`` anywhere in a bullet body → SEVERITY_WARN.
_DISCOVERY_WARN_RE = re.compile(r"\[(?:warn|advisory)\]", re.IGNORECASE)

# ``Max N per chapter``, ``Max N–M pro Kapitel``, ``Max einmal pro Kapitel``.
# Handles the German "Max. N–M pro Kapitel" phrasing (with trailing period on
# "Max") and "einmal"/"once" as a synonym for 1.
_DISCOVERY_LIMIT_RE = re.compile(
    r"\bmax(?:imum)?\.?\s+"
    r"(?:(?P<once>once|einmal)"
    r"|(?:(?P<low>\d+)\s*[-–—]\s*)?(?P<high>\d+))"
    r"\s+(?:per|pro)\s+(?:chapter|kapitel)\b",
    re.IGNORECASE,
)


def _extract_discovery_severity(text: str) -> str:
    """Return SEVERITY_WARN when ``[warn]`` / ``[advisory]`` is present."""
    return SEVERITY_WARN if _DISCOVERY_WARN_RE.search(text) else SEVERITY_BLOCK


def _extract_discovery_limit(text: str) -> int:
    """Parse per-chapter cap from a tic bullet body.

    Returns the integer limit (upper bound for ranges, 1 for once/einmal),
    or 0 when no cap is declared (block on first hit).
    """
    match = _DISCOVERY_LIMIT_RE.search(text)
    if not match:
        return 0
    if match.group("once"):
        return 1
    upper = match.group("high") or match.group("low")
    try:
        return int(upper)
    except ValueError:
        return 0


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

# Recurring-Tic bullet with separately-captured title + body (#212). Body
# spans from the title's closing ``**`` to the next bullet, blank line, or
# end-of-section.
_RECURRING_TIC_BULLET_RE = re.compile(
    r"^-\s+(?P<title>\*\*[^*]+\*\*)\s*(?P<body>.*?)(?=^-\s+|^\s*$|\Z)",
    re.MULTILINE | re.DOTALL,
)

# Backtick-wrapped content inside a bullet body — same shape as the book-rule
# extractor uses. Regex hint characters trigger compile-as-regex; otherwise
# the inner text is escaped and matched literally.
_BACKTICK_CONTENT_RE = re.compile(r"`([^`\n]+)`")
_REGEX_HINT_CHARS = set("|()[]\\^$?+*{}")


def _title_inner_quotes(title: str) -> list[str]:
    """Return only the double-quoted phrases embedded in a bold title.

    Unlike :func:`_extract_phrases_from_bold_title`, this helper does NOT
    fall back to the title text when no quotes are present — it returns
    ``[]``. Callers use the empty result as the signal that body-level
    extraction should kick in (#212).
    """
    if not title:
        return []
    bold_match = re.match(r"\*\*(?P<inner>.+)\*\*\s*$", title.strip())
    if not bold_match:
        return []
    inner = bold_match.group("inner").strip()
    if not inner:
        return []
    quoted = [m.group(1).strip() for m in _DOUBLE_QUOTE_RE.finditer(inner)]
    quoted = [q for q in quoted if len(q) >= 2]
    seen: set[str] = set()
    out: list[str] = []
    for q in quoted:
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out


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
    quoted = _title_inner_quotes(title)
    if quoted:
        return quoted
    cleaned = title.strip()
    bold_match = re.match(r"\*\*(?P<inner>.+)\*\*\s*$", cleaned)
    if not bold_match:
        return []
    inner = bold_match.group("inner").strip()
    return [inner] if len(inner) >= 2 else []


def _extract_patterns_from_tic_body(body: str) -> list[tuple[str, re.Pattern[str] | None]]:
    """Extract scannable patterns from a Recurring-Tic bullet body (#212).

    Walks the body prose AFTER the bold title and returns one entry per
    pattern. Two sources, in order:

    1. **Backtick patterns** — same heuristic as
       :func:`tools.analysis.manuscript.rules._extract_patterns_from_rule`.
       If the content carries regex metacharacters it compiles as a regex;
       otherwise literal substring.
    2. **Double-quoted phrases** of at least 3 characters. Both ASCII
       (``"x"``) and German typographic (``„x"``) quote pairs are accepted.

    Each tuple is ``(label, compiled_pattern_or_None)``:

    - When ``compiled_pattern`` is not ``None``, the caller should use it
      directly (backtick path — preserves regex intent).
    - When it is ``None``, the caller compiles via
      :func:`_build_discovery_pattern` (quoted-phrase path — gets the
      same inflection-aware compilation as title quotes).

    Returns a deduplicated, order-preserving list. Empty body returns ``[]``.
    """
    if not body:
        return []

    out: list[tuple[str, re.Pattern[str] | None]] = []
    seen: set[str] = set()

    for m in _BACKTICK_CONTENT_RE.finditer(body):
        raw = m.group(1)
        inner = raw.strip()
        if len(inner) < 2:
            continue
        key = inner.lower()
        if key in seen:
            continue
        seen.add(key)
        if any(c in _REGEX_HINT_CHARS for c in inner):
            try:
                compiled = re.compile(raw, re.IGNORECASE)
            except re.error:
                continue
            out.append((inner, compiled))
        else:
            out.append((inner, re.compile(re.escape(raw), re.IGNORECASE)))

    for m in _DOUBLE_QUOTE_RE.finditer(body):
        phrase = m.group(1).strip()
        if len(phrase) < 3:
            continue
        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((phrase, None))

    return out


# ---------------------------------------------------------------------------
# SQLite helpers — stdlib only (dependency-free for hook use)
# ---------------------------------------------------------------------------


def _author_db_path(storyforge_home: Path | None = None) -> Path:
    home = storyforge_home or (Path.home() / ".storyforge")
    return home / "db" / "authors.db"


def _query_author_discoveries(
    author_slug: str,
    discovery_type: str,
    storyforge_home: Path | None = None,
) -> list[str] | None:
    """Return ``text`` values from ``author_discoveries`` table, or ``None`` if
    the DB file is absent.

    Returns ``None`` (not an empty list) when the DB does not exist — callers
    treat ``None`` as "no data available" and return ``[]``.  An empty list
    means the DB exists but the author has no entries of this type.
    """
    import sqlite3  # stdlib — keeps the module dependency-free for hook use
    db_path = _author_db_path(storyforge_home)
    if not db_path.is_file():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT text FROM author_discoveries"
            " WHERE author_slug=? AND discovery_type=? ORDER BY id",
            (author_slug, discovery_type),
        ).fetchall()
        conn.close()
        return [r["text"] for r in rows]
    except Exception:  # pragma: no cover
        return None


def _build_patterns_from_tic_db_texts(texts: list[str]) -> list[BannedPattern]:
    """Convert ``author_discoveries`` DB rows (``recurring_tics``) to ``BannedPattern`` list.

    The ``text`` column stores the bullet body without the leading ``- ``
    prefix (e.g. ``**"thing"** — concretize on sight.``).  We reconstruct a
    minimal bullet so the existing parsing helpers can be reused verbatim.
    """
    source = "author writing discoveries (DB)"
    reason = "recurring tic promoted from a finished book"
    seen: set[str] = set()
    patterns: list[BannedPattern] = []

    def _emit(label: str, compiled: re.Pattern[str], severity: str, chapter_limit: int) -> None:
        cleaned = _strip_parenthetical(label).strip()
        if len(cleaned) < 2:
            return
        key = cleaned.lower()
        if key in seen:
            return
        seen.add(key)
        patterns.append(
            BannedPattern(
                label=cleaned,
                pattern=compiled,
                severity=severity,
                source=source,
                reason=reason,
                chapter_limit=chapter_limit,
            )
        )

    for text in texts:
        # Prepend "- " so _RECURRING_TIC_BULLET_RE can match; DB stores body only.
        bullet_match = _RECURRING_TIC_BULLET_RE.match("- " + text + "\n")
        if not bullet_match:
            continue
        bold_title = bullet_match.group("title")
        body_text = bullet_match.group("body") or ""
        full_bullet = bold_title + " " + body_text
        sev = _extract_discovery_severity(full_bullet)
        limit = _extract_discovery_limit(full_bullet)

        title_quotes = _title_inner_quotes(bold_title)
        if title_quotes:
            for phrase in title_quotes:
                _emit(
                    phrase,
                    _build_discovery_pattern(_strip_parenthetical(phrase).strip()),
                    sev,
                    limit,
                )
            continue

        body_patterns = _extract_patterns_from_tic_body(body_text)
        if body_patterns:
            for label, compiled in body_patterns:
                if compiled is None:
                    cleaned_lbl = _strip_parenthetical(label).strip()
                    if len(cleaned_lbl) < 2:
                        continue
                    _emit(label, _build_discovery_pattern(cleaned_lbl), sev, limit)
                else:
                    _emit(label, compiled, sev, limit)
            continue

        for phrase in _extract_phrases_from_bold_title(bold_title):
            _emit(
                phrase,
                _build_discovery_pattern(_strip_parenthetical(phrase).strip()),
                sev,
                limit,
            )

    return patterns


def load_author_writing_discoveries(
    author_slug: str,
    *,
    storyforge_home: Path | None = None,
) -> list[BannedPattern]:
    """Load scannable recurring-tic phrases for an author from the DB.

    Reads from the ``author_discoveries`` SQLite table (``recurring_tics``
    type). Returns ``[]`` when the DB is absent or the author has no entries.
    """
    db_texts = _query_author_discoveries(author_slug, "recurring_tics", storyforge_home)
    if db_texts is None:
        return []
    return _build_patterns_from_tic_db_texts(db_texts)



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
# Author Don'ts (block-severity) — Issue #210
# ---------------------------------------------------------------------------
#
# ``### Don'ts`` is the third subsection under ``## Writing Discoveries`` in
# the author profile. Where Recurring Tics encodes the scannable phrase
# inside the bold title's double-quotes, Don'ts encodes patterns either in
# backtick regexes (Section 11 style) or in italic example sentences.
# Without this loader, the elegant-abstraction register patterns shipped in
# PR #209 had to be duplicated into every book's CLAUDE.md to scan.

_DONTS_HEADER_RE = re.compile(
    r"^###\s+Don[’'’ʼ]?ts\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_HOOK_BACKTICK_RE = re.compile(r"`([^`\n]+)`")
_HOOK_ITALIC_RE = re.compile(r"(?<![\*\w])\*([^*\n]{3,})\*(?![\*\w])")
_HOOK_BAN_CUE_RE = re.compile(
    r"\b(banned|ban|avoid|never|don[’']?t\s+use|do\s+not\s+use|limit|no\s+\w+)\b",
    re.IGNORECASE,
)
_HOOK_REGEX_HINT_CHARS = set("|()[]\\^$?+*{}")


def _extract_dont_patterns(rule: str) -> list[tuple[str, re.Pattern[str]]]:
    """Hook-side extractor — block-tier patterns from a single Don't bullet.

    Pulls backticked strings (regex or literal) plus italic phrases when
    the bullet carries a ban cue. Quoted phrases are intentionally
    skipped: the hook keeps to the strict #70 convention of "backticks and
    italics only count as hard-block".
    """
    patterns: list[tuple[str, re.Pattern[str]]] = []
    seen: set[str] = set()

    def _add(label: str, compiled: re.Pattern[str]) -> None:
        key = compiled.pattern.lower()
        if key in seen:
            return
        seen.add(key)
        patterns.append((label, compiled))

    for m in _HOOK_BACKTICK_RE.finditer(rule):
        raw = m.group(1)
        inner = raw.strip()
        if len(inner) < 2:
            continue
        try:
            if any(c in _HOOK_REGEX_HINT_CHARS for c in inner):
                _add(inner, re.compile(raw, re.IGNORECASE))
            else:
                _add(inner, re.compile(re.escape(raw), re.IGNORECASE))
        except re.error:
            continue

    if _HOOK_BAN_CUE_RE.search(rule):
        for m in _HOOK_ITALIC_RE.finditer(rule):
            raw = m.group(1).strip()
            cleaned = raw.rstrip(".,!?;:").strip()
            if len(cleaned) < 3:
                continue
            _add(raw, re.compile(re.escape(cleaned), re.IGNORECASE))

    return patterns


def _build_patterns_from_dont_db_texts(texts: list[str]) -> list[BannedPattern]:
    """Convert ``author_discoveries`` DB rows (``donts``) to ``BannedPattern`` list."""
    patterns: list[BannedPattern] = []
    seen: set[str] = set()
    for text in texts:
        for label, compiled in _extract_dont_patterns(text):
            key = compiled.pattern.lower()
            if key in seen:
                continue
            seen.add(key)
            patterns.append(
                BannedPattern(
                    label=label,
                    pattern=compiled,
                    severity=SEVERITY_BLOCK,
                    source="author dont rules (DB)",
                    reason="forbidden shape across all books by this author",
                )
            )
    return patterns


def load_author_dont_rules(
    author_slug: str,
    *,
    storyforge_home: Path | None = None,
) -> list[BannedPattern]:
    """Load scannable don't-rules for an author from the DB.

    Reads from the ``author_discoveries`` SQLite table (``donts`` type).
    Returns ``[]`` when the DB is absent or the author has no entries.
    """
    db_texts = _query_author_discoveries(author_slug, "donts", storyforge_home)
    if db_texts is None:
        return []
    return _build_patterns_from_dont_db_texts(db_texts)


# ---------------------------------------------------------------------------
# Global anti-AI shape bans — Issue #213
# ---------------------------------------------------------------------------
#
# Section 11 of ``reference/craft/anti-ai-patterns.md`` documents the
# elegant-abstraction-register shapes as ``**Banned shape:** `regex```
# lines. PR #209 shipped these as reference text; this loader reads them
# at warn-severity so every author profile inherits the catalog without
# having to manually copy the regex into ``### Don'ts``.

_SECTION_11_HEADER_RE = re.compile(
    r"^##\s+11\.\s+",
    re.MULTILINE,
)
_NEXT_TOP_SECTION_RE = re.compile(
    r"^##\s+\d+\.\s+",
    re.MULTILINE,
)
_BANNED_SHAPE_LINE_RE = re.compile(
    r"^\*\*Banned\s+shape:\*\*\s*`([^`\n]+)`",
    re.MULTILINE | re.IGNORECASE,
)


def load_global_shape_bans(plugin_root: Path) -> list[BannedPattern]:
    """Parse banned-shape regexes from ``anti-ai-patterns.md`` Section 11.

    Returns one :class:`BannedPattern` per ``**Banned shape:** `regex```
    line found between the Section 11 header and the next top-level
    ``## N. ...`` heading. Invalid regexes are silently skipped so a
    single malformed line cannot break the global advisory layer.

    Severity is always ``warn`` — these shapes are advisory baselines.
    Authors who want hard-block treatment override per-profile via
    ``### Don'ts``.
    """
    path = plugin_root / "reference" / "craft" / "anti-ai-patterns.md"
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    header = _SECTION_11_HEADER_RE.search(text)
    if not header:
        return []
    section_text = text[header.end():]
    next_section = _NEXT_TOP_SECTION_RE.search(section_text)
    if next_section:
        section_text = section_text[: next_section.start()]

    patterns: list[BannedPattern] = []
    seen: set[str] = set()

    for match in _BANNED_SHAPE_LINE_RE.finditer(section_text):
        regex_src = match.group(1).strip()
        if not regex_src:
            continue
        key = regex_src.lower()
        if key in seen:
            continue
        try:
            compiled = re.compile(regex_src, re.IGNORECASE)
        except re.error:
            continue
        seen.add(key)
        patterns.append(
            BannedPattern(
                label=regex_src,
                pattern=compiled,
                severity=SEVERITY_WARN,
                source="global anti-ai (Section 11 shapes)",
                reason="elegant-abstraction-register pattern",
            )
        )
    return patterns


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
