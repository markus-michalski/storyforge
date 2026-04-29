"""Derive uniform ``GateResult`` envelopes from legacy checker outputs.

Each helper here takes the dict that an existing checker module already
returns and produces a ``GateResult`` that the MCP layer can attach via
``wrap_legacy``.  Keeping the derivation logic in one place means:

- the MCP tool stays a thin wrapper,
- the derivation rules are unit-testable without running the underlying
  checker, and
- a future refactor that pushes ``GateResult`` into the impl modules
  themselves (and removes these helpers) has a single place to delete.

Status mapping is conservative:

- "PASS"  — no findings, no overdue items, no FAIL-tier signals
- "WARN"  — findings exist or info-severity issues surfaced, nothing blocking
- "FAIL"  — at least one signal that should block the next workflow step
"""

from __future__ import annotations

from typing import Any, Mapping

from tools.shared.gate_result import Finding, GateResult


# ----------------------------------------------------------------------
# Manuscript checker (scan_repetitions)
# ----------------------------------------------------------------------


def derive_from_manuscript_scan(result: Mapping[str, Any]) -> GateResult:
    """Derive a gate from the manuscript_checker.scan_repetitions output.

    Status logic:
    - FAIL when any finding has category ``book_rule_violation`` (CLAUDE.md
      rule explicitly broken — highest severity by design).
    - WARN when other findings exist.
    - PASS when no findings.
    """
    findings_raw = list(result.get("findings") or [])

    rule_violations = [f for f in findings_raw if f.get("category") == "book_rule_violation"]

    metadata = {
        "chapters_scanned": result.get("chapters_scanned", 0),
        "findings_count": len(findings_raw),
        "rule_violations": len(rule_violations),
    }

    if not findings_raw:
        return GateResult.passed(
            reasons=["No prose-quality issues found across scanned chapters."],
            metadata=metadata,
        )

    findings: list[Finding] = []
    for raw in findings_raw[:50]:  # cap to keep envelope reasonable
        category = raw.get("category", "manuscript_finding")
        severity_raw = raw.get("severity")
        if category == "book_rule_violation":
            severity = "FAIL"
        elif severity_raw == "high":
            severity = "WARN"
        else:
            severity = "WARN"
        location: dict[str, Any] = {}
        occurrences = raw.get("occurrences") or []
        if occurrences:
            first = occurrences[0]
            location = {
                "chapter": first.get("chapter"),
                "line": first.get("line"),
                "occurrence_count": len(occurrences),
            }
        findings.append(
            Finding(
                code=category.upper(),
                message=str(raw.get("phrase") or raw.get("message") or "(unspecified)"),
                severity=severity,  # type: ignore[arg-type]
                location=location,
            )
        )

    if rule_violations:
        return GateResult.failed(
            reasons=[
                f"{len(rule_violations)} CLAUDE.md rule violation(s) found.",
                f"{len(findings_raw) - len(rule_violations)} other prose finding(s).",
            ],
            findings=findings,
            metadata=metadata,
        )

    return GateResult.warned(
        reasons=[f"{len(findings_raw)} prose finding(s) need attention."],
        findings=findings,
        metadata=metadata,
    )


# ----------------------------------------------------------------------
# Timeline validator
# ----------------------------------------------------------------------


