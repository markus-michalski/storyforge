"""Tests for renderer.py category wiring (Issue #210 + latent bug from #151).

Three categories that historically were emitted by scanners but never
appeared in reports because they were missing from ``CATEGORY_LABELS`` /
``CATEGORY_ORDER``:

- ``writing_discovery_violation`` (latent from #151)
- ``author_rule_violation`` (new in #210)
- ``author_vocab_violation`` (new in #210, also emitted by the hook)

The renderer iterates ``CATEGORY_ORDER`` and drops any findings whose
category is not in the list — that is the silent-drop bug.
"""

from __future__ import annotations

from tools.analysis.manuscript.renderer import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    render_report,
)


class TestCategoryWiring:
    def test_writing_discovery_violation_is_labeled(self):
        assert "writing_discovery_violation" in CATEGORY_LABELS
        assert "writing_discovery_violation" in CATEGORY_ORDER

    def test_author_rule_violation_is_labeled(self):
        assert "author_rule_violation" in CATEGORY_LABELS
        assert "author_rule_violation" in CATEGORY_ORDER

    def test_author_vocab_violation_is_labeled(self):
        assert "author_vocab_violation" in CATEGORY_LABELS
        assert "author_vocab_violation" in CATEGORY_ORDER

    def test_author_categories_render_their_own_section(self):
        """A finding with author_rule_violation must surface in the report
        Markdown, not be silently dropped."""
        scan = {
            "chapters_scanned": 1,
            "findings": [
                {
                    "phrase": "the room received it",
                    "category": "author_rule_violation",
                    "severity": "high",
                    "count": 1,
                    "occurrences": [
                        {
                            "chapter": "01-open",
                            "line": 5,
                            "snippet": "...the room received it without...",
                        }
                    ],
                    "source_rule": "author profile (Don'ts) [ethan-cole] — rooms",
                },
            ],
            "summary": {"author_rule_violation": {"high": 1, "medium": 0}},
        }
        out = render_report(scan)
        # Section header must be present (the label, not the raw category key).
        assert CATEGORY_LABELS["author_rule_violation"] in out
        # The finding's phrase + occurrence must surface.
        assert "the room received it" in out
        assert "01-open" in out

    def test_writing_discovery_violation_renders(self):
        scan = {
            "chapters_scanned": 1,
            "findings": [
                {
                    "phrase": "thing",
                    "category": "writing_discovery_violation",
                    "severity": "high",
                    "count": 1,
                    "occurrences": [
                        {"chapter": "01", "line": 3, "snippet": "...a thing happened..."}
                    ],
                    "source_rule": "author profile (Recurring Tics) — thing",
                },
            ],
            "summary": {"writing_discovery_violation": {"high": 1, "medium": 0}},
        }
        out = render_report(scan)
        assert CATEGORY_LABELS["writing_discovery_violation"] in out
        assert "thing" in out

    def test_author_vocab_violation_renders(self):
        scan = {
            "chapters_scanned": 1,
            "findings": [
                {
                    "phrase": "delve",
                    "category": "author_vocab_violation",
                    "severity": "high",
                    "count": 1,
                    "occurrences": [
                        {"chapter": "01", "line": 7, "snippet": "...began to delve..."}
                    ],
                    "source_rule": "author vocabulary [ethan-cole]",
                },
            ],
            "summary": {"author_vocab_violation": {"high": 1, "medium": 0}},
        }
        out = render_report(scan)
        assert CATEGORY_LABELS["author_vocab_violation"] in out
        assert "delve" in out

    def test_author_categories_ordered_after_book_rules(self):
        """Author-level findings are user-asserted bans; they should render
        immediately after book-level rule violations and before generic
        craft-level findings (clichés, filter words, etc.)."""
        book_idx = CATEGORY_ORDER.index("book_rule_violation")
        rule_idx = CATEGORY_ORDER.index("author_rule_violation")
        vocab_idx = CATEGORY_ORDER.index("author_vocab_violation")
        tic_idx = CATEGORY_ORDER.index("writing_discovery_violation")
        cliche_idx = CATEGORY_ORDER.index("cliche")

        assert book_idx < rule_idx < cliche_idx
        assert book_idx < vocab_idx < cliche_idx
        assert book_idx < tic_idx < cliche_idx
