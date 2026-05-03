"""Tests for ``tools.author.rule_harvester`` (Issue #151).

The harvester collects buchspezifische findings (book CLAUDE.md rules,
manuscript-checker findings) and classifies each into one of three buckets:

- ``banned_phrase`` — single-word/phrase ban → ``vocabulary.md``
- ``style_principle`` — pattern/structural rule → ``profile.md`` Writing Discoveries
- ``world_rule`` — book-canon term → ``keep_book_only``

Tests use the pure layer that takes pre-loaded inputs so they don't need a
real book on disk. Integration of the file-loading composition layer is
covered in ``test_harvest_book_rules.py`` (MCP tool).
"""

from __future__ import annotations

from tools.analysis.manuscript.types import Finding, Occurrence
from tools.author.rule_harvester import (
    Candidate,
    classify_finding,
    classify_rule,
    collect_book_rule_candidates,
    collect_manuscript_candidates,
    deduplicate_against_author,
    harvest,
)
from tools.claudemd.rules_editor import ParsedRule


def _rule(
    index: int,
    raw_text: str,
    *,
    has_regex: bool = False,
    has_literals: bool = True,
    patterns: list[dict] | None = None,
) -> ParsedRule:
    if patterns is None:
        patterns = [{"label": "math", "pattern": "math", "is_regex": False}]
    return ParsedRule(
        index=index,
        title="rule",
        raw_text=raw_text,
        has_regex=has_regex,
        has_literals=has_literals,
        extracted_patterns=patterns,
    )


# ---------------------------------------------------------------------------
# classify_rule — book CLAUDE.md rules
# ---------------------------------------------------------------------------


class TestClassifyRule:
    def test_short_phrase_with_literal_pattern_is_banned_phrase(self):
        rule = _rule(
            0,
            "Avoid `math` — Theo's analytical metaphor tic.",
            patterns=[{"label": "math", "pattern": "math", "is_regex": False}],
        )
        kind, target = classify_rule(rule, world_terms=set())
        assert kind == "banned_phrase"
        assert target == "vocabulary"

    def test_regex_rule_is_style_principle(self):
        rule = _rule(
            1,
            "Avoid blocking pattern `[A-Z]\\w+ moved to [a-z]+` — replace with sensory anchor.",
            has_regex=True,
            patterns=[{"label": "blocking", "pattern": r"[A-Z]\w+ moved to [a-z]+", "is_regex": True}],
        )
        kind, target = classify_rule(rule, world_terms=set())
        assert kind == "style_principle"
        assert target == "recurring_tics"

    def test_template_slot_is_style_principle(self):
        """Bracketed slots like `[Character]` are template patterns, not literals."""
        rule = _rule(
            2,
            "Avoid `[Character] moved to [location]` — author default.",
            patterns=[{"label": "[Character] moved to [location]", "pattern": "...", "is_regex": False}],
        )
        kind, target = classify_rule(rule, world_terms=set())
        assert kind == "style_principle"
        assert target == "recurring_tics"

    def test_world_term_is_world_rule(self):
        rule = _rule(
            3,
            "Lykos can sense fire affinity by scent — magic-system canon.",
            has_literals=False,
            patterns=[],
        )
        kind, target = classify_rule(rule, world_terms={"lykos", "fire affinity"})
        assert kind == "world_rule"
        assert target is None

    def test_prose_rule_without_patterns_is_style_principle(self):
        rule = _rule(4, "Avoid info-dumps in dialog.", has_literals=False, patterns=[])
        kind, target = classify_rule(rule, world_terms=set())
        assert kind == "style_principle"
        # Prose rules without explicit pattern shape default to style_principles.
        assert target == "style_principles"

    def test_multi_word_literal_long_phrase_is_style_principle(self):
        rule = _rule(
            5,
            "Avoid `the kind of X that Y` constructions — author tic.",
            patterns=[{"label": "the kind of X that Y", "pattern": "the kind of X that Y", "is_regex": False}],
        )
        kind, target = classify_rule(rule, world_terms=set())
        # 5-word literal → not a single banned phrase → style_principle
        assert kind == "style_principle"


# ---------------------------------------------------------------------------
# classify_finding — manuscript-checker findings
# ---------------------------------------------------------------------------


