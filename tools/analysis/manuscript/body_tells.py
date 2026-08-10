"""Slot-based body-language tell detector (Issue #511).

``scan_repetitions`` in :mod:`__init__` only produces a ``character_tell``
finding when the exact same 4-7 token n-gram repeats. A tic the author
paraphrases each time ("shoulders came down" / "shoulders had dropped" /
"the set of his shoulders") shares no n-gram with its own other occurrences
and is invisible to that pass — it rewards verbal consistency and catches
nothing when the author does the opposite.

This module adds an additive detector: for each manuscript line, if a known
body part and a known body-state signal — a verb (:data:`BODY_STATE_VERBS`)
or a resulting-state adjective (:data:`BODY_STATE_ADJECTIVES`) — appear
within :data:`_PROXIMITY_WINDOW` tokens of each other, that counts as one
occurrence of a tell for that body part. Findings are aggregated **per body
part** across the whole manuscript rather than per exact wording, so
paraphrased repetition surfaces the same way verbatim repetition already
does.

The proximity window (rather than bare same-line co-occurrence) matters
because a manuscript line is a whole markdown paragraph, not a sentence —
without it, a body part and an unrelated state word anywhere in the same
paragraph would false-positive on ordinary prose.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Collection

from tools.analysis.manuscript.metadata import _read_allowed_repetitions
from tools.analysis.manuscript.text_utils import (
    _make_snippet,
    _read_chapter_drafts,
    _strip_dialogue,
    _strip_markdown,
    _tokenise,
)
from tools.analysis.manuscript.types import Finding, Occurrence
from tools.analysis.manuscript.vocabularies import (
    BODY_PARTS,
    BODY_STATE_ADJECTIVES,
    BODY_STATE_COME_DOWN,
    BODY_STATE_VERBS,
)

# Minimum total occurrences (across all matched verb forms) for a body part
# to surface as a finding at all; >=10 escalates to high severity — mirrors
# the issue's proposal (firelight: shoulders=24 -> high, mouth-corners=~19
# already caught by the n-gram pass).
_MIN_OCCURRENCES = 5
_HIGH_THRESHOLD = 10

# Max token distance between a body-part token and a state-signal token for
# them to count as one tell. Generous enough for "his shoulders had come
# down" (distance 2) or "the set of his shoulders" (distance 3), tight
# enough to reject two unrelated clauses in the same paragraph-length line.
_PROXIMITY_WINDOW = 6

# Members of BODY_PARTS excluded from THIS detector's scanning surface (the
# shared BODY_PARTS set used by the n-gram classifier etc. is untouched).
# Both produced confirmed false positives on ordinary prose during review:
# "back" is at least as often a directional adverb ("stepped back", "pulled
# back") as the body-part noun, and "temple"/"temples" is genuinely
# ambiguous with the building sense ("the temple was set on the hill").
_EXCLUDED_FROM_DETECTOR = frozenset({"back", "temple", "temples"})
_DETECTOR_BODY_PARTS = BODY_PARTS - _EXCLUDED_FROM_DETECTOR

# Irregular plurals _canonical_body_part's trailing-"s" strip can't derive.
_IRREGULAR_BODY_PART_PLURALS = {"feet": "foot"}


def _canonical_body_part(token: str) -> str:
    """Collapse a plural body-part token onto its singular form.

    ``BODY_PARTS`` already lists most singular/plural pairs explicitly; this
    only merges the two so "shoulder" and "shoulders" count as one tell
    instead of two separate, sub-threshold findings.
    """
    token = token.rstrip("'")
    if token in _IRREGULAR_BODY_PART_PLURALS:
        return _IRREGULAR_BODY_PART_PLURALS[token]
    if token.endswith("s") and token[:-1] in BODY_PARTS:
        return token[:-1]
    return token


def _state_signal_indices(tokens: list[str]) -> list[int]:
    """Indices of tokens that carry a body-state verb or adjective.

    "came/come down" is handled separately from the rest of
    ``BODY_STATE_VERBS``: bare "came"/"come" is too common in ordinary
    English to count on its own, so it only counts when "down" is the very
    next token.
    """
    indices: list[int] = []
    for i, tok in enumerate(tokens):
        if tok in BODY_STATE_VERBS or tok in BODY_STATE_ADJECTIVES:
            indices.append(i)
        elif tok in BODY_STATE_COME_DOWN and i + 1 < len(tokens) and tokens[i + 1] == "down":
            indices.append(i)
    return indices


def _body_parts_near_signal(tokens: list[str]) -> dict[str, str]:
    """Canonical body parts with a state signal within the proximity window.

    Returns ``{canonical_part: matched_surface_token}`` — the surface token
    (e.g. "feet", not the canonical "foot") is kept so the caller can anchor
    the report snippet on text that actually appears in the line.
    """
    signal_indices = _state_signal_indices(tokens)
    if not signal_indices:
        return {}
    hits: dict[str, str] = {}
    for i, tok in enumerate(tokens):
        normalized = tok.rstrip("'")
        if normalized not in _DETECTOR_BODY_PARTS:
            continue
        if any(abs(i - s) <= _PROXIMITY_WINDOW for s in signal_indices):
            hits.setdefault(_canonical_body_part(normalized), tok)
    return hits


def _scan_body_state_tells(
    book_path: Path,
    *,
    min_occurrences: int = _MIN_OCCURRENCES,
    high_threshold: int = _HIGH_THRESHOLD,
    exclude_sites: Collection[tuple[str, int, str]] = frozenset(),
) -> list[Finding]:
    """Detect paraphrased body-language tics via [body part] + [state verb].

    Additive to the exact-n-gram findings produced by ``scan_repetitions``
    — this only adds findings the n-gram pass structurally cannot see.
    ``exclude_sites`` is a set of ``(chapter, line, canonical_body_part)``
    triples the caller has already reported via the n-gram pass
    (``character_tell`` and ``blocking_tic`` both key off the same
    body-part/verb vocabulary and can overlap this detector); only that
    specific body part on that specific line is skipped, so the same
    physical tell isn't counted twice. Keying on the body part too (not just
    chapter+line) matters because a manuscript line is a whole paragraph —
    an unrelated n-gram hit sharing the paragraph with a genuine paraphrase
    (a different body part, or no body part at all, e.g. a plain
    ``blocking_tic``) must not suppress that paraphrase's own occurrence.

    Only scans narration: dialogue (quoted text) is stripped first, same as
    :func:`tools.analysis.manuscript.scanners._scan_filter_words` and
    :func:`tools.analysis.manuscript.scanners._scan_adverb_density` — a
    body-language tell describes what the narrator shows, not what a
    character says. The report snippet is drawn from the same
    dialogue-stripped text that was matched, so it never shows a match that
    was actually excluded.
    """
    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    allowed = _read_allowed_repetitions(book_path)
    index: dict[str, list[Occurrence]] = defaultdict(list)

    for chapter_slug, raw_text in drafts:
        cleaned = _strip_markdown(raw_text)
        for line_no, original_line in enumerate(cleaned.splitlines(), start=1):
            stripped = original_line.strip()
            if not stripped:
                continue
            narration = _strip_dialogue(stripped)
            tokens = _tokenise(narration)
            parts_hit = _body_parts_near_signal(tokens)
            if not parts_hit:
                continue
            for part, surface_token in parts_hit.items():
                if (chapter_slug, line_no, part) in exclude_sites:
                    continue
                index[part].append(
                    Occurrence(
                        chapter=chapter_slug,
                        line=line_no,
                        snippet=_make_snippet(narration, surface_token),
                    )
                )

    # Canonicalize both sides — the allowlist's tokenised phrases and the
    # aggregation key — so an author writing the natural plural
    # ("- shoulders") still suppresses the singular-canonicalized finding.
    allowed_canonical = {_canonical_body_part(t) for allowed_phrase in allowed for t in allowed_phrase.split()}

    findings: list[Finding] = []
    for part in sorted(index):
        occs = index[part]
        if len(occs) < min_occurrences:
            continue
        if part in allowed_canonical:
            continue
        severity = "high" if len(occs) >= high_threshold else "medium"
        findings.append(
            Finding(
                phrase=f"{part} (varied phrasing)",
                category="character_tell",
                severity=severity,
                count=len(occs),
                occurrences=sorted(occs, key=lambda o: (o.chapter, o.line)),
                # Synthetic label, not manuscript text — must never be
                # promoted into an author-level literal scan pattern.
                promotable=False,
            )
        )
    return findings


__all__ = ["_canonical_body_part", "_scan_body_state_tells"]
