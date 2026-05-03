"""Book CLAUDE.md ## Rules parser + scanner.

Two responsibilities, kept in one file because they share the regex
toolkit (backticks vs quoted phrases, ban cues, regex hint chars):

- Pattern extraction from rule text.
- Scanning chapter drafts against the extracted patterns.
"""

from __future__ import annotations

import re
from pathlib import Path

from tools.analysis.manuscript.text_utils import (
    _make_snippet,
    _read_chapter_drafts,
    _strip_markdown,
)
from tools.analysis.manuscript.types import Finding, Occurrence
from tools.analysis.manuscript.vocabularies import STOP_WORDS

# Match "## Rules" heading through to the next "## " heading or EOF.
_RULES_SECTION_RE = re.compile(
    r"^##\s+Rules\s*$(.*?)(?=^##\s+\S|\Z)",
    re.MULTILINE | re.DOTALL,
)

# Match a markdown list item that spans until the next blank line, next list
# item, or section end. This preserves multi-sentence rules written on one
# logical bullet (continued across wrapped lines).
_RULE_BULLET_RE = re.compile(
    r"^-\s+(?P<body>.+?)(?=^-\s+|^\s*$|^<!--|\Z)",
    re.MULTILINE | re.DOTALL,
)

# Comment markers inside the Rules section — stripped before bullet parsing.
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

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
    r"\b(banned|ban|avoid|never|don[’']?t\s+use|do\s+not\s+use|limit|no\s+\w+)\b",
    re.IGNORECASE,
)


def _read_book_rules(book_path: Path) -> list[str]:
    """Extract rule text entries from a book's CLAUDE.md.

    Returns one string per bullet item found under the ``## Rules`` section,
    including entries inside the ``<!-- RULES:START --> ... <!-- RULES:END -->``
    block and any static entries listed above it. Comment markers are stripped
    before bullet parsing so they don't break list items.

    Returns an empty list when CLAUDE.md is missing or has no Rules section.
    """
    claudemd = book_path / "CLAUDE.md"
    if not claudemd.is_file():
        return []
    try:
        text = claudemd.read_text(encoding="utf-8")
    except OSError:
        return []

    match = _RULES_SECTION_RE.search(text)
    if not match:
        return []
    section = _COMMENT_RE.sub("", match.group(1))

    rules: list[str] = []
    for m in _RULE_BULLET_RE.finditer(section):
        body = m.group("body").strip()
        body = re.sub(r"\s+", " ", body)
        if body:
            rules.append(body)
    return rules


def _extract_patterns_from_rule(rule: str) -> list[tuple[str, re.Pattern[str]]]:
    """Extract scannable patterns from a single rule text.

    Returns a list of ``(display_label, compiled_regex)`` tuples. Heuristic
    extraction — stdlib only:

    1. Backtick-wrapped strings are always extracted. If the content contains
       regex metacharacters it's compiled as a regex, otherwise as a literal
       substring. Whitespace inside the backticks is preserved so the user
       can encode word-boundary intent (e.g. `` ` thing ` ``).
    2. Double-quoted phrases are extracted *only* when the rule contains a
       ban cue (``banned``, ``avoid``, ``never``, ``don't use``, ``do not
       use``, ``ban``, ``limit``, ``no X``).
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

    if _BAN_CUE_RE.search(rule):
        for m in _QUOTED_CONTENT_RE.finditer(rule):
            raw = m.group(1).strip()
            if len(raw) < 6 or raw.lower() in STOP_WORDS:
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
    """Scan chapter drafts for violations of rules in the book's CLAUDE.md."""
    rules = _read_book_rules(book_path)
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
            )
        )
    return findings


def _scan_writing_discoveries(book_path: Path) -> list[Finding]:
    """Scan chapter drafts for violations of the author's Writing Discoveries.

    Mirrors :func:`_scan_book_rules` but loads patterns from
    ``profile.md ## Writing Discoveries / ### Recurring Tics`` via
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


__all__ = [
    "_extract_patterns_from_rule",
    "_read_book_rules",
    "_rule_label",
    "_scan_book_rules",
    "_scan_writing_discoveries",
]