class TestClassifyFinding:
    def _finding(self, phrase: str, category: str, severity: str = "high", count: int = 6) -> Finding:
        occs = [Occurrence(chapter=f"ch-{i:02d}", line=1, snippet=phrase) for i in range(count)]
        return Finding(phrase=phrase, category=category, severity=severity, count=count, occurrences=occs)

    def test_signature_phrase_is_banned_phrase(self):
        kind, target = classify_finding(self._finding("the silence stretched", "signature_phrase"))
        assert kind == "banned_phrase"
        assert target == "vocabulary"

    def test_simile_is_banned_phrase(self):
        kind, target = classify_finding(self._finding("like a stone", "simile"))
        assert kind == "banned_phrase"
        assert target == "vocabulary"

    def test_blocking_tic_is_style_principle(self):
        kind, target = classify_finding(self._finding("opened it closed", "blocking_tic"))
        assert kind == "style_principle"
        assert target == "recurring_tics"

    def test_structural_finding_is_style_principle(self):
        kind, target = classify_finding(self._finding("for years and years", "structural"))
        assert kind == "style_principle"
        assert target == "recurring_tics"

    def test_book_rule_violation_inherits_book_rule_type(self):
        f = self._finding("math", "book_rule_violation")
        f.source_rule = "Avoid `math` — Theo's tic."
        # Book rules already classified via classify_rule — finding-side keeps banned_phrase
        # since the source rule's literal phrase is what landed in the manuscript.
        kind, target = classify_finding(f)
        assert kind == "banned_phrase"


# ---------------------------------------------------------------------------
# collect_book_rule_candidates
# ---------------------------------------------------------------------------


class TestCollectBookRuleCandidates:
    def test_emits_one_candidate_per_rule(self):
        rules = [
            _rule(0, "Avoid `math` — Theo's tic."),
            _rule(
                1,
                "Avoid blocking pattern `[Character] moved to [location]` — author default.",
                patterns=[{"label": "[Character] moved to [location]", "pattern": "...", "is_regex": False}],
            ),
        ]
        candidates = collect_book_rule_candidates(rules, world_terms=set())
        assert len(candidates) == 2
        types = {c.type for c in candidates}
        assert types == {"banned_phrase", "style_principle"}

    def test_world_rules_get_keep_recommendation(self):
        rules = [_rule(0, "Lykos sense fire affinity.", has_literals=False, patterns=[])]
        candidates = collect_book_rule_candidates(rules, world_terms={"lykos"})
        assert len(candidates) == 1
        assert candidates[0].type == "world_rule"
        assert candidates[0].recommendation == "keep_book_only"

    def test_promotable_candidates_recommend_promote(self):
        rules = [_rule(0, "Avoid `math` — Theo's tic.")]
        candidates = collect_book_rule_candidates(rules, world_terms=set())
        assert candidates[0].recommendation == "promote"

    def test_carries_source_rule_index_for_later_removal(self):
        rules = [_rule(7, "Avoid `math` — Theo's tic.")]
        candidates = collect_book_rule_candidates(rules, world_terms=set())
        assert candidates[0].source == "book_rule"
        assert candidates[0].source_rule_index == 7


# ---------------------------------------------------------------------------
# collect_manuscript_candidates
# ---------------------------------------------------------------------------


class TestCollectManuscriptCandidates:
    def _finding(self, phrase: str, category: str, *, count: int, severity: str = "high") -> Finding:
        chapters = [f"ch-{i:02d}" for i in range(count)]
        occs = [Occurrence(chapter=ch, line=1, snippet=phrase) for ch in chapters]
        return Finding(phrase=phrase, category=category, severity=severity, count=count, occurrences=occs)

    def test_high_severity_with_multiple_chapters_emits_candidate(self):
        finding = self._finding("the silence stretched", "signature_phrase", count=6)
        candidates = collect_manuscript_candidates([finding])
        assert len(candidates) == 1
        assert "silence" in candidates[0].value
        assert candidates[0].source == "manuscript_finding"

    def test_filters_out_low_severity_findings(self):
        finding = self._finding("foo", "signature_phrase", count=4, severity="medium")
        candidates = collect_manuscript_candidates([finding])
        assert candidates == []

    def test_filters_out_findings_in_too_few_chapters(self):
        # 2 chapters < default threshold of 3
        finding = self._finding("foo", "signature_phrase", count=2)
        candidates = collect_manuscript_candidates([finding])
        assert candidates == []

    def test_threshold_chapters_is_configurable(self):
        finding = self._finding("foo", "signature_phrase", count=2)
        candidates = collect_manuscript_candidates([finding], threshold_chapters=2)
        assert len(candidates) == 1


