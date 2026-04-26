#!/usr/bin/env python3
"""PostToolUse hook: validate chapter ``draft.md`` after Write/Edit/MultiEdit.

Reads the Claude Code hook JSON payload from stdin, locates the affected
file, and runs StoryForge's prose-quality checks. Findings carry a
severity (``block`` or ``warn``); when any ``block`` finding is produced
in ``strict`` mode the hook exits with code 2, which Claude Code surfaces
as a tool-call rejection and feeds back into the model.

The hook only reacts to writes against ``**/chapters/*/draft.md``. All
other file events are passed through silently.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(
    os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent))
)

# Make tools package importable when the hook runs standalone (and from
# pytest, where conftest.py also extends sys.path).
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))


# ---------------------------------------------------------------------------
# Severity vocabulary
# ---------------------------------------------------------------------------

SEVERITY_BLOCK = "block"
SEVERITY_WARN = "warn"

VALID_MODES = ("strict", "warn")
DEFAULT_MODE = "strict"

# Tools whose output should be inspected. Anything else is ignored.
WATCHED_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})

# Fallback AI-tell list — used only when ``reference/craft/anti-ai-patterns.md``
# cannot be parsed. The loader in ``tools.banlist_loader`` is the canonical
# source. Severity stays warn for both paths to preserve #70's behavior.
_AI_TELL_FALLBACK: tuple[str, ...] = (
    "delve", "tapestry", "nuanced", "vibrant", "embark", "resonate",
    "pivotal", "multifaceted", "realm", "testament", "intricate",
    "myriad", "unprecedented", "foster", "beacon", "juxtaposition",
    "paradigm", "synergy", "interplay", "ever-evolving", "navigate",
    "uncover",
)


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    message: str
    line: int | None = None


# ---------------------------------------------------------------------------
# Hook payload parsing
# ---------------------------------------------------------------------------


def _read_payload() -> dict[str, Any] | None:
    """Read the hook JSON payload from stdin. Returns None if stdin is empty
    or not valid JSON (legacy invocation path)."""
    if sys.stdin.isatty():
        return None
    raw = sys.stdin.read().strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _extract_file_path(payload: dict[str, Any]) -> str | None:
    """Find the file path in the hook payload. Tries tool_input first, then
    tool_response — schema differs between Write/Edit/MultiEdit."""
    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input, dict):
        fp = tool_input.get("file_path")
        if isinstance(fp, str) and fp:
            return fp
    tool_response = payload.get("tool_response") or {}
    if isinstance(tool_response, dict):
        for key in ("filePath", "file_path"):
            fp = tool_response.get(key)
            if isinstance(fp, str) and fp:
                return fp
    return None


# ---------------------------------------------------------------------------
# Mode resolution (strict vs warn)
# ---------------------------------------------------------------------------


def _find_book_root(file_path: Path) -> Path | None:
    """Walk up from a chapter draft.md to find the book root (the directory
    that contains both ``chapters/`` and ``README.md``)."""
    for parent in file_path.parents:
        if (parent / "chapters").is_dir() and (parent / "README.md").is_file():
            return parent
    return None


_FRONTMATTER_RE = re.compile(r"^---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
_LINTER_MODE_RE = re.compile(
    r"^\s*linter_mode\s*:\s*[\"']?(?P<value>strict|warn)[\"']?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _resolve_mode(file_path: Path) -> str:
    """Resolve linter mode for the given draft path.

    Default is ``strict``. Books opt into ``warn`` by setting
    ``linter_mode: warn`` in their CLAUDE.md frontmatter.
    """
    book_root = _find_book_root(file_path)
    if book_root is None:
        return DEFAULT_MODE
    claudemd = book_root / "CLAUDE.md"
    if not claudemd.is_file():
        return DEFAULT_MODE
    try:
        text = claudemd.read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_MODE
    fm = _FRONTMATTER_RE.match(text)
    if not fm:
        return DEFAULT_MODE
    m = _LINTER_MODE_RE.search(fm.group("body"))
    if not m:
        return DEFAULT_MODE
    value = m.group("value").lower()
    return value if value in VALID_MODES else DEFAULT_MODE


# ---------------------------------------------------------------------------
# Banned-phrase scan (book CLAUDE.md ## Rules)
# ---------------------------------------------------------------------------

# Hook-local extractor: ONLY backtick-wrapped strings count as hard-block
# patterns. The post-draft ``manuscript-checker`` uses a looser parser that
# also picks up ban-cued double-quoted phrases — that's tolerable for soft
# warnings but produces too many false positives when used as a write block.
# Backticks are the markdown convention for "this is a pattern reference",
# so requiring them keeps the user/skill in explicit territory.

_BACKTICK_PATTERN_RE = re.compile(r"`([^`\n]+)`")
_REGEX_HINT_CHARS = set("|()[]\\^$?+*{}")


def _extract_block_patterns_from_rule(
    rule: str,
) -> list[tuple[str, re.Pattern[str]]]:
    """Extract hard-block patterns from a single rule body.

    Only backtick-wrapped strings are returned. Whitespace inside the
    backticks is preserved so the user can encode word-boundary intent
    (e.g. `` ` thing ` ``). If the inner string contains regex
    metacharacters it is compiled as a regex; otherwise as a literal
    substring. Malformed regexes are skipped silently.
    """
    patterns: list[tuple[str, re.Pattern[str]]] = []
    seen: set[str] = set()
    for match in _BACKTICK_PATTERN_RE.finditer(rule):
        raw = match.group(1)
        inner = raw.strip()
        if len(inner) < 2:
            continue
        key = raw.lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            if any(c in _REGEX_HINT_CHARS for c in inner):
                compiled = re.compile(raw, re.IGNORECASE)
            else:
                compiled = re.compile(re.escape(raw), re.IGNORECASE)
        except re.error:
            continue
        patterns.append((inner, compiled))
    return patterns


# Matches "max N per chapter", "maximum N per chapter", "max N-M per chapter"
# (range — upper bound is taken), "limit to N per chapter". Numeric value
# applies per chapter; a per-scene limit is then derived by scaling against
# the chapter's word-count target (see ``_scan_book_banlist``).
_CHAPTER_LIMIT_RE = re.compile(
    r"\b(?:max(?:imum)?|limit\s+to)\s+(?:of\s+)?"
    r"(?P<low>\d+)(?:\s*[-–]\s*(?P<high>\d+))?"
    r"\s+per\s+(?:chapter|kapitel)\b",
    re.IGNORECASE,
)


def _extract_chapter_limit(rule: str) -> int:
    """Parse ``max N per chapter`` / ``max N-M per chapter`` from a rule body.

    Returns the integer limit (upper bound for ranges), or ``0`` when the
    rule does not declare a per-chapter cap. ``0`` means "block on first
    hit" — the existing default behavior.
    """
    match = _CHAPTER_LIMIT_RE.search(rule)
    if not match:
        return 0
    upper = match.group("high") or match.group("low")
    try:
        return int(upper)
    except ValueError:
        return 0


def _book_banned_patterns(
    book_root: Path,
) -> list[tuple[str, re.Pattern[str], int]]:
    """Return ``(label, compiled_regex, chapter_limit)`` patterns.

    ``chapter_limit`` is ``0`` when the source rule has no
    ``max N per chapter`` declaration (block on first hit). When > 0 the
    scanner applies a scaled per-scene limit instead (see
    ``_scan_book_banlist``).
    """
    try:
        from tools.analysis.manuscript_checker import _read_book_rules
    except Exception:
        return []

    rules = _read_book_rules(book_root)
    patterns: list[tuple[str, re.Pattern[str], int]] = []
    seen: set[str] = set()
    for rule in rules:
        limit = _extract_chapter_limit(rule)
        for label, compiled in _extract_block_patterns_from_rule(rule):
            key = compiled.pattern.lower()
            if key in seen:
                continue
            seen.add(key)
            patterns.append((label, compiled, limit))
    return patterns


# ---------------------------------------------------------------------------
# Chapter target word-count (for per-scene limit scaling)
# ---------------------------------------------------------------------------

# Matches a "Target Words" cell in the chapter README's overview table.
# Examples it accepts: "| Target Words | ~3,200 |", "| Target Words | 2500 |"
_TARGET_WORDS_RE = re.compile(
    r"\|\s*Target\s+Words?\s*\|\s*~?\s*"
    r"(?P<value>\d{1,3}(?:[,\.]\d{3})*|\d+)\s*\|",
    re.IGNORECASE,
)

# Used when no chapter README or no parseable target is available. Picked to
# match the typical scene-by-scene chapter size users have been writing.
DEFAULT_CHAPTER_TARGET_WORDS = 3000


def _chapter_target_words(draft_path: Path) -> int:
    """Return the chapter's target word count.

    Looks at ``README.md`` next to the draft, parses the
    "Target Words" overview cell, and returns the integer. Falls back to
    ``DEFAULT_CHAPTER_TARGET_WORDS`` if the README is missing or has no
    parseable target.
    """
    readme = draft_path.parent / "README.md"
    if not readme.is_file():
        return DEFAULT_CHAPTER_TARGET_WORDS
    try:
        text = readme.read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_CHAPTER_TARGET_WORDS
    match = _TARGET_WORDS_RE.search(text)
    if not match:
        return DEFAULT_CHAPTER_TARGET_WORDS
    raw = match.group("value").replace(",", "").replace(".", "")
    try:
        target = int(raw)
    except ValueError:
        return DEFAULT_CHAPTER_TARGET_WORDS
    return target if target > 0 else DEFAULT_CHAPTER_TARGET_WORDS


def _scaled_scene_limit(
    chapter_limit: int, current_words: int, target_words: int
) -> int:
    """Compute per-scene limit from a per-chapter cap, prorated by progress.

    A 900-word draft toward a 3200-word chapter target is "about a third
    of the way through", so the scene budget is one third of the chapter
    cap (rounded up, floored at 1, never exceeding the chapter cap — going
    over the word target should not unlock more banned-phrase budget).
    """
    if chapter_limit <= 0:
        return 0
    if target_words <= 0:
        return chapter_limit
    ratio = current_words / target_words
    return max(1, min(chapter_limit, math.ceil(chapter_limit * ratio)))


# ---------------------------------------------------------------------------
# Meta-narrative scan (script-reviewer language leaking into prose)
# ---------------------------------------------------------------------------

# Phrases that name the manuscript's *structure* instead of doing the work.
# Belong in review notes, not in the prose. Each entry is
# ``(compiled_pattern, short_label, fix_suggestion)``. Patterns are
# applied to prose outside HTML comments only — outline scaffolding inside
# ``<!-- ... -->`` blocks is fair game for structural language.
#
# Deliberately conservative: tokens like ``beat``, ``set piece``, and bare
# ``parallels`` are excluded because they have too many legitimate uses
# in prose (a heart beat, a music beat, parallels of latitude). They need
# narration-vs-dialog awareness that this hook does not have.
META_NARRATIVE_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(r"\bCh\.?\s*\d+\b"),
        "chapter reference",
        "name the event or character instead of pointing to the chapter number",
    ),
    (
        re.compile(r"\bcallbacks?\b", re.IGNORECASE),
        "callback",
        "let the recurrence land without naming it as a callback",
    ),
    (
        re.compile(r"\bas\s+established\b", re.IGNORECASE),
        "as established",
        "trust the reader to remember without flagging it",
    ),
    (
        re.compile(r"\becho(?:es|ed)?\s+the\s+earlier\b", re.IGNORECASE),
        "echoes the earlier",
        "let the parallel work without narrating that it echoes",
    ),
    (
        re.compile(r"\bforeshadow(?:ing|ed|s)?\b", re.IGNORECASE),
        "foreshadow",
        "show the seed; do not name what it foreshadows",
    ),
    (
        re.compile(r"\bcalls?\s+back\s+to\b", re.IGNORECASE),
        "calls back to",
        "the callback should land on its own, not be announced",
    ),
    (
        re.compile(
            r"\b(?:parallels?|mirrors?)\s+(?:the|his|her|their)\s+(?:earlier|previous)\b",
            re.IGNORECASE,
        ),
        "parallels/mirrors the earlier",
        "let the parallel work without narration",
    ),
)


def _comment_spans(text: str) -> list[tuple[int, int]]:
    """Return ``(start, end)`` offsets of every ``<!-- ... -->`` block.

    HTML comments may span multiple lines and are excluded from the
    meta-narrative scan because they typically hold outline scaffolding
    where structural language is expected.
    """
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"<!--.*?-->", text, flags=re.DOTALL):
        spans.append((match.start(), match.end()))
    return spans


def _offset_in_spans(offset: int, spans: list[tuple[int, int]]) -> bool:
    for start, end in spans:
        if start <= offset < end:
            return True
        if start > offset:
            break
    return False


def _scan_meta_narrative(text: str) -> list[Finding]:
    """Block script-reviewer language that has leaked into the prose.

    Each match emits a ``block``-severity finding with line number and a
    short fix suggestion. Matches inside HTML comments are ignored.
    """
    findings: list[Finding] = []
    spans = _comment_spans(text)
    seen_offsets: set[int] = set()
    for pattern, label, suggestion in META_NARRATIVE_PATTERNS:
        for match in pattern.finditer(text):
            offset = match.start()
            if _offset_in_spans(offset, spans):
                continue
            if offset in seen_offsets:
                continue
            seen_offsets.add(offset)
            line_num = _line_for_offset(text, offset)
            snippet = match.group(0)
            findings.append(
                Finding(
                    severity=SEVERITY_BLOCK,
                    category="meta_narrative",
                    message=(
                        f"meta-narrative phrase '{snippet}' ({label}) — "
                        f"{suggestion}"
                    ),
                    line=line_num,
                )
            )
    return findings


def _line_for_offset(text: str, offset: int) -> int:
    return text[:offset].count("\n") + 1


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _scan_ai_tells(text: str) -> list[Finding]:
    """Warn-severity scan against the curated global AI-tell vocabulary.

    Source: ``reference/craft/anti-ai-patterns.md`` via
    ``tools.banlist_loader.load_global_ai_tells``. Falls back to the
    local ``_AI_TELL_FALLBACK`` list if the loader cannot read the file.
    """
    findings: list[Finding] = []
    try:
        from tools.banlist_loader import load_global_ai_tells

        patterns = load_global_ai_tells(PLUGIN_ROOT)
    except Exception:
        patterns = []

    if patterns:
        for banned in patterns:
            matches = list(banned.pattern.finditer(text))
            if not matches:
                continue
            line_num = _line_for_offset(text, matches[0].start())
            suffix = "s" if len(matches) > 1 else ""
            findings.append(
                Finding(
                    severity=SEVERITY_WARN,
                    category="ai_tell",
                    message=(
                        f"AI-tell '{banned.label}' found "
                        f"({len(matches)} occurrence{suffix})"
                    ),
                    line=line_num,
                )
            )
        return findings

    # Fallback path — loader failed or file missing.
    text_lower = text.lower()
    for word in _AI_TELL_FALLBACK:
        pattern = rf"\b{re.escape(word)}\b"
        matches = list(re.finditer(pattern, text_lower))
        if not matches:
            continue
        line_num = _line_for_offset(text, matches[0].start())
        suffix = "s" if len(matches) > 1 else ""
        findings.append(
            Finding(
                severity=SEVERITY_WARN,
                category="ai_tell",
                message=(
                    f"AI-tell word '{word}' found ({len(matches)} occurrence{suffix})"
                ),
                line=line_num,
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Story-time anchor scan (relative phrases vs. chapter timeline)
# ---------------------------------------------------------------------------

# Phrases the anchor mapper knows how to resolve. Pattern keeps each
# phrase as its own group so we can match them case-insensitively without
# losing the matched text. Multi-word phrases must come before their
# substrings (``last night`` before ``night``).
_RELATIVE_PHRASE_RE = re.compile(
    r"\b("
    r"yesterday"
    r"|tomorrow"
    r"|tonight"
    r"|last\s+night"
    r"|last\s+week"
    r"|next\s+week"
    r"|this\s+morning"
    r"|this\s+afternoon"
    r"|this\s+evening"
    r"|two\s+hours\s+ago"
    r"|one\s+hour\s+ago"
    r"|an\s+hour\s+ago"
    r")\b",
    re.IGNORECASE,
)


def _scan_time_anchor(text: str, draft_path: Path) -> list[Finding]:
    """Warn when prose uses a relative time phrase, naming the implied
    story-calendar target so the writer can verify against
    ``plot/timeline.md``.

    Severity is ``warn`` — semantic event-vs-timeline matching is out of
    scope for this hook (would need NLP). The annotation alone catches
    most drift cases by giving the writer a concrete date to check
    against. Block-on-conflict can come in a follow-up issue.
    """
    findings: list[Finding] = []
    chapter_dir = draft_path.parent

    try:
        from tools.timeline_anchor import (
            compute_relative_phrase_mapping,
            get_chapter_anchor,
        )
    except Exception:
        return findings

    anchor = get_chapter_anchor(chapter_dir)
    if anchor is None or anchor.start is None:
        return findings

    mapping = compute_relative_phrase_mapping(anchor)
    if not mapping:
        return findings

    seen_offsets: set[int] = set()
    for match in _RELATIVE_PHRASE_RE.finditer(text):
        offset = match.start()
        if offset in seen_offsets:
            continue
        seen_offsets.add(offset)
        # Normalize whitespace inside the matched phrase for lookup.
        phrase = re.sub(r"\s+", " ", match.group(1).lower())
        implied = mapping.get(phrase)
        if implied is None:
            continue
        line_num = _line_for_offset(text, offset)
        findings.append(
            Finding(
                severity=SEVERITY_WARN,
                category="time_anchor",
                message=(
                    f"phrase '{match.group(1)}' implies {implied} "
                    f"(chapter starts {anchor.start.label()}). "
                    f"Verify against plot/timeline.md."
                ),
                line=line_num,
            )
        )
    return findings


def _scan_author_banlist(text: str, book_root: Path) -> list[Finding]:
    """Block-severity scan against the active book's author vocabulary.md.

    Resolves the author from the book's CLAUDE.md ``Book Facts`` section,
    loads ``~/.storyforge/authors/{slug}/vocabulary.md`` via the
    banlist loader, and emits one ``BLOCK`` finding per matched phrase.
    Author-vocab bans express the user's voice intent and are
    non-negotiable.
    """
    try:
        from tools.banlist_loader import author_slug_from_book, load_author_vocab
    except Exception:
        return []

    slug = author_slug_from_book(book_root)
    if not slug:
        return []
    patterns = load_author_vocab(slug)
    if not patterns:
        return []

    findings: list[Finding] = []
    for banned in patterns:
        match = banned.pattern.search(text)
        if not match:
            continue
        line_num = _line_for_offset(text, match.start())
        findings.append(
            Finding(
                severity=SEVERITY_BLOCK,
                category="author_vocab_violation",
                message=(
                    f"Banned by author voice ({banned.source}): "
                    f"'{banned.label}'"
                ),
                line=line_num,
            )
        )
    return findings


def _scan_sentence_variance(text: str) -> list[Finding]:
    prose = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
    prose = re.sub(r"^#+\s+.*$", "", prose, flags=re.MULTILINE)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", prose.strip()) if s.split()]
    if len(sentences) <= 10:
        return []
    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(lengths)
    variance = sum((n - mean) ** 2 for n in lengths) / len(lengths)
    std_dev = variance**0.5
    if std_dev >= 4:
        return []
    return [
        Finding(
            severity=SEVERITY_WARN,
            category="variance",
            message=(
                f"Low sentence length variance (std_dev={std_dev:.1f}) — "
                "text may sound AI-generated. Vary sentence lengths more."
            ),
        )
    ]


def _format_occurrences(
    text: str, matches: list[re.Match[str]], cap: int = 5
) -> str:
    """Format up to ``cap`` match locations as a compact list for stderr."""
    parts: list[str] = []
    for match in matches[:cap]:
        line = _line_for_offset(text, match.start())
        start = max(0, match.start() - 25)
        end = min(len(text), match.end() + 25)
        snippet = text[start:end].replace("\n", " ").strip()
        parts.append(f"line {line}: …{snippet}…")
    if len(matches) > cap:
        parts.append(f"…and {len(matches) - cap} more")
    return "; ".join(parts)


def _scan_book_banlist(
    text: str, book_root: Path, draft_path: Path
) -> list[Finding]:
    """Scan prose against the book's CLAUDE.md banned-phrase patterns.

    Patterns without a per-chapter limit (the default) block on the first
    hit. Patterns whose source rule declares ``max N per chapter`` get a
    scaled per-scene budget instead — a 900-word draft toward a 3200-word
    chapter target gets ``ceil(N * 900/3200)`` allowed hits, floored at 1.
    Only counts above the budget produce a finding.
    """
    findings: list[Finding] = []
    target_words = _chapter_target_words(draft_path)
    current_words = max(len(text.split()), 1)

    for label, compiled, chapter_limit in _book_banned_patterns(book_root):
        matches = list(compiled.finditer(text))
        if not matches:
            continue

        if chapter_limit > 0:
            scene_limit = _scaled_scene_limit(
                chapter_limit, current_words, target_words
            )
            if len(matches) <= scene_limit:
                continue
            line_num = _line_for_offset(text, matches[0].start())
            occurrences = _format_occurrences(text, matches)
            findings.append(
                Finding(
                    severity=SEVERITY_BLOCK,
                    category="book_rule_violation",
                    message=(
                        f"phrase '{label}' appears {len(matches)} times "
                        f"(scaled scene limit: {scene_limit}; chapter cap: "
                        f"{chapter_limit}; current draft: {current_words}w "
                        f"of {target_words}w target). Cut at least "
                        f"{len(matches) - scene_limit}. {occurrences}"
                    ),
                    line=line_num,
                )
            )
        else:
            match = matches[0]
            line_num = _line_for_offset(text, match.start())
            findings.append(
                Finding(
                    severity=SEVERITY_BLOCK,
                    category="book_rule_violation",
                    message=f"Banned phrase from book CLAUDE.md: '{label}'",
                    line=line_num,
                )
            )
    return findings


def validate_chapter(file_path: str) -> list[Finding]:
    """Validate a chapter draft and return findings.

    Returns an empty list when the file is not a chapter draft, is too
    short to evaluate, or does not exist.
    """
    path = Path(file_path)
    if not path.exists():
        return []
    if "/chapters/" not in str(path):
        return []
    if path.name != "draft.md":
        return []

    text = path.read_text(encoding="utf-8")
    if len(text.split()) < 50:
        return []

    findings: list[Finding] = []
    book_root = _find_book_root(path)
    if book_root is not None:
        findings.extend(_scan_book_banlist(text, book_root, path))
        findings.extend(_scan_author_banlist(text, book_root))
    findings.extend(_scan_time_anchor(text, path))
    findings.extend(_scan_meta_narrative(text))
    findings.extend(_scan_ai_tells(text))
    findings.extend(_scan_sentence_variance(text))
    return findings


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _format_finding(finding: Finding, path: Path) -> str:
    location = f" line {finding.line}" if finding.line else ""
    return f"[{finding.severity.upper()}] {path.name}{location}: {finding.message}"


def _emit_block_report(
    path: Path,
    blocking: list[Finding],
    warnings: list[Finding],
    stream: Any,
) -> None:
    print("StoryForge linter blocked this write:", file=stream)
    for finding in blocking:
        print(f"  {_format_finding(finding, path)}", file=stream)
    if warnings:
        suffix = "s" if len(warnings) != 1 else ""
        print(
            f"Plus {len(warnings)} non-blocking warning{suffix}:",
            file=stream,
        )
        for finding in warnings[:5]:
            print(f"  {_format_finding(finding, path)}", file=stream)
    print(
        "Fix the blocking issues and try again. "
        "Set `linter_mode: warn` in the book's CLAUDE.md frontmatter to override.",
        file=stream,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Hook entry point. Returns 0 (continue), or 2 (block + feed stderr to model)."""
    payload = _read_payload()

    file_path: str = ""
    if payload is not None:
        tool_name = payload.get("tool_name")
        if isinstance(tool_name, str) and tool_name not in WATCHED_TOOLS:
            return 0
        file_path = _extract_file_path(payload) or ""
    else:
        # Legacy fallback: positional argv (used by older invocations / tests).
        if len(sys.argv) > 1:
            file_path = sys.argv[1]
        else:
            file_path = os.environ.get("CLAUDE_FILE_PATH", "") or os.environ.get(
                "CLAUDE_TOOL_ARG_FILE_PATH", ""
            )

    if not file_path:
        return 0

    findings = validate_chapter(file_path)
    if not findings:
        return 0

    path = Path(file_path)
    mode = _resolve_mode(path)
    blocking = [f for f in findings if f.severity == SEVERITY_BLOCK]
    warnings = [f for f in findings if f.severity == SEVERITY_WARN]

    if blocking and mode == "strict":
        _emit_block_report(path, blocking, warnings, sys.stderr)
        return 2

    # Warn mode, or no blocking findings: emit non-blocking diagnostics on stdout.
    for finding in findings[:10]:
        print(_format_finding(finding, path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
