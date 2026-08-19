"""Book-rules pattern extraction and scanner.

Two responsibilities, kept in one file because they share the regex
toolkit (backticks vs quoted phrases, ban cues, regex hint chars):

- Pattern extraction from rule text (rules come from the book_rules DB,
  not from parsing CLAUDE.md file text — see _read_book_rules()).
- Scanning chapter drafts against the extracted patterns.
"""

from __future__ import annotations

import bisect
import re
from pathlib import Path

from tools.analysis.manuscript.text_utils import (
    _make_snippet,
    _read_chapter_drafts,
    _strip_markdown,
)
from tools.analysis.manuscript.types import Finding, Occurrence
from tools.analysis.manuscript.vocabularies import STOP_WORDS

# Backtick-wrapped content. We split on these to distinguish regex hints from
# plain-literal tokens.
_BACKTICK_CONTENT_RE = re.compile(r"`([^`\n]+)`")

# Double-quoted phrases ≥3 chars of content. Deliberately excludes short words
# like "a" or "ok" which produce noisy false positives.
_QUOTED_CONTENT_RE = re.compile(r'"([^"\n]{3,})"')

# Characters that strongly suggest a backtick-wrapped string is intended as a
# regex rather than a literal substring.
_REGEX_HINT_CHARS = set("|()[]\\^$?+*{}")

# Cue keywords that mark a rule as containing bannable quoted phrases. Without
# a cue, quoted strings are treated as examples, not patterns.
_BAN_CUE_RE = re.compile(
    r"\b(banned|ban|avoid|never|don[’']?t\s+use|do\s+not\s+use|limit|no\s+\w+|"
    r"vermeide[nt]?|nie(?:mals)?(?:\s+(?:verwenden?|nutzen|benutzen|einsetzen))?|"
    r"kein(?:e[srnm]?)?\b|verboten|raus|"
    r"nicht\s+(?:\S+\s+)?(?:verwenden?|nutzen|benutzen|einsetzen|schreiben|tippen))\b",
    re.IGNORECASE,
)

# Segment boundaries for cue/quote scoping (#612): a sentence end — optionally
# followed by a closing quote/curly-quote character, covering the "period
# inside closing quote" (US English) convention this codebase's own dialogue
# rules use — then whitespace. A plain character-distance window was tried
# first and rejected: it breaks on any rule phrased as a cue followed by a
# list of quoted items ("Avoid: "a", "b", "c""), since items past the first
# fall outside a fixed window. Scoping by sentence keeps an entire list-style
# ban sentence together while still separating a cue in the rule's own bold
# title from an unrelated quoted example several sentences later in the body.
_SEGMENT_BOUNDARY_RE = re.compile(r'[.!?]["”’]?\s+')

# A rule's leading **bold title** is always its own segment, distinct from
# the sentence(s) that follow — even when the title and the first body
# sentence run together with no intervening period (e.g. "**Never treat X**
# — When Y, do Z."). Without this, a cue word used rhetorically in the title
# ("**Never** treat comedy as a timeout...") would share a segment with an
# unrelated quoted example anywhere in that same first sentence.
_BOLD_TITLE_RE = re.compile(r"^\*\*[^*]+\*\*")


def _rule_segment_boundaries(rule: str) -> list[int]:
    """Offsets carving `rule` into cue/quote scoping segments (#612)."""
    bold = _BOLD_TITLE_RE.match(rule)
    start = bold.end() if bold else 0
    boundaries = [0, start] if bold else [0]
    boundaries.extend(m.end() for m in _SEGMENT_BOUNDARY_RE.finditer(rule, start))
    boundaries.append(len(rule))
    return sorted(set(boundaries))


def _segment_index(offset: int, boundaries: list[int]) -> int:
    """Index of the segment (between consecutive boundaries) containing offset."""
    return bisect.bisect_right(boundaries, offset) - 1