def derive_from_timeline_validation(result: Mapping[str, Any]) -> GateResult:
    """Derive a gate from validate_timeline output.

    Status logic:
    - PASS when no findings and no missing anchors.
    - WARN when missing anchors only (incomplete READMEs, but no drift).
    - FAIL when any drift findings exist (story-day mismatch).
    """
    findings_raw = list(result.get("findings") or [])
    missing = list(result.get("missing_anchors") or [])

    metadata = {
        "chapters_checked": result.get("chapters_checked", 0),
        "calendar_built": result.get("calendar_built", False),
        "findings_count": len(findings_raw),
        "missing_anchors_count": len(missing),
    }

    if not findings_raw and not missing:
        return GateResult.passed(
            reasons=["Timeline anchors consistent across all checked chapters."],
            metadata=metadata,
        )

    findings: list[Finding] = []
    for raw in findings_raw[:50]:
        findings.append(
            Finding(
                code=str(raw.get("code") or "TIMELINE_DRIFT").upper(),
                message=str(raw.get("message") or raw.get("phrase") or "(unspecified)"),
                severity="FAIL",
                location={
                    "chapter": raw.get("chapter"),
                    "line": raw.get("line"),
                },
            )
        )

    if findings_raw:
        return GateResult.failed(
            reasons=[f"{len(findings_raw)} timeline drift finding(s) detected."],
            findings=findings,
            metadata=metadata,
        )

    return GateResult.warned(
        reasons=[f"{len(missing)} chapter(s) missing a parseable Chapter Timeline anchor."],
        findings=findings,
        metadata=metadata,
    )


# ----------------------------------------------------------------------
# Callback validator
# ----------------------------------------------------------------------


def derive_from_callback_verification(result: Mapping[str, Any]) -> GateResult:
    """Derive a gate from verify_callbacks output.

    Status logic:
    - PASS when no callbacks registered, or all satisfied.
    - WARN when only ``deferred`` items exist.
    - FAIL when ``potentially_dropped`` items exist (overdue or silent
      must-not-forget callback).
    """
    satisfied = list(result.get("satisfied") or [])
    deferred = list(result.get("deferred") or [])
    dropped = list(result.get("potentially_dropped") or [])

    metadata = {
        "callbacks_checked": result.get("callbacks_checked", 0),
        "satisfied": len(satisfied),
        "deferred": len(deferred),
        "potentially_dropped": len(dropped),
    }

    if not (deferred or dropped):
        return GateResult.passed(
            reasons=["All registered callbacks satisfied."],
            metadata=metadata,
        )

    findings: list[Finding] = []
    for entry in dropped[:30]:
        findings.append(
            Finding(
                code="CALLBACK_DROPPED",
                message=f"{entry.get('name', '(unnamed)')}: {entry.get('warning', 'overdue or silent')}",
                severity="FAIL",
                location={"last_appeared_ch": entry.get("last_appeared_ch")},
            )
        )
    for entry in deferred[:30]:
        findings.append(
            Finding(
                code="CALLBACK_DEFERRED",
                message=f"{entry.get('name', '(unnamed)')}: {entry.get('status', 'pending')}",
                severity="WARN",
                location={"chapters_since": entry.get("chapters_since")},
            )
        )

    if dropped:
        return GateResult.failed(
            reasons=[f"{len(dropped)} potentially dropped callback(s)."],
            findings=findings,
            metadata=metadata,
        )

    return GateResult.warned(
        reasons=[f"{len(deferred)} deferred callback(s) — track or resolve."],
        findings=findings,
        metadata=metadata,
    )


# ----------------------------------------------------------------------
# Memoir consent checker
# ----------------------------------------------------------------------


def derive_from_consent_check(result: Mapping[str, Any]) -> GateResult:
    """Derive a gate from memoir_ethics.check_consent output.

    Status comes directly from the legacy ``overall`` field — that field is
    already FAIL > WARN > PASS aggregation across people.
    """
    overall = str(result.get("overall") or "PASS").upper()
    pass_count = int(result.get("pass_count") or 0)
    warn_count = int(result.get("warn_count") or 0)
    fail_count = int(result.get("fail_count") or 0)

    metadata = {
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "people_total": pass_count + warn_count + fail_count,
    }

    findings: list[Finding] = []
    for person in result.get("people") or []:
        verdict = str(person.get("verdict") or "PASS").upper()
        if verdict == "PASS":
            continue
        slug = person.get("slug") or person.get("name") or "(unknown)"
        findings.append(
            Finding(
                code=f"CONSENT_{verdict}",
                message=f"{slug}: {person.get('reason', '(no reason recorded)')}",
                severity=verdict,  # type: ignore[arg-type]
                location={"person": slug},
            )
        )

    if overall == "FAIL":
        return GateResult.failed(
            reasons=[f"{fail_count} person profile(s) at FAIL severity — publication blocked."],
            findings=findings,
            metadata=metadata,
        )
    if overall == "WARN":
        return GateResult.warned(
            reasons=[f"{warn_count} person profile(s) need attention before publication."],
            findings=findings,
            metadata=metadata,
        )
    return GateResult.passed(
        reasons=[f"All {pass_count} person profile(s) cleared."],
        metadata=metadata,
    )


