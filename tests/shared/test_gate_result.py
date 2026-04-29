"""Unit tests for the shared GateResult contract (Issue #122)."""

from __future__ import annotations

import json

import pytest

from tools.shared.gate_result import (
    Finding,
    GateResult,
    aggregate_gates,
    aggregate_status,
    wrap_legacy,
)


class TestFinding:
    def test_serializes_with_minimal_fields(self):
        f = Finding(code="X", message="m")
        assert f.to_json_dict() == {"code": "X", "message": "m", "severity": "WARN"}

    def test_serializes_with_location(self):
        f = Finding(code="X", message="m", severity="FAIL", location={"file": "a.md", "line": 3})
        assert f.to_json_dict() == {
            "code": "X",
            "message": "m",
            "severity": "FAIL",
            "location": {"file": "a.md", "line": 3},
        }

    def test_round_trips_through_dict(self):
        original = Finding(code="X", message="m", severity="FAIL", location={"file": "a"})
        restored = Finding.from_dict(original.to_json_dict())
        assert restored == original

    def test_unknown_severity_is_coerced_to_warn(self):
        restored = Finding.from_dict({"code": "X", "message": "m", "severity": "bogus"})
        assert restored.severity == "WARN"


class TestGateResult:
    def test_default_is_pass(self):
        g = GateResult()
        assert g.status == "PASS"
        assert g.reasons == []
        assert g.findings == []
        assert g.metadata == {}

    def test_passed_factory(self):
        g = GateResult.passed(reasons=["ok"], metadata={"k": 1})
        assert g.status == "PASS"
        assert g.reasons == ["ok"]
        assert g.metadata == {"k": 1}

    def test_warned_and_failed_factories_set_status(self):
        assert GateResult.warned().status == "WARN"
        assert GateResult.failed().status == "FAIL"

    def test_add_finding_escalates_status(self):
        g = GateResult.passed()
        g.add_finding(Finding(code="X", message="m", severity="WARN"))
        assert g.status == "WARN"
        g.add_finding(Finding(code="Y", message="m", severity="FAIL"))
        assert g.status == "FAIL"

    def test_add_finding_does_not_downgrade_status(self):
        g = GateResult.failed()
        g.add_finding(Finding(code="X", message="m", severity="PASS"))
        assert g.status == "FAIL"

    def test_to_json_dict_is_json_serializable(self):
        g = GateResult.warned(
            reasons=["a"],
            findings=[Finding(code="X", message="m", severity="WARN", location={"file": "a"})],
            metadata={"count": 3},
        )
        # Round-trips through json without error and preserves shape.
        s = json.dumps(g.to_json_dict())
        restored = json.loads(s)
        assert restored["status"] == "WARN"
        assert restored["reasons"] == ["a"]
        assert restored["findings"][0]["code"] == "X"
        assert restored["metadata"] == {"count": 3}

    def test_to_json_dict_always_contains_metadata_key(self):
        g = GateResult.passed()
        out = g.to_json_dict()
        assert "metadata" in out
        assert out["metadata"] == {}

    def test_from_dict_round_trips(self):
        original = GateResult.failed(
            reasons=["bad"],
            findings=[Finding(code="X", message="m", severity="FAIL")],
            metadata={"k": "v"},
        )
        restored = GateResult.from_dict(original.to_json_dict())
        assert restored.status == original.status
        assert restored.reasons == original.reasons
        assert restored.findings == original.findings
        assert restored.metadata == original.metadata


class TestAggregateStatus:
    @pytest.mark.parametrize(
        "inputs,expected",
        [
            ([], "PASS"),
            (["PASS"], "PASS"),
            (["PASS", "WARN"], "WARN"),
            (["PASS", "FAIL"], "FAIL"),
            (["WARN", "FAIL", "PASS"], "FAIL"),
            (["WARN", "WARN"], "WARN"),
            (["bogus", "PASS"], "PASS"),  # unknown values skipped
            (["pass", "warn", "fail"], "FAIL"),  # case-insensitive
        ],
    )
    def test_aggregate_status(self, inputs, expected):
        assert aggregate_status(inputs) == expected


class TestAggregateGates:
    def test_empty_returns_pass(self):
        out = aggregate_gates([])
        assert out.status == "PASS"
        assert out.reasons == []
        assert out.findings == []

    def test_combines_reasons_and_findings_in_order(self):
        a = GateResult.warned(
            reasons=["a-reason"],
            findings=[Finding(code="A", message="ma", severity="WARN")],
        )
        b = GateResult.failed(
            reasons=["b-reason"],
            findings=[Finding(code="B", message="mb", severity="FAIL")],
        )
        out = aggregate_gates([a, b])
        assert out.status == "FAIL"
        assert out.reasons == ["a-reason", "b-reason"]
        assert [f.code for f in out.findings] == ["A", "B"]

    def test_default_metadata_records_child_statuses(self):
        a = GateResult.passed()
        b = GateResult.warned()
        out = aggregate_gates([a, b])
        assert out.metadata == {"child_statuses": ["PASS", "WARN"]}

    def test_custom_metadata_overrides_default(self):
        out = aggregate_gates(
            [GateResult.passed(), GateResult.failed()],
            metadata={"label": "pre-export"},
        )
        assert out.metadata == {"label": "pre-export"}


class TestWrapLegacy:
    def test_preserves_legacy_keys_and_adds_gate(self):
        legacy = {"book_slug": "demo", "overall": "PASS", "people": []}
        gate = GateResult.passed(metadata={"pass_count": 0})
        out = wrap_legacy(legacy, gate)
        assert out["book_slug"] == "demo"
        assert out["overall"] == "PASS"
        assert out["people"] == []
        assert out["gate"]["status"] == "PASS"
        assert out["gate"]["metadata"] == {"pass_count": 0}

    def test_overwrites_existing_gate_key(self):
        legacy = {"gate": {"status": "PASS"}}
        out = wrap_legacy(legacy, GateResult.failed(reasons=["bad"]))
        assert out["gate"]["status"] == "FAIL"
        assert out["gate"]["reasons"] == ["bad"]
