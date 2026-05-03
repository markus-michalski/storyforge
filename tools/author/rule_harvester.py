"""Harvest buchspezifische Findings → Autorenprofil-Kandidaten (Issue #151).

Two-layer design:

- **Pure layer** (this module): takes pre-loaded rules, findings, author state,
  and returns structured candidate lists. Side-effect-free, fully unit-testable.
- **Composition layer**: the ``harvest_book_rules`` MCP tool reads files from
  disk and calls this module. Lives in ``routers/authors.py``.

A *candidate* is a buchspezifisches Finding that *might* belong to the author
profile instead of the book CLAUDE.md. The harvester emits a recommendation
(``promote`` / ``keep_book_only`` / ``discuss``) — the actual decision happens
in the skill, where the user walks each candidate.

Three classification buckets:

- ``banned_phrase`` — single-word/short-phrase ban → ``vocabulary.md``
- ``style_principle`` — pattern, regex, or prose-rule → ``profile.md`` Writing
  Discoveries
- ``world_rule`` — magic-system / canon term → keeps book scope (no promotion)

The classifier inspects:

- ``ParsedRule.has_regex`` — regex shape always denotes structural pattern
- ``extracted_patterns`` — short literal labels denote phrase bans, longer or
  template-shaped labels denote structural patterns
- ``world_terms`` set — magic-system, glossary, character names; passed in by
  the composition layer so the pure layer stays decoupled from disk I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from tools.analysis.manuscript.types import Finding
from tools.claudemd.rules_editor import ParsedRule

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

CANDIDATE_TYPES: tuple[str, ...] = ("banned_phrase", "style_principle", "world_rule")
RECOMMENDATIONS: tuple[str, ...] = ("promote", "keep_book_only", "discuss")
TARGET_SECTIONS: tuple[str, ...] = ("vocabulary", "recurring_tics", "style_principles", "donts")

# Default thresholds for manuscript-finding promotion. A finding promotes only
# when it occurs in at least this many distinct chapters AND its severity is
# ``high``. Tuneable via ``collect_manuscript_candidates`` parameters.
DEFAULT_CHAPTER_THRESHOLD = 3
DEFAULT_SEVERITY_FLOOR = "high"


@dataclass
class Candidate:
    """One promotion candidate. Maps 1:1 to the issue's spec'd JSON shape."""

    id: str
    type: str  # banned_phrase | style_principle | world_rule
    value: str  # the phrase or rule body
    context: str
    evidence: str
    recommendation: str  # promote | keep_book_only | discuss
    rationale: str
    source: str  # book_rule | manuscript_finding
    target_section: str | None  # vocabulary | recurring_tics | style_principles | donts | None
    source_rule_index: int | None = None  # only for source == "book_rule"
    occurrences: list[dict[str, Any]] = field(default_factory=list)  # for manuscript findings

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "value": self.value,
            "context": self.context,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "rationale": self.rationale,
            "source": self.source,
            "target_section": self.target_section,
            "source_rule_index": self.source_rule_index,
            "occurrences": self.occurrences,
        }


# ---------------------------------------------------------------------------
# Rule classifier — book CLAUDE.md
# ---------------------------------------------------------------------------

# Template slots (e.g. "[Character]", "[location]") signal a structural pattern.
_TEMPLATE_SLOT_RE = re.compile(r"\[[A-Za-z][A-Za-z\s\-_]*\]")

# A literal pattern is "phrase-shaped" (single banned phrase) when it is short
# (≤3 tokens) AND contains no template slots AND is not regex. Anything else
# is structural.
_PHRASE_TOKEN_LIMIT = 3


def classify_rule(rule: ParsedRule, *, world_terms: set[str]) -> tuple[str, str | None]:
    """Classify a book CLAUDE.md rule into ``(type, target_section)``.

    Returns ``("world_rule", None)`` for canon/magic-system terms.
    Otherwise returns one of ``banned_phrase``/``style_principle`` plus the
    matching target section (``vocabulary`` or ``recurring_tics`` /
    ``style_principles``).
    """
    if _matches_world_term(rule.raw_text, world_terms):
        return "world_rule", None

    # Regex shape always denotes structural pattern.
    if rule.has_regex:
        return "style_principle", "recurring_tics"

    # Inspect literal patterns. Short single-word/short-phrase literals →
    # banned_phrase. Template slots, multi-word literals, or no literals at
    # all → style_principle.
    literal_labels = [p["label"] for p in rule.extracted_patterns if not p.get("is_regex")]
    if not literal_labels:
        # Pure prose rule (no extractable pattern). Treat as style_principle
        # under the looser "Style Principles" bucket — these are positive
        # craft heuristics, not recurring tics.
        return "style_principle", "style_principles"

    short_phrase_only = all(
        not _TEMPLATE_SLOT_RE.search(label) and len(label.split()) <= _PHRASE_TOKEN_LIMIT
        for label in literal_labels
    )
    if short_phrase_only:
        return "banned_phrase", "vocabulary"

    return "style_principle", "recurring_tics"


def _matches_world_term(text: str, world_terms: set[str]) -> bool:
    """Case-insensitive substring check against canon/glossary terms."""
    if not world_terms:
        return False
    lower = text.lower()
    return any(term.lower() in lower for term in world_terms if term.strip())


# ---------------------------------------------------------------------------
# Finding classifier — manuscript scanner
# ---------------------------------------------------------------------------

# Manuscript Finding categories (from tools.analysis.manuscript.types) map
# directly onto our buckets. ``signature_phrase`` and ``simile`` are phrase
# bans; ``blocking_tic`` / ``structural`` / ``character_tell`` / ``sensory``
# are recurring structural tics.
_FINDING_CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "signature_phrase": ("banned_phrase", "vocabulary"),
    "simile": ("banned_phrase", "vocabulary"),
    "blocking_tic": ("style_principle", "recurring_tics"),
    "structural": ("style_principle", "recurring_tics"),
    "character_tell": ("style_principle", "recurring_tics"),
    "sensory": ("style_principle", "recurring_tics"),
    "book_rule_violation": ("banned_phrase", "vocabulary"),
}


def classify_finding(finding: Finding) -> tuple[str, str]:
    """Classify a manuscript Finding into ``(type, target_section)``.

    Unknown categories default to ``("banned_phrase", "vocabulary")`` because
    that is the conservative fallback — the user can always re-classify in
    the skill walk.
    """
    return _FINDING_CATEGORY_MAP.get(finding.category, ("banned_phrase", "vocabulary"))


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------


def collect_book_rule_candidates(
    parsed_rules: list[ParsedRule],
    *,
    world_terms: set[str],
) -> list[Candidate]:
    """Walk book CLAUDE.md rules and emit one Candidate per rule."""
    candidates: list[Candidate] = []
    for rule in parsed_rules:
        kind, target = classify_rule(rule, world_terms=world_terms)
        if kind == "world_rule":
            recommendation = "keep_book_only"
            rationale = "Worldbuilding-specific term — not transferable across books."
        else:
            recommendation = "promote"
            rationale = _rule_rationale(kind)
        candidates.append(
            Candidate(
                id=f"rule-{rule.index:03d}",
                type=kind,
                value=_extract_rule_value(rule),
                context=f"From book CLAUDE.md ## Rules — {rule.title}",
                evidence=f"Book rule index {rule.index}",
                recommendation=recommendation,
                rationale=rationale,
                source="book_rule",
                target_section=target,
                source_rule_index=rule.index,
            )
        )
    return candidates


def _extract_rule_value(rule: ParsedRule) -> str:
    """Pick the most descriptive value for display.

    Prefer the first literal label (the phrase to ban). Fall back to the
    rule title or the raw text.
    """
    for pattern in rule.extracted_patterns:
        if not pattern.get("is_regex") and pattern.get("label"):
            return pattern["label"]
    if rule.title and rule.title != "rule":
        return rule.title
    # Strip leading "Avoid `...`" framing if present so the value is readable.
    cleaned = re.sub(r"^(?:Avoid|Never|Do not use|Limit|Stop using)\s+", "", rule.raw_text, flags=re.IGNORECASE)
    return cleaned.strip()


def _rule_rationale(kind: str) -> str:
    if kind == "banned_phrase":
        return "Short literal phrase ban — typical author-vocabulary entry."
    return "Structural / pattern rule — recurring author habit, not book-specific."


def collect_manuscript_candidates(
    findings: list[Finding],
    *,
    threshold_chapters: int = DEFAULT_CHAPTER_THRESHOLD,
    severity_floor: str = DEFAULT_SEVERITY_FLOOR,
) -> list[Candidate]:
    """Emit candidates from manuscript-checker findings.

    A finding is promotable when it occurs in at least ``threshold_chapters``
    distinct chapters AND its severity matches ``severity_floor``. The
    rationale is the cross-chapter spread, which marks the pattern as an
    author-level tic rather than a one-chapter blip.
    """
    candidates: list[Candidate] = []
    for idx, finding in enumerate(findings):
        if finding.severity != severity_floor:
            continue
        chapter_count = len({occ.chapter for occ in finding.occurrences})
        if chapter_count < threshold_chapters:
            continue
        kind, target = classify_finding(finding)
        candidates.append(
            Candidate(
                id=f"finding-{idx:03d}",
                type=kind,
                value=finding.phrase,
                context=f"Manuscript-checker finding ({finding.category})",
                evidence=(
                    f"Flagged {finding.count}x across {chapter_count} chapters "
                    f"(severity={finding.severity})"
                ),
                recommendation="promote",
                rationale="Cross-chapter spread suggests an author tic, not a one-chapter blip.",
                source="manuscript_finding",
                target_section=target,
                source_rule_index=None,
                occurrences=[
                    {"chapter": occ.chapter, "line": occ.line, "snippet": occ.snippet}
                    for occ in finding.occurrences
                ],
            )
        )
    return candidates


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------


def deduplicate_against_author(
    candidates: list[Candidate],
    *,
    vocabulary_text: str,
    author_profile: dict[str, Any] | None,
) -> list[Candidate]:
    """Drop candidates that already exist in the author profile.

    Vocabulary phrases are matched case-insensitively as substrings.
    Discoveries are matched against the appropriate sub-section
    (``recurring_tics`` / ``style_principles`` / ``donts``) by keyword
    overlap — a candidate is considered duplicate when its value's tokens
    are a subset of an existing entry's tokens (after stop-word removal).
    """
    if author_profile is None:
        author_profile = {"writing_discoveries": {}}

    discoveries = (author_profile or {}).get("writing_discoveries") or {}
    vocab_lower = vocabulary_text.lower() if vocabulary_text else ""

    kept: list[Candidate] = []
    for cand in candidates:
        if cand.type == "banned_phrase":
            if vocab_lower and cand.value.lower() in vocab_lower:
                continue
        elif cand.target_section in {"recurring_tics", "style_principles", "donts"}:
            if _value_already_in_discoveries(cand.value, discoveries.get(cand.target_section, [])):
                continue
        kept.append(cand)
    return kept


_STOP_WORDS_FOR_DEDUP = {
    "a", "an", "and", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on",
    "or", "the", "to", "with", "—",
}


def _value_already_in_discoveries(value: str, entries: list[dict[str, Any]]) -> bool:
    cand_tokens = _normalize_tokens(value)
    if not cand_tokens:
        return False
    for entry in entries:
        existing_tokens = _normalize_tokens(entry.get("text", ""))
        if not existing_tokens:
            continue
        # Subset in either direction → treat as duplicate. Captures both
        # "info-dumps in dialog" matching "Avoid info-dumps" and the reverse.
        if cand_tokens.issubset(existing_tokens) or existing_tokens.issubset(cand_tokens):
            return True
    return False


def _normalize_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", text.lower())
    return {t for t in tokens if t not in _STOP_WORDS_FOR_DEDUP}


# ---------------------------------------------------------------------------
# Orchestration — pure
# ---------------------------------------------------------------------------


def harvest(
    *,
    book_slug: str,
    author_slug: str | None,
    parsed_rules: list[ParsedRule],
    findings: list[Finding] | None,
    author_profile: dict[str, Any] | None,
    vocabulary_text: str,
    world_terms: set[str],
    threshold_chapters: int = DEFAULT_CHAPTER_THRESHOLD,
    severity_floor: str = DEFAULT_SEVERITY_FLOOR,
) -> dict[str, Any]:
    """Compose all collectors + dedup. Returns the issue-spec'd JSON shape.

    Side-effect-free; the composition layer (MCP tool) is responsible for
    loading rules, findings, profile, vocabulary, and world terms from disk
    and passing them in here.
    """
    rule_candidates = collect_book_rule_candidates(parsed_rules, world_terms=world_terms)
    manuscript_candidates = collect_manuscript_candidates(
        findings or [],
        threshold_chapters=threshold_chapters,
        severity_floor=severity_floor,
    )
    all_candidates = rule_candidates + manuscript_candidates
    kept = deduplicate_against_author(
        all_candidates,
        vocabulary_text=vocabulary_text,
        author_profile=author_profile,
    )

    summary = {
        "total": len(kept),
        "recommended_promote": sum(1 for c in kept if c.recommendation == "promote"),
        "recommended_keep_book": sum(1 for c in kept if c.recommendation == "keep_book_only"),
        "recommended_discuss": sum(1 for c in kept if c.recommendation == "discuss"),
    }

    return {
        "book_slug": book_slug,
        "author_slug": author_slug,
        "candidates": [c.to_json() for c in kept],
        "summary": summary,
    }


__all__ = [
    "Candidate",
    "CANDIDATE_TYPES",
    "RECOMMENDATIONS",
    "TARGET_SECTIONS",
    "DEFAULT_CHAPTER_THRESHOLD",
    "DEFAULT_SEVERITY_FLOOR",
    "classify_rule",
    "classify_finding",
    "collect_book_rule_candidates",
    "collect_manuscript_candidates",
    "deduplicate_against_author",
    "harvest",
]