# Italic-wrapped content (single asterisks). The negative look-arounds keep
# this from matching the inner content of **bold** spans. Minimum 3 chars of
# content avoids noise from single-letter emphasis. Used only by the author-
# profile Don't extractor (#210) — book CLAUDE.md rules continue to treat
# italics as narrative examples, not bannable patterns.
_ITALIC_CONTENT_RE = re.compile(r"(?<![\*\w])\*([^*\n]{3,})\*(?![\*\w])")

# Quality-exception cue (#608) — phrasing that marks a rule as documenting
# its own "sometimes fine, sometimes not" carve-out, which a regex match
# cannot evaluate (it requires human/LLM judgment of whether a specific
# occurrence does the work the exception describes). Rules matching this cue
# get their violations flagged as WARN rather than a hard FAIL at the gate
# level — see tools/shared/gate_derivation.py::derive_from_manuscript_scan.
#
# A bare conjunction ("unless", "as long as") is not enough on its own
# (code review M-1) — "Don't let pacing sag unless the scene demands
# stillness" is an ordinary conditional, not a quality carve-out for the
# banned construction itself. Require the conjunction to be followed
# (within the same clause, not crossing a sentence boundary) by a verb that
# actually judges quality/craft — matching :data:`_QUALITY_JUDGMENT_VERBS`.
# Covers German equivalents (``nur wenn``, ``es sei denn``, ``sofern``,
# ``solange``) alongside :data:`_BAN_CUE_RE`'s existing German coverage —
# a German-language rule with a real quality exception must not be exempt
# from this check just because the pattern was English-only.
_QUALITY_JUDGMENT_VERBS = (
    r"does|serves|works|earns|characterizes|carries|justifies|"
    r"tut|dient|funktioniert|rechtfertigt|tr[aä]gt"
)
_QUALITY_EXCEPTION_RE = re.compile(
    r"\b(?:only when|except when|unless|provided that|as long as|"
    r"nur wenn|es sei denn|sofern|solange)\b[^.!?]{0,60}\b(?:" + _QUALITY_JUDGMENT_VERBS + r")\b"
    r"|\bwhen it (?:actually |really )?(?:does|serves|works|characterizes)\b",
    re.IGNORECASE,
)

# Recommendation markers (#217) — words/symbols that signal "what follows is
# the recommended replacement, not the banned example". The author-Don't
# extractor caps the italic/quoted extraction window at the first occurrence
# of any of these markers so positive examples never end up as banned
# patterns. Backticks are unaffected — they encode explicit ban intent.
#
# Word-boundary markers use ``\b`` to avoid false positives inside other
# words (``rerendered`` must not trigger the ``Render`` marker). The arrow
# ``→`` is matched literally; colon-suffixed forms allow optional whitespace
# before the colon.
_RECOMMENDATION_MARKER_RE = re.compile(
    r"(?:"
    r"\bRender\b"
    r"|\bReplace\b"
    r"|\bUse\s+instead\b"
    r"|\bInstead\s*:"
    r"|\bAllowed\s*:"
    r"|\bBetter\s*:"
    r"|\bRewrite\s+as\b"
    r"|\bRather\s*:"
    r"|→"
    r")",
    re.IGNORECASE,
)


def _read_book_rules(book_path: Path) -> list[str]:
    """Return rule texts for a book — reads from the book_rules DB (sole source).

    Returns an empty list when no rules exist or the DB is unavailable.

    Raises :class:`~tools.db.connection.BookNotLinkedToSeriesError` (Issue
    #579) rather than swallowing it — a book scaffolded into a series but
    never linked via ``add_book_to_series()`` has no reliable ``book_num``
    to query, so returning ``[]`` here would silently report "no rule
    violations" for a book whose rules were never actually checked. The
    caller (:func:`_scan_book_rules`) turns this into a WARN-level finding
    instead of a false gate PASS.
    """
    from tools.db.connection import BookNotLinkedToSeriesError

    try:
        from tools.db.book_rules import list_rules as _db_list_rules
        from tools.db.connection import get_book_num, get_db_slug_for_book, open_canon_db

        db_slug = get_db_slug_for_book(book_path)
        book_num = get_book_num(book_path)
        conn = open_canon_db(db_slug)
        try:
            rows = _db_list_rules(conn, book_num=book_num, rule_type="rule")
        finally:
            conn.close()
        return [r["text"] for r in rows]
    except BookNotLinkedToSeriesError:
        raise
    except Exception:  # pylint: disable=broad-except
        return []


