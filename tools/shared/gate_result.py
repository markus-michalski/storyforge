"""Shared gate-result contract for StoryForge checker MCP tools (Issue #122).

A *gate* is a quality check that produces a verdict — PASS, WARN, or FAIL.
This module defines a uniform contract so aggregators (such as
``run_pre_export_gates`` and ``validate_book_structure``) can consume any
checker without category-specific glue, and so skills can rely on a single
machine-readable shape regardless of which checker produced it.

Schema
------

``GateResult``
    status   : "PASS" | "WARN" | "FAIL"
    reasons  : list[str]              human-readable, suitable for end-user output
    findings : list[Finding]          structured findings (file:line where applicable)
    metadata : dict                   checker-specific extras (counts, paths, ...)

``Finding``
    code     : str                    short identifier (e.g. "CONSENT_REFUSED")
    message  : str                    human-readable description
    severity : "PASS" | "WARN" | "FAIL"
    location : dict                   optional {"file": str, "line": int, ...}

Aggregation
-----------

``aggregate_status`` returns the worst status across an iterable
(FAIL > WARN > PASS).  ``aggregate_gates`` combines a list of GateResults
into a single GateResult, preserving findings and reasons in input order.

JSON serialization
------------------

``to_json_dict`` returns a plain dict suitable for ``json.dumps``.  All
existing checker tools that already return JSON shapes can preserve their
legacy keys and add ``gate`` as a top-level field — see ``wrap_legacy``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Mapping

GateStatus = Literal["PASS", "WARN", "FAIL"]

_STATUS_RANK: dict[str, int] = {"PASS": 0, "WARN": 1, "FAIL": 2}
_RANK_TO_STATUS: dict[int, GateStatus] = {0: "PASS", 1: "WARN", 2: "FAIL"}


@dataclass
class Finding:
    """A single structured finding produced by a checker."""

    code: str
    message: str
    severity: GateStatus = "WARN"
    location: dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }
        if self.location:
            out["location"] = dict(self.location)
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Finding":
        severity = _coerce_status(data.get("severity"), default="WARN")
        return cls(
            code=str(data.get("code", "")),
            message=str(data.get("message", "")),
            severity=severity,
            location=dict(data.get("location") or {}),
        )


@dataclass
class GateResult:
    """A uniform verdict envelope for any quality checker."""

    status: GateStatus = "PASS"
    reasons: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def passed(
        cls,
        reasons: Iterable[str] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "GateResult":
        return cls(
            status="PASS",
            reasons=list(reasons or []),
            metadata=dict(metadata or {}),
        )

    @classmethod
    def warned(
        cls,
        reasons: Iterable[str] | None = None,
        findings: Iterable[Finding] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "GateResult":
        return cls(
            status="WARN",
            reasons=list(reasons or []),
            findings=list(findings or []),
            metadata=dict(metadata or {}),
        )

    @classmethod
    def failed(
        cls,
        reasons: Iterable[str] | None = None,
        findings: Iterable[Finding] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "GateResult":
        return cls(
            status="FAIL",
            reasons=list(reasons or []),
            findings=list(findings or []),
            metadata=dict(metadata or {}),
        )

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_finding(self, finding: Finding) -> None:
        """Append a finding and escalate ``status`` to its severity if higher."""
        self.findings.append(finding)
        self.status = _max_status(self.status, finding.severity)

    def add_reason(self, reason: str) -> None:
        if reason:
            self.reasons.append(reason)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "status": self.status,
            "reasons": list(self.reasons),
            "findings": [f.to_json_dict() for f in self.findings],
        }
        if self.metadata:
            out["metadata"] = dict(self.metadata)
        else:
            out["metadata"] = {}
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GateResult":
        status = _coerce_status(data.get("status"), default="PASS")
        findings_raw = data.get("findings") or []
        findings = [Finding.from_dict(f) for f in findings_raw]
        return cls(
            status=status,
            reasons=list(data.get("reasons") or []),
            findings=findings,
            metadata=dict(data.get("metadata") or {}),
        )


# ----------------------------------------------------------------------
# Aggregation
# ----------------------------------------------------------------------


def aggregate_status(statuses: Iterable[str]) -> GateStatus:
    """Return the worst status across ``statuses`` (FAIL > WARN > PASS).

    An empty iterable returns ``"PASS"``.  Unknown values are skipped — they
    do not silently degrade the verdict.
    """
    worst = 0
    for raw in statuses:
        rank = _STATUS_RANK.get(str(raw).upper())
        if rank is None:
            continue
        if rank > worst:
            worst = rank
    return _RANK_TO_STATUS[worst]


def aggregate_gates(
    gates: Iterable[GateResult],
    metadata: Mapping[str, Any] | None = None,
) -> GateResult:
    """Combine multiple GateResults into one.

    Status uses ``aggregate_status``.  Reasons and findings are concatenated
    in input order.  ``metadata`` defaults to a dict containing per-input
    statuses keyed by index.
    """
    gates_list = list(gates)
    statuses = [g.status for g in gates_list]
    combined = GateResult(
        status=aggregate_status(statuses),
        reasons=[r for g in gates_list for r in g.reasons],
        findings=[f for g in gates_list for f in g.findings],
        metadata=dict(metadata or {"child_statuses": statuses}),
    )
    return combined


# ----------------------------------------------------------------------
# Backward-compat wrapper
# ----------------------------------------------------------------------


def wrap_legacy(legacy: Mapping[str, Any], gate: GateResult) -> dict[str, Any]:
    """Merge a legacy result dict with a ``gate`` envelope.

    The legacy keys are preserved verbatim — a checker can keep its existing
    JSON shape while adding the uniform contract under ``gate``.  When the
    legacy dict already has a ``gate`` key, it is overwritten.
    """
    out = dict(legacy)
    out["gate"] = gate.to_json_dict()
    return out


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------


def _coerce_status(raw: Any, default: GateStatus = "PASS") -> GateStatus:
    if raw is None:
        return default
    upper = str(raw).upper()
    if upper in _STATUS_RANK:
        return upper  # type: ignore[return-value]
    return default


def _max_status(a: GateStatus, b: GateStatus) -> GateStatus:
    return _RANK_TO_STATUS[max(_STATUS_RANK[a], _STATUS_RANK[b])]


__all__ = [
    "Finding",
    "GateResult",
    "GateStatus",
    "aggregate_gates",
    "aggregate_status",
    "wrap_legacy",
]
