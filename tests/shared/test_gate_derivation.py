"""Tests for gate-derivation helpers (Issue #122)."""

from __future__ import annotations

from tools.shared.gate_derivation import (
    derive_from_callback_verification,
    derive_from_consent_check,
    derive_from_manuscript_scan,
    derive_from_structure_validation,
    derive_from_tactical_setup,
    derive_from_timeline_validation,
)


class TestManuscriptScan:
    def test_no_findings_passes(self):
        gate = derive_from_manuscript_scan({"chapters_scanned": 5, "findings": []})
        assert gate.status == "PASS"
        assert gate.metadata["chapters_scanned"] == 5
        assert gate.metadata["findings_count"] == 0
        assert gate.metadata["rule_violations"] == 0

    def test_book_rule_violation_fails(self):
        gate = derive_from_manuscript_scan(
            {
                "chapters_scanned": 3,
                "findings": [
                    {
                        "phrase": "the air went still",
                        "category": "book_rule_violation",
                        "severity": "high",
                        "occurrences": [{"chapter": "01", "line": 12}],
                    },
                ],
            }
        )
        assert gate.status == "FAIL"
        assert gate.metadata["rule_violations"] == 1
        assert gate.findings[0].severity == "FAIL"
        assert gate.findings[0].code == "BOOK_RULE_VIOLATION"
        assert gate.findings[0].location["chapter"] == "01"

    def test_other_findings_warn(self):
        gate = derive_from_manuscript_scan(
            {
                "chapters_scanned": 3,
                "findings": [
                    {
                        "phrase": "her heart skipped",
                        "category": "cliche",
                        "severity": "high",
                        "occurrences": [{"chapter": "02", "line": 5}],
                    },
                ],
            }
        )
        assert gate.status == "WARN"
        assert gate.findings[0].severity == "WARN"


class TestTimelineValidation:
    def test_clean_timeline_passes(self):
        gate = derive_from_timeline_validation(
            {
                "chapters_checked": 4,
                "calendar_built": True,
                "findings": [],
                "missing_anchors": [],
            }
        )
        assert gate.status == "PASS"

    def test_missing_anchors_only_warn(self):
        gate = derive_from_timeline_validation(
            {
                "chapters_checked": 4,
                "calendar_built": True,
                "findings": [],
                "missing_anchors": ["03-prologue"],
            }
        )
        assert gate.status == "WARN"
        assert gate.metadata["missing_anchors_count"] == 1

    def test_drift_findings_fail(self):
        gate = derive_from_timeline_validation(
            {
                "chapters_checked": 4,
                "calendar_built": True,
                "findings": [{"chapter": "02", "line": 14, "message": "drift"}],
                "missing_anchors": [],
            }
        )
        assert gate.status == "FAIL"
        assert gate.findings[0].severity == "FAIL"


class TestCallbackVerification:
    def test_no_callbacks_passes(self):
        gate = derive_from_callback_verification(
            {
                "callbacks_checked": 0,
                "satisfied": [],
                "deferred": [],
                "potentially_dropped": [],
            }
        )
        assert gate.status == "PASS"

    def test_dropped_callback_fails(self):
        gate = derive_from_callback_verification(
            {
                "callbacks_checked": 1,
                "satisfied": [],
                "deferred": [],
                "potentially_dropped": [
                    {"name": "Lena's promise", "warning": "deadline passed"},
                ],
            }
        )
        assert gate.status == "FAIL"
        assert any(f.code == "CALLBACK_DROPPED" for f in gate.findings)

    def test_only_deferred_warns(self):
        gate = derive_from_callback_verification(
            {
                "callbacks_checked": 1,
                "satisfied": [],
                "deferred": [{"name": "magic-cost", "status": "pending"}],
                "potentially_dropped": [],
            }
        )
        assert gate.status == "WARN"


class TestConsentCheck:
    def test_overall_pass(self):
        gate = derive_from_consent_check(
            {
                "overall": "PASS",
                "pass_count": 3,
                "warn_count": 0,
                "fail_count": 0,
                "people": [],
            }
        )
        assert gate.status == "PASS"

    def test_overall_warn_records_warn_findings(self):
        gate = derive_from_consent_check(
            {
                "overall": "WARN",
                "pass_count": 1,
                "warn_count": 1,
                "fail_count": 0,
                "people": [
                    {"slug": "alice", "verdict": "PASS", "reason": "ok"},
                    {"slug": "bob", "verdict": "WARN", "reason": "consent pending"},
                ],
            }
        )
        assert gate.status == "WARN"
        codes = {f.code for f in gate.findings}
        assert "CONSENT_WARN" in codes
        assert "CONSENT_PASS" not in codes

    def test_overall_fail(self):
        gate = derive_from_consent_check(
            {
                "overall": "FAIL",
                "pass_count": 0,
                "warn_count": 0,
                "fail_count": 1,
                "people": [
                    {"slug": "x", "verdict": "FAIL", "reason": "refused consent"},
                ],
            }
        )
        assert gate.status == "FAIL"


class TestTacticalSetup:
    def test_clean_setup_passes(self):
        gate = derive_from_tactical_setup({"passes": True, "warnings": []})
        assert gate.status == "PASS"

    def test_warns_when_warnings_present(self):
        gate = derive_from_tactical_setup(
            {
                "passes": False,
                "warnings": [{"severity": "warn", "message": "lead unprotected"}],
            }
        )
        assert gate.status == "WARN"
        assert gate.findings[0].code == "TACTICAL_WARN"


class TestStructureValidation:
    def test_all_checks_pass(self):
        gate = derive_from_structure_validation(
            {
                "checks": [
                    {"check": "README.md", "status": "PASS"},
                    {"check": "synopsis.md", "status": "PASS"},
                ],
                "passed": 2,
                "total": 2,
            }
        )
        assert gate.status == "PASS"
        assert gate.metadata["passed"] == 2

    def test_required_failure(self):
        gate = derive_from_structure_validation(
            {
                "checks": [
                    {"check": "README.md", "status": "PASS"},
                    {"check": "synopsis.md", "status": "FAIL"},
                ],
                "passed": 1,
                "total": 2,
            }
        )
        assert gate.status == "FAIL"
        assert any(f.code == "STRUCTURE_MISSING" for f in gate.findings)

    def test_optional_warning_only(self):
        gate = derive_from_structure_validation(
            {
                "checks": [
                    {"check": "Has chapters", "status": "WARN", "detail": "0 chapters"},
                ],
                "passed": 0,
                "total": 1,
            }
        )
        assert gate.status == "WARN"
        assert gate.findings[0].code == "STRUCTURE_INCOMPLETE"