def _extract_patterns_from_rule(rule: str) -> list[tuple[str, re.Pattern[str]]]:
    """Extract scannable patterns from a single rule text.

    Returns a list of ``(display_label, compiled_regex)`` tuples. Heuristic
    extraction — stdlib only:

    1. Backtick-wrapped strings are always extracted. If the content contains
       regex metacharacters it's compiled as a regex, otherwise as a literal
       substring. Whitespace inside the backticks is preserved so the user
       can encode word-boundary intent (e.g. `` ` thing ` ``).
    2. Double-quoted phrases are extracted *only* when a ban cue (``banned``,
       ``avoid``, ``never``, ``don't use``, ``do not use``, ``ban``,
       ``limit``, ``no X``) appears in the *same scoping segment* as the
       quote (see :func:`_rule_segment_boundaries`) — not merely anywhere in
       the rule text. A rule's bold title routinely uses a cue word (e.g.
       "**Never** treat comedy as a timeout...") that has nothing to do with
       an unrelated quoted example several sentences later in the same
       rule's prose (e.g. "...give the reader a \"break\"", quoted only to
       illustrate a *different* concept). A whole-rule presence check for
       the cue can't tell those apart and mines the illustrative word as a
       banned literal; scoping the cue to the sentence (or bold title) it
       actually sits in ties the two together the way a human reading the
       rule would (Issue #612).
    3. Italics (``*foo*``) are intentionally ignored — they're used for
       narrative examples, not scannable bans.
    4. Malformed regex strings are skipped rather than raising.
    """
    patterns: list[tuple[str, re.Pattern[str]]] = []
    seen: set[str] = set()

    def _add(label: str, compiled: re.Pattern[str]) -> None:
        key = compiled.pattern.lower()
        if key in seen:
            return
        seen.add(key)
        patterns.append((label, compiled))

    for m in _BACKTICK_CONTENT_RE.finditer(rule):
        raw = m.group(1)
        inner = raw.strip()
        if len(inner) < 2:
            continue
        if any(c in _REGEX_HINT_CHARS for c in inner):
            try:
                _add(inner, re.compile(raw, re.IGNORECASE))
            except re.error:
                continue
        else:
            _add(inner, re.compile(re.escape(raw), re.IGNORECASE))

    boundaries = _rule_segment_boundaries(rule)
    cue_segments = {_segment_index(m.start(), boundaries) for m in _BAN_CUE_RE.finditer(rule)}
    if cue_segments:
        for m in _QUOTED_CONTENT_RE.finditer(rule):
            raw = m.group(1).strip()
            if len(raw) < 6 or raw.lower() in STOP_WORDS:
                continue
            if _segment_index(m.start(), boundaries) not in cue_segments:
                # No ban cue shares this quote's sentence (or bold title) —
                # it's an illustrative example elsewhere in the rule's
                # prose, not the thing the cue is actually banning (#612).
                continue
            _add(raw, re.compile(re.escape(raw), re.IGNORECASE))

    return patterns


def _rule_label(rule: str, max_len: int = 80) -> str:
    """Short display label for a rule — typically the bold'd title prefix."""
    bold = re.match(r"\*\*(?P<title>[^*]+)\*\*", rule)
    if bold:
        title = bold.group("title").strip()
    else:
        title = rule
    title = re.sub(r"\s+", " ", title)
    if len(title) > max_len:
        title = title[: max_len - 1].rstrip() + "…"
    return title


