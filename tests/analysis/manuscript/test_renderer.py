"""Unit tests for tools.analysis.manuscript.renderer."""

from __future__ import annotations

from tools.analysis.manuscript.renderer import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    render_report,
)


class TestRenderReport:
    def test_empty_findings_message(self) -> None:
        report = render_report({
            "findings": [],
            "chapters_scanned": 5,
            "summary": {},
        })
        assert "No cross-chapter repetitions" in report
        assert "Chapters scanned:** 5" in report

    def test_renders_summary_table(self) -> None:
        report = render_report({
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
        })
        assert "## Summary" in report
        assert "Book Rule Violations" in report
        assert "**Rule:** Avoid `synergy`" in report
        assert "01" in report and "line 12" in report

    def test_recommendation_present_per_finding(self) -> None:
        report = render_report({
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
        })
        assert "_Recommendation:_" in report

    def test_category_order_matches_labels(self) -> None:
        # Every label in CATEGORY_ORDER must have a matching display label.
        for cat in CATEGORY_ORDER:
            assert cat in CATEGORY_LABELS, f"missing label for {cat}"
