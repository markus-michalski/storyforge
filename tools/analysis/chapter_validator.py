"""Chapter draft validator — extracted from ``hooks/validate_chapter.py`` (#119).

The PostToolUse hook delegates to this module so the same validation logic
is available outside the hook context: skills can call it during
draft → review transitions, the MCP layer exposes it as a callable tool,
and unit tests can drive the scanners without forging hook-event JSON.

Public API
----------

``validate_chapter(file_path)``
    Backwards-compatible entry point. Takes a path string, returns a list
    of :class:`Finding` objects. Empty list for non-chapter paths or
    too-short drafts.

``validate_chapter_path(file_path)``
    Higher-level entry point used by the MCP tool. Returns a
    :class:`ValidationResult` with the resolved ``mode`` (strict/warn),
    blocking/warning splits, and a ``GateResult``-shaped envelope.

``Finding``, ``ValidationResult``
    Plain dataclasses, JSON-serializable through ``to_json_dict``.

Severity constants ``SEVERITY_BLOCK`` and ``SEVERITY_WARN`` along with
``DEFAULT_MODE`` and ``VALID_MODES`` are exported for the hook shim and
tests that build expectations against them.
"""

from __future__ import annotations

import math
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(
    os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent.parent))
)

# Make tools package importable when this module is loaded standalone
# (covers hook invocation and test harnesses).
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))


from tools.shared.gate_result import Finding as GateFinding, GateResult


# ---------------------------------------------------------------------------
# Severity vocabulary
# ---------------------------------------------------------------------------

SEVERITY_BLOCK = "block"
SEVERITY_WARN = "warn"

VALID_MODES = ("strict", "warn")
DEFAULT_MODE = "strict"

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


# ---------------------------------------------------------------------------
# Findings + result envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    message: str
    line: int | None = None

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
        }
        if self.line is not None:
            out["line"] = self.line
        return out


@dataclass
class ValidationResult:
    file_path: str
    mode: str = DEFAULT_MODE
    findings: list[Finding] = field(default_factory=list)

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_BLOCK]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_WARN]

    @property
    def will_block(self) -> bool:
        """Whether the hook would reject the write in the resolved mode."""
        return self.mode == "strict" and bool(self.blocking)

    def to_gate(self) -> GateResult:
        """Translate the result into the uniform GateResult contract.

        - ``FAIL``  — blocking finding(s) AND the resolved mode is strict.
        - ``WARN``  — any finding present, but the hook would not block
          (warn mode, or warn-only findings).
        - ``PASS``  — no findings.
        """
        gate_findings: list[GateFinding] = []
        for f in self.findings:
            severity = "FAIL" if f.severity == SEVERITY_BLOCK else "WARN"
            gate_findings.append(
                GateFinding(
                    code=f.category.upper(),
                    message=f.message,
                    severity=severity,  # type: ignore[arg-type]
                    location={"file": self.file_path, "line": f.line} if f.line else {"file": self.file_path},
                )
            )

        metadata = {
            "file_path": self.file_path,
            "mode": self.mode,
            "blocking_count": len(self.blocking),
            "warning_count": len(self.warnings),
        }

        if self.will_block:
            return GateResult.failed(
                reasons=[f"{len(self.blocking)} blocking finding(s) in strict mode."],
                findings=gate_findings,
                metadata=metadata,
            )
        if self.findings:
            note = "warn mode — blocking findings demoted." if self.blocking else "warn-severity findings only."
            return GateResult.warned(
                reasons=[note],
                findings=gate_findings,
                metadata=metadata,
            )
        return GateResult.passed(
            reasons=["No findings."],
            metadata=metadata,
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "mode": self.mode,
            "findings": [f.to_json_dict() for f in self.findings],
            "blocking_count": len(self.blocking),
            "warning_count": len(self.warnings),
            "gate": self.to_gate().to_json_dict(),
        }

    def render_block_report(self, *, warning_cap: int = 5) -> str:
        """Render the strict-mode block report — the message the hook prints
        on stderr and the model sees when the write is rejected.
        """
        path = Path(self.file_path)
        lines: list[str] = ["StoryForge linter blocked this write:"]
        for f in self.blocking:
            location = f" line {f.line}" if f.line else ""
            lines.append(f"  [{f.severity.upper()}] {path.name}{location}: {f.message}")
        if self.warnings:
            suffix = "s" if len(self.warnings) != 1 else ""
            lines.append(f"Plus {len(self.warnings)} non-blocking warning{suffix}:")
            for f in self.warnings[:warning_cap]:
                location = f" line {f.line}" if f.line else ""
                lines.append(
                    f"  [{f.severity.upper()}] {path.name}{location}: {f.message}"
                )
        lines.append(
            "Fix the blocking issues and try again. "
            "Set `linter_mode: warn` in the book's CLAUDE.md frontmatter to override."
        )
        return "\n".join(lines)

    def render_diagnostics(self, *, cap: int = 10) -> list[str]:
        """Render up to ``cap`` non-blocking diagnostic lines for stdout."""
        path = Path(self.file_path)
        out: list[str] = []
        for f in self.findings[:cap]:
            location = f" line {f.line}" if f.line else ""
            out.append(f"[{f.severity.upper()}] {path.name}{location}: {f.message}")
        return out


