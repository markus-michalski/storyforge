"""Unit tests for tools.analysis.manuscript.renderer."""

from __future__ import annotations

from tools.analysis.manuscript.renderer import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    render_report,
)


class TestRenderReport:
    def test_empty_findings_message(self) -> None:
        report = render_report(
            {
                "findings": [],
                "chapters_scanned": 5,
                "summary": {},
            }
        )
        assert "No cross-chapter repetitions" in report
        assert "Chapters scanned:** 5" in report

    def test_renders_summary_table(self) -> None:
        report = render_report(
            {
                "findings": [
                    {
                        "phrase": "synergy",
                        "category": "book_rule_violation",
                        "severity": "high",
                        "count": 3,
                        "occurrences": [
                            {"chapter": "01", "line": 12, "snippet": "the synergy"},
                        ],
                        "source_rule": "Avoid `synergy`",
                    },
                ],
                "chapters_scanned": 4,
                "summary": {"book_rule_violation": {"high": 1, "medium": 0}},
            }
        )
        assert "## Summary" in report
        assert "Book Rule Violations" in report
        assert "**Rule:** Avoid `synergy`" in report
        assert "01" in report and "line 12" in report

    def test_recommendation_present_per_finding(self) -> None:
        report = render_report(
            {
                "findings": [
                    {
                        "phrase": "blood ran cold",
                        "category": "cliche",
                        "severity": "high",
                        "count": 2,
                        "occurrences": [
                            {"chapter": "02", "line": 1, "snippet": "his blood ran cold"},
                        ],
                    },
                ],
                "chapters_scanned": 1,
                "summary": {"cliche": {"high": 1, "medium": 0}},
            }
        )
        assert "_Recommendation:_" in report

    def test_category_order_matches_labels(self) -> None:
        # Every label in CATEGORY_ORDER must have a matching display label.
        for cat in CATEGORY_ORDER:
            assert cat in CATEGORY_LABELS, f"missing label for {cat}"

    def test_unreadable_meta_findings_get_an_actionable_recommendation(self) -> None:
        """Issue #584 code review MEDIUM-2: book_rules_unreadable/
        callbacks_unreadable are synthetic meta-findings with no real prose
        occurrences — count=1, occurrences=[]. Falling through to the
        generic repetition-fallback text ("cut or rewrite the other 0")
        told the author to edit prose for a problem that isn't a prose
        problem at all. Must instead point at add_book_to_series()."""
        report = render_report(
            {
                "findings": [
                    {
                        "phrase": "callbacks_unreadable",
                        "category": "callbacks_unreadable",
                        "severity": "high",
                        "count": 1,
                        "occurrences": [],
                        "source_rule": "Book 'b2' has series='saga' but series_number=0 — "
                        "call add_book_to_series(...) first.",
                    },
                ],
                "chapters_scanned": 4,
                "summary": {"callbacks_unreadable": {"high": 1, "medium": 0}},
            }
        )
        assert "add_book_to_series" in report
        assert "cut or rewrite the other" not in report
