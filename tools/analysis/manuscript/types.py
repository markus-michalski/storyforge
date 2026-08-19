"""Dataclasses + classifier for the manuscript checker.

Splits the small data + classification surface out of the orchestrator so
unit tests can drive the classifier without spinning up the whole scanner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from tools.analysis.manuscript.vocabularies import (
    BLOCKING_VERBS,
    BODY_PARTS,
    SENSORY_TOKENS,
    STRUCTURAL_HINTS,
)


@dataclass
class Occurrence:
    """A single occurrence of a repeated phrase in the manuscript."""

    chapter: str
    line: int
    snippet: str  # ~120 chars of surrounding context, with the phrase intact


@dataclass
class Finding:
    """A repeated phrase with all its occurrences and a category guess."""

    phrase: str
    category: str
    severity: str  # "high" | "medium"
    count: int
    occurrences: list[Occurrence] = field(default_factory=list)
    # Populated only for category == "book_rule_violation": the verbatim rule
    # from the book's CLAUDE.md that triggered the finding, so the user sees
    # *why* a phrase was flagged.
    source_rule: str | None = None
    # False for findings whose ``phrase`` is a synthetic label rather than
    # manuscript text (e.g. body_tells.py's "shoulder (varied phrasing)") —
    # tells tools.author.rule_harvester not to promote it into an
    # author-level scan pattern that could never match anything (#511).
    promotable: bool = True
    # True when category == "book_rule_violation" and the source rule's own
    # text documents a quality exception (e.g. "only when X does real
    # character work") — the regex match can't tell whether this specific
    # occurrence satisfies that exception, so the gate treats it as WARN
    # rather than a hard FAIL (Issue #608).
    has_quality_exception: bool = False


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

# Compiled patterns for category detection on the original (non-normalised)
# context snippet, so we can spot punctuation cues like "Closed it." or
# quotation marks.
_SIMILE_HINT_RE = re.compile(r"\b(like|as if|as though)\b", re.IGNORECASE)
_AS_X_AS_RE = re.compile(r"\bas\s+\w+\s+as\b", re.IGNORECASE)
_BLOCKING_PUNCT_RE = re.compile(r"\.\s+\w+(ed|s)?\s+(it|him|her|them)\.")


def _classify(phrase: str, occurrences: list[Occurrence]) -> str:
    """Pick the best category for a repeated phrase."""
    tokens = phrase.split()
    token_set = set(tokens)
    contexts = " ".join(o.snippet for o in occurrences)

    # Similes first — they're the most distinctive.
    if "like" in token_set or "as" in token_set:
        if _SIMILE_HINT_RE.search(contexts) or _AS_X_AS_RE.search(contexts) or "like" in tokens[:2]:
            return "simile"

    # Blocking tic: physical micro-action between dialog beats.
    if token_set & BLOCKING_VERBS:
        if _BLOCKING_PUNCT_RE.search(contexts) or any(t in token_set for t in ("opened", "closed", "shut")):
            return "blocking_tic"

    # Character tell: repeated body-part description.
    if token_set & BODY_PARTS:
        return "character_tell"

    # Sensory repetition: same smell/taste/sound description.
    if token_set & SENSORY_TOKENS:
        return "sensory"

    # Structural tic: "the kind of X that Y" / "for X years" / "the first time"
    if token_set & STRUCTURAL_HINTS or _looks_structural(tokens):
        return "structural"

    return "signature_phrase"


def _collapse_overlapping_findings(findings: list[Finding]) -> list[Finding]:
    """Collapse n-gram findings that are just a shorter/shifted window of an
    already-accepted longer finding over the same duplicate (Issue #613).

    Overlapping sliding-window n-grams over the same duplicated sentence
    produce one "finding" per window length/offset otherwise — a single
    repeated sentence can inflate into a dozen+ near-identical findings
    that all point at the same underlying duplicate. Processing
    longest-phrase-first, a finding is dropped only when BOTH hold against
    an already-accepted finding:

    - its (chapter, line) occurrence set is a subset of the accepted
      finding's occurrence set (the same duplicate instances, not a
      coincidence of two unrelated phrases sharing a line — a scanner
      "line" is a full paragraph and can legitimately hold more than one
      independently-repeated phrase), and
    - either its phrase is a substring of the accepted phrase (the same
      window, just shorter), or the two share a category (covers two
      same-length windows shifted by one token, which share no substring
      relationship at all but are still the same duplicate — this only
      needs to hold within one category, since a same-length shift can't
      jump from e.g. a body-part token into an unrelated phrase).

    Location-subset alone is not enough on its own (code review H-2): two
    *different*, unrelated findings — a simile and a character_tell from a
    different phrase entirely — can share an occurrence-location set by
    coincidence (the same two paragraphs happen to carry both tics), and
    must not be merged into one just because they co-occur.
    """

    def _locations(f: Finding) -> frozenset[tuple[str, int]]:
        return frozenset((o.chapter, o.line) for o in f.occurrences)

    # Longest phrase first; among equal lengths, higher occurrence count
    # first so a real tie-break prefers the better-evidenced finding over
    # alphabetical order.
    ordered = sorted(findings, key=lambda f: (-len(f.phrase.split()), -f.count, f.phrase))
    kept: list[Finding] = []
    for f in ordered:
        locs = _locations(f)
        if locs and any(
            locs <= _locations(existing) and (f.phrase in existing.phrase or existing.category == f.category)
            for existing in kept
        ):
            continue
        kept.append(f)
    return kept


def _looks_structural(tokens: list[str]) -> bool:
    """Heuristic for repeated structural patterns."""
    if not tokens:
        return False
    # "for <number-ish> years/days/months"
    if tokens[0] == "for" and tokens[-1] in {"years", "year", "days", "months", "weeks"}:
        return True
    # "the X of Y" patterns
    if len(tokens) >= 4 and tokens[0] == "the" and "of" in tokens:
        return True
    return False


__all__ = ["Finding", "Occurrence", "_classify", "_collapse_overlapping_findings", "_looks_structural"]