# ---------------------------------------------------------------------------
# deduplicate_against_author
# ---------------------------------------------------------------------------


class TestDeduplicateAgainstAuthor:
    def _candidate(self, value: str, kind: str = "banned_phrase") -> Candidate:
        return Candidate(
            id=f"cand-{value}",
            type=kind,
            value=value,
            context="",
            evidence="",
            recommendation="promote",
            rationale="",
            source="book_rule",
            source_rule_index=0,
            target_section="vocabulary" if kind == "banned_phrase" else "recurring_tics",
        )

    def test_drops_phrase_already_in_vocabulary(self):
        candidates = [self._candidate("math"), self._candidate("just")]
        vocabulary_text = "### Absolutely Forbidden\n\n- math\n- clocked\n"
        author_profile = {"writing_discoveries": {"recurring_tics": [], "style_principles": [], "donts": []}}

        kept = deduplicate_against_author(candidates, vocabulary_text=vocabulary_text, author_profile=author_profile)
        values = [c.value for c in kept]
        assert "math" not in values
        assert "just" in values

    def test_drops_principle_already_in_writing_discoveries(self):
        principle = self._candidate("blocking pattern moved to", kind="style_principle")
        author_profile = {
            "writing_discoveries": {
                "recurring_tics": [{"text": "Blocking pattern moved to location", "origins": []}],
                "style_principles": [],
                "donts": [],
            }
        }
        kept = deduplicate_against_author([principle], vocabulary_text="", author_profile=author_profile)
        assert kept == []

    def test_keeps_distinct_principles(self):
        principle = self._candidate("info-dumps in dialog", kind="style_principle")
        author_profile = {
            "writing_discoveries": {
                "recurring_tics": [{"text": "Blocking pattern moved to location", "origins": []}],
                "style_principles": [],
                "donts": [],
            }
        }
        kept = deduplicate_against_author([principle], vocabulary_text="", author_profile=author_profile)
        assert len(kept) == 1

    def test_handles_missing_author_profile(self):
        candidates = [self._candidate("math")]
        kept = deduplicate_against_author(candidates, vocabulary_text="", author_profile=None)
        assert kept == candidates


# ---------------------------------------------------------------------------
# harvest — orchestration
# ---------------------------------------------------------------------------


class TestHarvest:
    def test_returns_issue_spec_shape(self):
        rules = [_rule(0, "Avoid `math` — Theo's tic.")]
        result = harvest(
            book_slug="firelight",
            author_slug="ethan-cole",
            parsed_rules=rules,
            findings=[],
            author_profile=None,
            vocabulary_text="",
            world_terms=set(),
        )
        assert result["book_slug"] == "firelight"
        assert result["author_slug"] == "ethan-cole"
        assert "candidates" in result
        assert "summary" in result
        assert result["summary"]["total"] == 1
        assert result["summary"]["recommended_promote"] == 1

    def test_summary_counts_per_recommendation(self):
        rules = [
            _rule(0, "Avoid `math` — Theo's tic."),
            _rule(1, "Lykos sense fire affinity.", has_literals=False, patterns=[]),
        ]
        result = harvest(
            book_slug="firelight",
            author_slug=None,
            parsed_rules=rules,
            findings=[],
            author_profile=None,
            vocabulary_text="",
            world_terms={"lykos"},
        )
        assert result["summary"]["total"] == 2
        assert result["summary"]["recommended_promote"] == 1
        assert result["summary"]["recommended_keep_book"] == 1

    def test_dedups_candidates_already_in_author(self):
        rules = [_rule(0, "Avoid `math` — Theo's tic.")]
        author_profile = {
            "writing_discoveries": {"recurring_tics": [], "style_principles": [], "donts": []}
        }
        vocabulary_text = "### Absolutely Forbidden\n\n- math\n"
        result = harvest(
            book_slug="firelight",
            author_slug="ethan-cole",
            parsed_rules=rules,
            findings=[],
            author_profile=author_profile,
            vocabulary_text=vocabulary_text,
            world_terms=set(),
        )
        assert result["candidates"] == []
        assert result["summary"]["total"] == 0