# ---------------------------------------------------------------------------
# Mode resolution (strict vs warn)
# ---------------------------------------------------------------------------


def find_book_root(file_path: Path) -> Path | None:
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


def resolve_mode(file_path: Path) -> str:
    """Resolve linter mode for the given draft path.

    Default is ``strict``. Books opt into ``warn`` by setting
    ``linter_mode: warn`` in their CLAUDE.md frontmatter.
    """
    book_root = find_book_root(file_path)
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

_TARGET_WORDS_RE = re.compile(
    r"\|\s*Target\s+Words?\s*\|\s*~?\s*"
    r"(?P<value>\d{1,3}(?:[,\.]\d{3})*|\d+)\s*\|",
    re.IGNORECASE,
)

DEFAULT_CHAPTER_TARGET_WORDS = 3000


def _chapter_target_words(draft_path: Path) -> int:
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
    if chapter_limit <= 0:
        return 0
    if target_words <= 0:
        return chapter_limit
    ratio = current_words / target_words
    return max(1, min(chapter_limit, math.ceil(chapter_limit * ratio)))


# ---------------------------------------------------------------------------
# Meta-narrative scan (script-reviewer language leaking into prose)
# ---------------------------------------------------------------------------

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


def _line_for_offset(text: str, offset: int) -> int:
    return text[:offset].count("\n") + 1


def _scan_meta_narrative(text: str) -> list[Finding]:
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


# ---------------------------------------------------------------------------
# AI-tells, time anchors, POV boundary, author banlist, sentence variance
# ---------------------------------------------------------------------------


def _scan_ai_tells(text: str) -> list[Finding]:
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


def _scan_pov_boundary(
    text: str, draft_path: Path, book_root: Path,
) -> list[Finding]:
    findings: list[Finding] = []
    try:
        from tools.analysis.pov_boundary_checker import (
            load_domain_vocabularies,
            parse_character_knowledge,
            scan_pov_boundary,
        )
        from tools.shared.paths import slugify
        from tools.state.parsers import parse_chapter_readme
    except Exception:
        return findings

    chapter_dir = draft_path.parent
    chapter_readme = chapter_dir / "README.md"
    if not chapter_readme.is_file():
        return findings
    try:
        meta = parse_chapter_readme(chapter_readme)
    except Exception:
        return findings
    pov_name = (meta.get("pov_character") or "").strip()
    if not pov_name:
        return findings

    pov_slug = slugify(pov_name)
    char_file = book_root / "characters" / f"{pov_slug}.md"
    pov_knowledge = parse_character_knowledge(char_file)
    if pov_knowledge is None or not pov_knowledge.has_knowledge_data:
        return findings

    domain_dir = PLUGIN_ROOT / "reference" / "craft" / "knowledge-domains"
    domain_vocab = load_domain_vocabularies(domain_dir)
    if not domain_vocab:
        return findings

    for hit in scan_pov_boundary(text, pov_knowledge, domain_vocab):
        findings.append(Finding(
            severity=SEVERITY_WARN,
            category="pov_boundary",
            message=(
                f"POV BOUNDARY: '{hit.phrase}' (domain: {hit.domain}, "
                f"{pov_knowledge.name} knowledge: {hit.knowledge_level}). "
                "Move into dialog by an expert, reframe as lay observation, "
                "or cut."
            ),
            line=hit.line,
        ))
    return findings


def _scan_author_banlist(text: str, book_root: Path) -> list[Finding]:
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_chapter(file_path: str) -> list[Finding]:
    """Validate a chapter draft and return findings.

    Returns an empty list when the file is not a chapter draft, is too
    short to evaluate, or does not exist. Backwards-compatible with the
    pre-#119 hook entry point — same return shape, same gating rules.
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
    book_root = find_book_root(path)
    if book_root is not None:
        findings.extend(_scan_book_banlist(text, book_root, path))
        findings.extend(_scan_author_banlist(text, book_root))
        findings.extend(_scan_pov_boundary(text, path, book_root))
    findings.extend(_scan_time_anchor(text, path))
    findings.extend(_scan_meta_narrative(text))
    findings.extend(_scan_ai_tells(text))
    findings.extend(_scan_sentence_variance(text))
    return findings


def validate_chapter_path(file_path: str) -> ValidationResult:
    """High-level validator returning a :class:`ValidationResult`.

    Resolves the linter mode for the chapter's book and packages the
    findings with mode + counts. The MCP tool layer wraps this and emits
    the gate envelope through ``ValidationResult.to_gate``.
    """
    path = Path(file_path)
    findings = validate_chapter(file_path)
    mode = resolve_mode(path) if path.exists() else DEFAULT_MODE
    return ValidationResult(file_path=str(path), mode=mode, findings=findings)


__all__ = [
    "DEFAULT_CHAPTER_TARGET_WORDS",
    "DEFAULT_MODE",
    "Finding",
    "META_NARRATIVE_PATTERNS",
    "SEVERITY_BLOCK",
    "SEVERITY_WARN",
    "VALID_MODES",
    "ValidationResult",
    "find_book_root",
    "resolve_mode",
    "validate_chapter",
    "validate_chapter_path",
]
