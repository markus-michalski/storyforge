"""Cross-chapter manuscript checker — package layout (Issue #118).

Scans all chapter drafts of a book for prose-quality issues that only
surface when the whole manuscript is read in one pass. Produces a
structured report for the ``manuscript-checker`` skill, which turns it
into human-readable Markdown with revision recommendations.

The module is dependency-free (stdlib only) so it can run inside the
MCP server without extra installs.

Detection categories
--------------------
- **book_rule_violation** — Patterns extracted from the book's CLAUDE.md rules.
- **simile / character_tell / blocking_tic / sensory / structural /
  signature_phrase** — Cross-chapter repeated n-grams.
- **filter_word** — POV-distancing verbs ("felt", "noticed", "saw that") that
  weaken close-third narration.
- **adverb_density** — Per-chapter ``-ly`` adverb ratio.
- **cliche** — Curated banlist of worn-out fiction phrasings.
- **question_as_statement** — Dialogue that starts with an interrogative word
  but ends with a period instead of a question mark.
- **sentence_repetition / snapshot / callback_dropped / callback_deferred** —
  Structural pattern checks.
- Memoir-specific (``book_category: memoir``):
  **anonymization_leak / tidy_lesson_ending / reflective_platitude /
  timeline_ambiguity / real_people_consistency**.

Public API: :func:`scan_repetitions` (the orchestrator) and
:func:`render_report` (Markdown rendering).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from tools.analysis.manuscript.memoir_patterns import (
    _scan_anonymization_leak,
    _scan_real_people_consistency,
    _scan_reflective_platitudes,
    _scan_tidy_lesson_endings,
    _scan_timeline_ambiguity,
)
from tools.analysis.manuscript.metadata import (
    _read_allowed_repetitions,
    _read_book_category,
    _read_book_genres,
    _read_people_profiles,
    _read_snapshot_threshold,
)
from tools.analysis.manuscript.renderer import render_report
from tools.analysis.manuscript.rules import (
    _extract_patterns_from_rule,
    _read_book_rules,
    _rule_label,
    _scan_book_rules,
)
from tools.analysis.manuscript.scanners import (
    _load_action_verbs,
    _load_cliche_banlist,
    _scan_adverb_density,
    _scan_callbacks,
    _scan_cliches,
    _scan_filter_words,
    _scan_plot_holes,
    _scan_question_as_statement,
    _scan_sentence_repetitions,
    _scan_snapshots,
    _strip_dialogue,
)
from tools.analysis.manuscript.text_utils import (
    _make_snippet,
    _ngrams_in_line,
    _read_chapter_drafts,
    _strip_markdown,
    _tokenise,
)
from tools.analysis.manuscript.types import (
    Finding,
    Occurrence,
    _classify,
    _looks_structural,
)
from tools.analysis.manuscript.vocabularies import (
    BLOCKING_VERBS,
    BODY_PARTS,
    DEFAULT_MIN_OCCURRENCES,
    DEFAULT_NGRAM_SIZES,
    SENSORY_TOKENS,
    STOP_WORDS,
    STRUCTURAL_HINTS,
)

# Plugin root: three levels up from tools/analysis/manuscript/
_PLUGIN_ROOT = Path(__file__).resolve().parents[3]


def scan_repetitions(
    book_path: Path,
    ngram_sizes: Iterable[int] = DEFAULT_NGRAM_SIZES,
    min_occurrences: int = DEFAULT_MIN_OCCURRENCES,
    max_findings_per_category: int | None = None,
    plugin_root: Path | None = None,
    book_category: str | None = None,
) -> dict[str, Any]:
    """Scan all chapter drafts of a book for repeated phrases.

    Returns a dict with ``findings`` (list[Finding-as-dict]), grouped
    counts, and basic metadata. The caller — typically the MCP tool —
    turns this into a Markdown report via :func:`render_report`.
    """
    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return {
            "book_path": str(book_path),
            "chapters_scanned": 0,
            "findings": [],
            "summary": {},
        }

    # Map: phrase -> list[Occurrence]
    index: dict[str, list[Occurrence]] = defaultdict(list)
    sizes = tuple(ngram_sizes)

    for chapter_slug, raw_text in drafts:
        cleaned = _strip_markdown(raw_text)
        for line_no, original_line in enumerate(cleaned.splitlines(), start=1):
            stripped = original_line.strip()
            if not stripped:
                continue
            tokens = _tokenise(stripped)
            if len(tokens) < min(sizes):
                continue
            for _size, _i, phrase in _ngrams_in_line(tokens, sizes):
                snippet = _make_snippet(stripped, phrase)
                index[phrase].append(Occurrence(chapter=chapter_slug, line=line_no, snippet=snippet))

    # Per-length thresholds. Shorter n-grams need MORE occurrences to be
    # considered noteworthy, otherwise the report drowns in 4-grams that are
    # just common English connective tissue.
    length_thresholds = {
        4: max(min_occurrences, 5),
        5: max(min_occurrences, 3),
        6: max(min_occurrences, 2),
        7: max(min_occurrences, 2),
    }

    # Build findings, dropping sub-phrases that a longer accepted phrase
    # already explains. Tolerance of 1 catches the case where the shorter
    # phrase appears once outside the longer match.
    findings: list[Finding] = []
    sorted_phrases = sorted(index.keys(), key=lambda p: (-len(p.split()), p))
    seen_long: list[tuple[str, int]] = []  # (phrase, count) of accepted longer phrases

    for phrase in sorted_phrases:
        occs = index[phrase]
        size = len(phrase.split())
        threshold = length_thresholds.get(size, min_occurrences)
        if len(occs) < threshold:
            continue
        # Skip if a longer accepted phrase fully contains this one with a
        # comparable occurrence count (within +/- 1).
        if any(phrase in longer and abs(len(occs) - longer_count) <= 1 for longer, longer_count in seen_long):
            continue
        category = _classify(phrase, occs)
        severity = "high" if len(occs) >= 4 else "medium"
        findings.append(
            Finding(
                phrase=phrase,
                category=category,
                severity=severity,
                count=len(occs),
                occurrences=sorted(occs, key=lambda o: (o.chapter, o.line)),
            )
        )
        seen_long.append((phrase, len(occs)))

    # Merge in per-book CLAUDE.md rule violations. These are high-severity
    # by definition and ignore the n-gram frequency thresholds above.
    findings.extend(_scan_book_rules(book_path))
    # Merge the craft-level checks (filter words, adverb density, clichés,
    # question-as-statement punctuation, sentence-level repetitions).
    findings.extend(_scan_filter_words(book_path))
    findings.extend(_scan_adverb_density(book_path))
    book_genres = _read_book_genres(book_path)
    findings.extend(
        _scan_cliches(
            book_path,
            plugin_root=plugin_root,
            genres=book_genres or None,
        )
    )
    findings.extend(_scan_question_as_statement(book_path))
    findings.extend(_scan_sentence_repetitions(book_path))
    findings.extend(_scan_snapshots(book_path, plugin_root=plugin_root))
    findings.extend(_scan_callbacks(book_path))
    # Plot-logic findings (causality_inversion, chekhov_gun) — Issue #150.
    # Outranks clichés in the sort below; reader trust > prose tics.
    findings.extend(_scan_plot_holes(book_path))

    # Memoir-specific checks — run only when book_category is memoir.
    if book_category is None:
        book_category = _read_book_category(book_path)
    if book_category == "memoir":
        findings.extend(_scan_anonymization_leak(book_path))
        findings.extend(_scan_tidy_lesson_endings(book_path))
        findings.extend(_scan_reflective_platitudes(book_path))
        findings.extend(_scan_timeline_ambiguity(book_path))
        findings.extend(_scan_real_people_consistency(book_path))

    # Sort order priority: book_rule_violation first (user-authored rules
    # override everything), then anonymization_leak (privacy-critical),
    # then plot_hole (story-logic breaks reader trust), then clichés,
    # then the rest by severity.
    # Within same bucket: severity desc, count desc, phrase asc.
    category_rank = {
        "book_rule_violation": 0,
        "anonymization_leak": 1,
        "plot_hole": 2,
        "cliche": 3,
    }
    severity_rank = {"high": 0, "medium": 1}
    findings.sort(
        key=lambda f: (
            category_rank.get(f.category, 4),
            severity_rank[f.severity],
            -f.count,
            f.phrase,
        )
    )

    if max_findings_per_category is not None:
        per_cat: dict[str, int] = defaultdict(int)
        capped: list[Finding] = []
        for f in findings:
            if per_cat[f.category] >= max_findings_per_category:
                continue
            per_cat[f.category] += 1
            capped.append(f)
        findings = capped

    # Summary
    summary: dict[str, dict[str, int]] = defaultdict(lambda: {"high": 0, "medium": 0})
    for f in findings:
        summary[f.category][f.severity] += 1

    return {
        "book_path": str(book_path),
        "chapters_scanned": len(drafts),
        "findings": [_finding_to_dict(f) for f in findings],
        "summary": {k: dict(v) for k, v in summary.items()},
    }


def _finding_to_dict(f: Finding) -> dict[str, Any]:
    return asdict(f)


__all__ = [
    # Public API
    "Finding",
    "Occurrence",
    "render_report",
    "scan_repetitions",
    # Constants surfaced for backward compat with the legacy module.
    "BLOCKING_VERBS",
    "BODY_PARTS",
    "DEFAULT_MIN_OCCURRENCES",
    "DEFAULT_NGRAM_SIZES",
    "SENSORY_TOKENS",
    "STOP_WORDS",
    "STRUCTURAL_HINTS",
    # Private helpers re-exported for the legacy shim.
    "_classify",
    "_extract_patterns_from_rule",
    "_load_action_verbs",
    "_load_cliche_banlist",
    "_looks_structural",
    "_make_snippet",
    "_ngrams_in_line",
    "_read_allowed_repetitions",
    "_read_book_category",
    "_read_book_genres",
    "_read_book_rules",
    "_read_chapter_drafts",
    "_read_people_profiles",
    "_read_snapshot_threshold",
    "_rule_label",
    "_scan_adverb_density",
    "_scan_anonymization_leak",
    "_scan_book_rules",
    "_scan_callbacks",
    "_scan_cliches",
    "_scan_filter_words",
    "_scan_plot_holes",
    "_scan_question_as_statement",
    "_scan_real_people_consistency",
    "_scan_reflective_platitudes",
    "_scan_sentence_repetitions",
    "_scan_snapshots",
    "_scan_tidy_lesson_endings",
    "_scan_timeline_ambiguity",
    "_strip_dialogue",
    "_strip_markdown",
    "_tokenise",
]