def _scan_book_rules(book_path: Path) -> list[Finding]:
    """Scan chapter drafts for violations of rules in the book's CLAUDE.md.

    A book that exists but hasn't been linked to its series via
    ``add_book_to_series()`` yet (Issue #579) has no reliable ``book_num`` —
    rather than silently reporting zero rule violations (which would read
    as "verified clean" and let the export gate PASS), this returns a
    single WARN-severity finding flagging that book-rule checking could not
    run, so the manuscript scan never looks cleaner than it actually is.
    """
    from tools.db.connection import BookNotLinkedToSeriesError

    try:
        rules = _read_book_rules(book_path)
    except BookNotLinkedToSeriesError as exc:
        return [
            Finding(
                phrase="book_rules_unreadable",
                category="book_rules_unreadable",
                severity="high",
                count=1,
                occurrences=[],
                source_rule=str(exc),
                promotable=False,
            )
        ]
    if not rules:
        return []
    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    findings: list[Finding] = []
    for rule in rules:
        patterns = _extract_patterns_from_rule(rule)
        if not patterns:
            continue
        rule_label = _rule_label(rule)
        seen_positions: set[tuple[str, int]] = set()
        occurrences: list[Occurrence] = []
        matched_labels: dict[str, None] = {}  # insertion-ordered unique set
        for display, pattern in patterns:
            pattern_hit = False
            for chapter_slug, raw_text in drafts:
                cleaned = _strip_markdown(raw_text)
                for line_no, line in enumerate(cleaned.splitlines(), start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    for m in pattern.finditer(stripped):
                        key = (chapter_slug, line_no)
                        if key in seen_positions:
                            continue
                        seen_positions.add(key)
                        snippet = _make_snippet(stripped, m.group(0).lower())
                        occurrences.append(Occurrence(chapter=chapter_slug, line=line_no, snippet=snippet))
                        pattern_hit = True
            if pattern_hit:
                matched_labels[display] = None
        if not occurrences:
            continue
        phrase = " / ".join(matched_labels) if matched_labels else rule_label
        findings.append(
            Finding(
                phrase=phrase,
                category="book_rule_violation",
                severity="high",
                count=len(occurrences),
                occurrences=sorted(occurrences, key=lambda o: (o.chapter, o.line)),
                source_rule=rule_label,
                has_quality_exception=bool(_QUALITY_EXCEPTION_RE.search(rule)),
            )
        )
    return findings


def _scan_writing_discoveries(book_path: Path) -> list[Finding]:
    """Scan chapter drafts for violations of the author's Writing Discoveries.

    Mirrors :func:`_scan_book_rules` but loads patterns from
    ``recurring_tics``-type ``author_discoveries`` DB rows via
    :func:`tools.banlist_loader.load_author_writing_discoveries`. Findings are
    emitted with ``category='writing_discovery_violation'`` so the report can
    distinguish them from book-rule violations.

    Issue #151 follow-up — without this scanner, phrases promoted via
    ``/storyforge:harvest-author-rules`` were invisible to the manuscript
    checker even though the chapter-writer brief picked them up.
    """
    # Lazy import: the manuscript module already keeps imports light to stay
    # patchable from tests.
    from tools.banlist_loader import author_slug_from_book, load_author_writing_discoveries

    author_slug = author_slug_from_book(book_path)
    if not author_slug:
        return []

    try:
        patterns = load_author_writing_discoveries(author_slug)
    except Exception:  # pylint: disable=broad-except
        return []
    if not patterns:
        return []

    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    findings: list[Finding] = []
    for banned in patterns:
        seen_positions: set[tuple[str, int]] = set()
        occurrences: list[Occurrence] = []
        for chapter_slug, raw_text in drafts:
            cleaned = _strip_markdown(raw_text)
            for line_no, line in enumerate(cleaned.splitlines(), start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                for m in banned.pattern.finditer(stripped):
                    key = (chapter_slug, line_no)
                    if key in seen_positions:
                        continue
                    seen_positions.add(key)
                    snippet = _make_snippet(stripped, m.group(0).lower())
                    occurrences.append(Occurrence(chapter=chapter_slug, line=line_no, snippet=snippet))
        if not occurrences:
            continue
        findings.append(
            Finding(
                phrase=banned.label,
                category="writing_discovery_violation",
                severity="high",
                count=len(occurrences),
                occurrences=sorted(occurrences, key=lambda o: (o.chapter, o.line)),
                source_rule=f"author profile ## Writing Discoveries — {banned.label}",
            )
        )
    return findings


def _extract_patterns_from_author_dont(rule: str) -> list[tuple[str, re.Pattern[str]]]:
    """Author-profile Don't extractor — superset of :func:`_extract_patterns_from_rule`.

    Adds italic-phrase extraction on top of the book-rule extractor. In a
    book's ``CLAUDE.md`` italics are narrative examples and stay invisible
    to the scanner; in author Don'ts italics are the user-facing encoding
    of the example phrases that should be flagged (Section 11 of
    ``anti-ai-patterns.md``).

    Extraction rules:

    1. Backticks: always extracted (literal or regex, same heuristic as
       :func:`_extract_patterns_from_rule`). Position-independent — they
       encode explicit ban intent.
    2. Double-quoted phrases: extracted only when the rule carries a ban
       cue (``Never``, ``Avoid``, ``Don't use``, ...) AND only from inside
       the "ban window" — the slice before the first recommendation marker
       (``Render``, ``Instead:``, ``→``, ...). Phrases after the marker are
       positive examples, not bans (#217).
    3. Italic phrases (single ``*foo*``, not bold ``**foo**``): same gate
       as quoted phrases. Bold spans are skipped via ``(?<![\\*\\w])`` /
       ``(?![\\*\\w])`` look-arounds.
    """
    patterns: list[tuple[str, re.Pattern[str]]] = []
    seen: set[str] = set()

    def _add(label: str, compiled: re.Pattern[str]) -> None:
        key = compiled.pattern.lower()
        if key in seen:
            return
        seen.add(key)
        patterns.append((label, compiled))

    # Backticks: extracted from the full rule regardless of marker position.
    for m in _BACKTICK_CONTENT_RE.finditer(rule):
        raw = m.group(1)
        inner = raw.strip()
        if len(inner) < 2:
            continue
        if any(c in _REGEX_HINT_CHARS for c in inner):
            try:
                _add(inner, re.compile(raw, re.IGNORECASE))
            except re.error:
                continue
        else:
            _add(inner, re.compile(re.escape(raw), re.IGNORECASE))

    if not _BAN_CUE_RE.search(rule):
        return patterns

    # Italic and quoted extraction is bounded by the first recommendation
    # marker (#217). Everything from start-of-rule up to (but not including)
    # the marker is the ban window; phrases after the marker are positive
    # examples and must not be extracted as banned patterns.
    #
    # Markers inside ``*...*`` italic spans are part of the example, not
    # a boundary signal — mask italic content with spaces before searching
    # so positions stay aligned but the marker regex cannot land inside.
    masked = _ITALIC_CONTENT_RE.sub(lambda m: " " * len(m.group(0)), rule)
    marker = _RECOMMENDATION_MARKER_RE.search(masked)
    ban_window = rule[: marker.start()] if marker else rule

    for m in _QUOTED_CONTENT_RE.finditer(ban_window):
        raw = m.group(1).strip()
        if len(raw) < 6 or raw.lower() in STOP_WORDS:
            continue
        _add(raw, re.compile(re.escape(raw), re.IGNORECASE))

    for m in _ITALIC_CONTENT_RE.finditer(ban_window):
        raw = m.group(1).strip()
        # Italic example sentences in author Don'ts typically end with a period
        # (full sentence). Trailing sentence punctuation is decorative, not part
        # of the bannable substring — strip it so the pattern matches the
        # phrase wherever it sits in the manuscript.
        cleaned = raw.rstrip(".,!?;:").strip()
        if len(cleaned) < 3:
            continue
        _add(raw, re.compile(re.escape(cleaned), re.IGNORECASE))
    return patterns


def _read_author_rules(book_path: Path) -> list[str]:
    """Extract Don't-bullet text from the resolved author's discoveries DB.

    Returns one string per ``donts``-type row in the ``author_discoveries``
    SQLite table for the book's author (Issue #604). Previously read
    ``profile.md ## Writing Discoveries / ### Don'ts`` directly from the
    file — which went stale the moment a Don't was added/edited/removed
    via MCP (``write_author_discovery``, ``delete_discovery``, ...), since
    those writes target the DB only. Reading the file also silently missed
    any *second* ``### Don'ts (...)`` subsection whose header text didn't
    match the exact ``### Don'ts`` anchor (a book can legitimately have
    more than one, e.g. ``### Don'ts`` plus a later
    ``### Don'ts (beyond banned phrases)`` promoted from a different
    book) — the DB has no such per-subsection blind spot, since every row
    is just ``discovery_type='donts'`` regardless of which subsection it
    was originally promoted under.

    Returns an empty list when the book has no resolvable author or the
    author has no ``donts`` entries.
    """
    # Lazy import: keeps the manuscript module patchable from tests and
    # avoids a top-level import of the slug resolver.
    from tools.banlist_loader import _query_author_discoveries, author_slug_from_book

    slug = author_slug_from_book(book_path)
    if not slug:
        return []

    return _query_author_discoveries(slug, "donts") or []


def _scan_author_rules(book_path: Path) -> list[Finding]:
    """Scan chapter drafts for violations of the author profile's ``### Don'ts``.

    Mirrors :func:`_scan_book_rules` but reads patterns from ``donts``-type
    ``author_discoveries`` DB rows via :func:`_read_author_rules` +
    :func:`_extract_patterns_from_author_dont`.
    Findings are emitted with ``category='author_rule_violation'`` so the
    report can distinguish them from book-rule and Recurring-Tic violations.

    Issue #210 — without this scanner, every author-level Don't had to be
    duplicated into each book's ``CLAUDE.md`` to be scannable.
    """
    from tools.banlist_loader import author_slug_from_book

    rules = _read_author_rules(book_path)
    if not rules:
        return []
    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    author_slug = author_slug_from_book(book_path) or "author"

    findings: list[Finding] = []
    for rule in rules:
        patterns = _extract_patterns_from_author_dont(rule)
        if not patterns:
            continue
        rule_label = _rule_label(rule)
        seen_positions: set[tuple[str, int]] = set()
        occurrences: list[Occurrence] = []
        matched_labels: dict[str, None] = {}
        for display, pattern in patterns:
            pattern_hit = False
            for chapter_slug, raw_text in drafts:
                cleaned = _strip_markdown(raw_text)
                for line_no, line in enumerate(cleaned.splitlines(), start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    for m in pattern.finditer(stripped):
                        key = (chapter_slug, line_no)
                        if key in seen_positions:
                            continue
                        seen_positions.add(key)
                        snippet = _make_snippet(stripped, m.group(0).lower())
                        occurrences.append(Occurrence(chapter=chapter_slug, line=line_no, snippet=snippet))
                        pattern_hit = True
            if pattern_hit:
                matched_labels[display] = None
        if not occurrences:
            continue
        phrase = " / ".join(matched_labels) if matched_labels else rule_label
        findings.append(
            Finding(
                phrase=phrase,
                category="author_rule_violation",
                severity="high",
                count=len(occurrences),
                occurrences=sorted(occurrences, key=lambda o: (o.chapter, o.line)),
                source_rule=(
                    f"author profile (## Writing Discoveries / Don'ts) "
                    f"[{author_slug}] — {rule_label}"
                ),
            )
        )
    return findings


def _scan_author_vocab(book_path: Path) -> list[Finding]:
    """Scan chapter drafts for violations of the author's flat vocabulary bans.

    Loads patterns from ``donts``-type DB rows via
    :func:`tools.banlist_loader.load_author_vocab` — the canonical
    author-scoped phrase store that the PostToolUse hook already enforces.
    Surfacing the same bans in the manuscript-checker closes the gap when
    the hook is bypassed (warn mode, edits via tools that skip the hook).

    Findings carry ``category='author_vocab_violation'`` to match the hook's
    category vocabulary.
    """
    from tools.banlist_loader import author_slug_from_book, load_author_vocab

    slug = author_slug_from_book(book_path)
    if not slug:
        return []

    try:
        patterns = load_author_vocab(slug)
    except Exception:  # pylint: disable=broad-except
        return []
    if not patterns:
        return []

    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    findings: list[Finding] = []
    for banned in patterns:
        seen_positions: set[tuple[str, int]] = set()
        occurrences: list[Occurrence] = []
        for chapter_slug, raw_text in drafts:
            cleaned = _strip_markdown(raw_text)
            for line_no, line in enumerate(cleaned.splitlines(), start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                for m in banned.pattern.finditer(stripped):
                    key = (chapter_slug, line_no)
                    if key in seen_positions:
                        continue
                    seen_positions.add(key)
                    snippet = _make_snippet(stripped, m.group(0).lower())
                    occurrences.append(Occurrence(chapter=chapter_slug, line=line_no, snippet=snippet))
        if not occurrences:
            continue
        findings.append(
            Finding(
                phrase=banned.label,
                category="author_vocab_violation",
                severity="high",
                count=len(occurrences),
                occurrences=sorted(occurrences, key=lambda o: (o.chapter, o.line)),
                source_rule=f"author vocabulary [{slug}] — {banned.label}",
            )
        )
    return findings


def _scan_global_shape_bans(
    book_path: Path,
    *,
    plugin_root: Path | None = None,
) -> list[Finding]:
    """Scan chapter drafts for catalog-level shape bans (Issue #213).

    Loads patterns from ``reference/craft/anti-ai-patterns.md`` Section 11
    via :func:`tools.banlist_loader.load_global_shape_bans`. Findings are
    emitted with ``category='global_shape_violation'`` and
    ``severity='medium'`` — advisory, not user-asserted. The hook surfaces
    the same patterns at warn-severity at write time.

    Dedup with author-level bans: if the author's ``### Don'ts`` or
    flat-vocabulary ``donts`` rows already match a phrase at the same
    chapter+line, the global-shape finding is suppressed to avoid
    double-flagging the same hit.
    """
    from tools.banlist_loader import (
        author_slug_from_book,
        load_author_dont_rules,
        load_author_vocab,
        load_author_writing_discoveries,
        load_global_shape_bans,
    )

    if plugin_root is None:
        # Three levels up from tools/analysis/manuscript/rules.py.
        plugin_root = Path(__file__).resolve().parents[3]

    try:
        patterns = load_global_shape_bans(plugin_root)
    except Exception:  # pylint: disable=broad-except
        return []
    if not patterns:
        return []

    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    # Build the set of (chapter_slug, line_no) positions where an author-level
    # ban already matches — those positions are suppressed from the global
    # report so the user does not see the same line flagged twice.
    suppress: set[tuple[str, int]] = set()
    author_slug = author_slug_from_book(book_path)
    if author_slug:
        author_patterns: list = []
        try:
            author_patterns.extend(load_author_vocab(author_slug))
        except Exception:  # pylint: disable=broad-except
            pass
        try:
            author_patterns.extend(load_author_writing_discoveries(author_slug))
        except Exception:  # pylint: disable=broad-except
            pass
        try:
            author_patterns.extend(load_author_dont_rules(author_slug))
        except Exception:  # pylint: disable=broad-except
            pass
        for ap in author_patterns:
            for chapter_slug, raw_text in drafts:
                cleaned = _strip_markdown(raw_text)
                for line_no, line in enumerate(cleaned.splitlines(), start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if ap.pattern.search(stripped):
                        suppress.add((chapter_slug, line_no))

    findings: list[Finding] = []
    for banned in patterns:
        seen_positions: set[tuple[str, int]] = set()
        occurrences: list[Occurrence] = []
        for chapter_slug, raw_text in drafts:
            cleaned = _strip_markdown(raw_text)
            for line_no, line in enumerate(cleaned.splitlines(), start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                key = (chapter_slug, line_no)
                if key in suppress:
                    continue
                for m in banned.pattern.finditer(stripped):
                    if key in seen_positions:
                        continue
                    seen_positions.add(key)
                    snippet = _make_snippet(stripped, m.group(0).lower())
                    occurrences.append(Occurrence(chapter=chapter_slug, line=line_no, snippet=snippet))
        if not occurrences:
            continue
        findings.append(
            Finding(
                phrase=banned.label,
                category="global_shape_violation",
                severity="medium",
                count=len(occurrences),
                occurrences=sorted(occurrences, key=lambda o: (o.chapter, o.line)),
                source_rule=(
                    "global anti-ai (Section 11 shapes) — "
                    "reference/craft/anti-ai-patterns.md"
                ),
            )
        )
    return findings


def _scan_global_ai_tells(
    book_path: Path,
    *,
    plugin_root: Path | None = None,
) -> list[Finding]:
    """Scan chapter drafts for catalog-level AI-tell vocabulary (Issue #216).

    Loads patterns from ``reference/craft/anti-ai-patterns.md`` Section 1
    (``### Heavily Flagged Words and Phrases``) via
    :func:`tools.banlist_loader.load_global_ai_tells`. Findings are emitted
    with ``category='ai_tell_violation'`` and ``severity='medium'`` —
    advisory, parallel to ``global_shape_violation``. The hook already
    surfaces the same patterns at warn-severity at write time; this scanner
    closes the gap for the post-draft manuscript sweep.

    Dedup with author-level bans: if the author's flat-vocabulary ``donts``
    rows, ``### Don'ts``, or ``### Recurring Tics`` already match a phrase
    at the same chapter+line, the catalog finding is suppressed.
    """
    from tools.banlist_loader import (
        author_slug_from_book,
        load_author_dont_rules,
        load_author_vocab,
        load_author_writing_discoveries,
        load_global_ai_tells,
    )

    if plugin_root is None:
        # Three levels up from tools/analysis/manuscript/rules.py.
        plugin_root = Path(__file__).resolve().parents[3]

    try:
        patterns = load_global_ai_tells(plugin_root)
    except Exception:  # pylint: disable=broad-except
        return []
    if not patterns:
        return []

    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    suppress: set[tuple[str, int]] = set()
    author_slug = author_slug_from_book(book_path)
    if author_slug:
        author_patterns: list = []
        try:
            author_patterns.extend(load_author_vocab(author_slug))
        except Exception:  # pylint: disable=broad-except
            pass
        try:
            author_patterns.extend(load_author_writing_discoveries(author_slug))
        except Exception:  # pylint: disable=broad-except
            pass
        try:
            author_patterns.extend(load_author_dont_rules(author_slug))
        except Exception:  # pylint: disable=broad-except
            pass
        for ap in author_patterns:
            for chapter_slug, raw_text in drafts:
                cleaned = _strip_markdown(raw_text)
                for line_no, line in enumerate(cleaned.splitlines(), start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if ap.pattern.search(stripped):
                        suppress.add((chapter_slug, line_no))

    findings: list[Finding] = []
    for banned in patterns:
        seen_positions: set[tuple[str, int]] = set()
        occurrences: list[Occurrence] = []
        for chapter_slug, raw_text in drafts:
            cleaned = _strip_markdown(raw_text)
            for line_no, line in enumerate(cleaned.splitlines(), start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                key = (chapter_slug, line_no)
                if key in suppress:
                    continue
                for m in banned.pattern.finditer(stripped):
                    if key in seen_positions:
                        continue
                    seen_positions.add(key)
                    snippet = _make_snippet(stripped, m.group(0).lower())
                    occurrences.append(Occurrence(chapter=chapter_slug, line=line_no, snippet=snippet))
        if not occurrences:
            continue
        findings.append(
            Finding(
                phrase=banned.label,
                category="ai_tell_violation",
                severity="medium",
                count=len(occurrences),
                occurrences=sorted(occurrences, key=lambda o: (o.chapter, o.line)),
                source_rule=(
                    "global anti-ai (Section 1 vocabulary) — "
                    "reference/craft/anti-ai-patterns.md"
                ),
            )
        )
    return findings


__all__ = [
    "_extract_patterns_from_author_dont",
    "_extract_patterns_from_rule",
    "_read_author_rules",
    "_read_book_rules",
    "_rule_label",
    "_scan_author_rules",
    "_scan_author_vocab",
    "_scan_book_rules",
    "_scan_global_ai_tells",
    "_scan_global_shape_bans",
    "_scan_writing_discoveries",
]