# ----------------------------------------------------------------------
# Tactical setup
# ----------------------------------------------------------------------


def derive_from_tactical_setup(result: Mapping[str, Any]) -> GateResult:
    """Derive a gate from tactical_checker.verify_tactical_setup output."""
    passes = bool(result.get("passes"))
    warnings_raw = list(result.get("warnings") or [])

    metadata = {
        "warnings_count": len(warnings_raw),
        "characters_present": list(result.get("characters_present") or []),
    }

    findings: list[Finding] = []
    for w in warnings_raw:
        sev_raw = (w.get("severity") or "info").lower()
        severity = "WARN" if sev_raw == "warn" else "WARN"
        findings.append(
            Finding(
                code=f"TACTICAL_{sev_raw.upper()}",
                message=str(w.get("message", "(no message)")),
                severity=severity,  # type: ignore[arg-type]
            )
        )

    if passes and not warnings_raw:
        return GateResult.passed(
            reasons=["Tactical setup clears all sanity checks."],
            metadata=metadata,
        )
    if passes:
        return GateResult.warned(
            reasons=[f"{len(warnings_raw)} info-level note(s); scene still passes."],
            findings=findings,
            metadata=metadata,
        )
    return GateResult.warned(
        reasons=[f"{len(warnings_raw)} tactical warning(s) — review before writing."],
        findings=findings,
        metadata=metadata,
    )


# ----------------------------------------------------------------------
# Structure validator
# ----------------------------------------------------------------------


def derive_from_structure_validation(result: Mapping[str, Any]) -> GateResult:
    """Derive a gate from validate_book_structure legacy output."""
    checks = list(result.get("checks") or [])
    metadata = {
        "passed": int(result.get("passed", 0)),
        "total": int(result.get("total", 0)),
    }

    findings: list[Finding] = []
    fails: list[str] = []
    warns: list[str] = []
    for check in checks:
        status = str(check.get("status") or "").upper()
        name = str(check.get("check") or "(unnamed)")
        detail = str(check.get("detail") or "")
        if status == "FAIL":
            fails.append(name)
            findings.append(
                Finding(
                    code="STRUCTURE_MISSING",
                    message=f"{name}: missing or invalid",
                    severity="FAIL",
                    location={"check": name},
                )
            )
        elif status == "WARN":
            warns.append(name)
            findings.append(
                Finding(
                    code="STRUCTURE_INCOMPLETE",
                    message=f"{name}: {detail or 'incomplete'}",
                    severity="WARN",
                    location={"check": name},
                )
            )

    if fails:
        return GateResult.failed(
            reasons=[f"Required structure missing: {', '.join(fails)}"],
            findings=findings,
            metadata=metadata,
        )
    if warns:
        return GateResult.warned(
            reasons=[f"Optional content incomplete: {', '.join(warns)}"],
            findings=findings,
            metadata=metadata,
        )
    return GateResult.passed(
        reasons=["All structural checks pass."],
        metadata=metadata,
    )


__all__ = [
    "derive_from_callback_verification",
    "derive_from_consent_check",
    "derive_from_manuscript_scan",
    "derive_from_structure_validation",
    "derive_from_tactical_setup",
    "derive_from_timeline_validation",
]
