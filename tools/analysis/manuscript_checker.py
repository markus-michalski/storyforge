"""Cross-chapter manuscript checker — backwards-compat shim (Issue #118).

The implementation moved into the ``tools.analysis.manuscript`` package.
This module stays as a re-export so existing imports keep working:

- ``from tools.analysis.manuscript_checker import scan_repetitions, render_report``
- ``from tools.analysis.manuscript_checker import _read_book_rules, ...``

New code should import from ``tools.analysis.manuscript`` directly.
"""

from __future__ import annotations

from tools.analysis.manuscript import (  # noqa: F401  (intentional re-exports)
    BLOCKING_VERBS,
    BODY_PARTS,
    DEFAULT_MIN_OCCURRENCES,
    DEFAULT_NGRAM_SIZES,
    Finding,
    Occurrence,
    SENSORY_TOKENS,
    STOP_WORDS,
    STRUCTURAL_HINTS,
    _classify,
    _extract_patterns_from_rule,
    _load_action_verbs,
    _load_cliche_banlist,
    _looks_structural,
    _make_snippet,
    _ngrams_in_line,
    _read_allowed_repetitions,
    _read_book_category,
    _read_book_genres,
    _read_book_rules,
    _read_chapter_drafts,
    _read_people_profiles,
    _read_snapshot_threshold,
    _rule_label,
    _scan_adverb_density,
    _scan_anonymization_leak,
    _scan_book_rules,
    _scan_callbacks,
    _scan_cliches,
    _scan_filter_words,
    _scan_question_as_statement,
    _scan_real_people_consistency,
    _scan_reflective_platitudes,
    _scan_sentence_repetitions,
    _scan_snapshots,
    _scan_tidy_lesson_endings,
    _scan_timeline_ambiguity,
    _scan_writing_discoveries,
    _strip_dialogue,
    _strip_markdown,
    _tokenise,
    render_report,
    scan_repetitions,
)

__all__ = [
    # Public API
    "Finding",
    "Occurrence",
    "render_report",
    "scan_repetitions",
    # Constants
    "BLOCKING_VERBS",
    "BODY_PARTS",
    "DEFAULT_MIN_OCCURRENCES",
    "DEFAULT_NGRAM_SIZES",
    "SENSORY_TOKENS",
    "STOP_WORDS",
    "STRUCTURAL_HINTS",
    # Private helpers (re-exported for tests + skill-side imports)
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
    "_scan_question_as_statement",
    "_scan_real_people_consistency",
    "_scan_reflective_platitudes",
    "_scan_sentence_repetitions",
    "_scan_snapshots",
    "_scan_tidy_lesson_endings",
    "_scan_timeline_ambiguity",
    "_scan_writing_discoveries",
    "_strip_dialogue",
    "_strip_markdown",
    "_tokenise",
]
