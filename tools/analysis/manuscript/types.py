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


__all__ = ["Finding", "Occurrence", "_classify", "_looks_structural"]
