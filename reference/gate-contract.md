---
title: Gate-Result contract for checker MCP tools
issue: "#122"
audience: skill authors, MCP tool authors
---

# Gate-Result contract

Every checker MCP tool returns a uniform `gate` envelope alongside its
legacy result keys. Skills and aggregators can rely on a single
machine-readable shape regardless of which checker produced the output.

## The envelope

```json
{
  "<legacy keys preserved>": "...",
  "gate": {
    "status": "PASS" | "WARN" | "FAIL",
    "reasons": ["human-readable reason 1", "..."],
    "findings": [
      {
        "code": "SHORT_IDENTIFIER",
        "message": "Human-readable description",
        "severity": "PASS" | "WARN" | "FAIL",
        "location": { "file": "...", "line": 42 }
      }
    ],
    "metadata": { "checker_specific": "extras" }
  }
}
```

`reasons` is plain text suitable for direct rendering. `findings` carry
structured detail, optionally with a `location` (chapter / file / line).
`metadata` holds checker-specific counts and references.

## Status semantics

| Status | Meaning |
|---|---|
| `PASS` | No issues — the gate clears. |
| `WARN` | Issues exist, but no workflow step should be blocked. |
| `FAIL` | At least one signal that should block the next step (e.g., publication). |

Aggregation is monotonic: `FAIL > WARN > PASS`. An aggregator that combines
multiple gates returns the worst observed status.

## Tools that emit a gate

| MCP tool | Status mapping |
|---|---|
| `scan_manuscript` | FAIL on any `book_rule_violation`; WARN on other findings; PASS otherwise. |
| `validate_timeline_consistency` | FAIL on any drift finding; WARN if anchors missing only; PASS when clean. |
| `verify_callbacks` | FAIL on `potentially_dropped`; WARN on `deferred`; PASS otherwise. |
| `check_memoir_consent` | Mirrors `overall` — FAIL > WARN > PASS across all people. |
| `verify_tactical_setup` | WARN when warnings exist; PASS when clean. |
| `validate_book_structure` | FAIL when any required check fails; WARN on optional warnings; PASS otherwise. |
| `run_pre_export_gates` | FAIL when blocking gate fails; WARN if non-blocking warnings; PASS otherwise. |
| `run_quality_gates` | Aggregator — runs all of the above for a book and returns one combined gate. |

## Aggregator: `run_quality_gates`

Calls every checker that applies to the book (memoir books additionally
get the consent gate) and returns:

```json
{
  "book_slug": "demo-book",
  "book_category": "fiction",
  "results": {
    "structure": { "status": "...", "...": "..." },
    "manuscript": { "status": "...", "...": "..." },
    "timeline": { "status": "...", "...": "..." },
    "callbacks": { "status": "...", "...": "..." }
  },
  "gate": {
    "status": "WARN",
    "reasons": ["..."],
    "findings": [],
    "metadata": {
      "book_slug": "demo-book",
      "book_category": "fiction",
      "checkers_run": ["structure", "manuscript", "timeline", "callbacks"]
    }
  }
}
```

Use this from any skill that wants a single signal — for example, a
`drafting → revision` transition that only proceeds when the aggregator
returns PASS.

## Backward compatibility

The envelope is **additive** — every legacy key returned by a checker is
preserved verbatim. Existing skills and tests that read `overall`,
`verdict`, `gates`, `findings`, etc. keep working. New code should prefer
the `gate` envelope.

## Adding a new checker

1. Implement the underlying logic in `tools/analysis/<name>.py`.
2. Add a derive helper in `tools/shared/gate_derivation.py`:
   `derive_from_<name>(legacy_dict) -> GateResult`.
3. In the MCP tool, return `wrap_legacy(legacy_dict, gate)`.
4. Add the new gate to `run_quality_gates` if it should run by default.
5. Add unit tests for the derive helper and an envelope assertion in
   `tests/test_gate_envelope_smoketest.py`.

## Schema reference

See `tools/shared/gate_result.py` for the full dataclass definition,
construction helpers (`GateResult.passed/warned/failed`), and the
`aggregate_gates` aggregator.
