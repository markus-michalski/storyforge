"""All validation/quality-gate tools.

Bundles the per-checker entry points (manuscript scan, timeline,
callbacks, memoir consent, structure, chapter, pre-export) and the
``run_quality_gates`` aggregator that runs every applicable checker
and merges the results into one ``GateResult`` envelope.
"""

from __future__ import annotations

import json
from typing import Any

from tools.analysis.callback_validator import verify_callbacks as _verify_callbacks_impl
from tools.analysis.chapter_validator import (
    validate_chapter_path as _validate_chapter_path_impl,
)
from tools.analysis.manuscript_checker import render_report, scan_repetitions
from tools.analysis.memoir_ethics import check_consent as _check_consent_impl
from tools.analysis.timeline_validator import validate_timeline
from tools.shared.gate_derivation import (
    derive_from_callback_verification,
    derive_from_consent_check,
    derive_from_manuscript_scan,
    derive_from_structure_validation,
    derive_from_timeline_validation,
)
from tools.shared.gate_result import GateResult, aggregate_gates, wrap_legacy
from tools.shared.paths import (
    find_chapters,
    resolve_project_path,
    resolve_world_dir,
)
from tools.state.parsers import count_words_in_file, parse_frontmatter

from . import _app
from ._app import mcp


@mcp.tool()
def scan_manuscript(
    book_slug: str,
    min_occurrences: int = 2,
    write_report: bool = True,
    max_findings_per_category: int = 40,
) -> str:
    """Scan all chapter drafts of a book for prose-quality issues that only
    surface when the whole manuscript is read in one pass.

    Detects (all books):
    - Violations of rules from the book's CLAUDE.md (highest priority)
    - Curated clichés ("blood ran cold", "time stood still", ...)
    - Dialogue punctuation anomalies (Q-word opener + trailing period)
    - POV filter-word overuse per chapter ("felt", "noticed", "saw that", ...)
    - Per-chapter `-ly` adverb density
    - Cross-chapter repeated phrases: similes, character tells, blocking tics,
      structural patterns, signature phrases

    Memoir-only (book_category: memoir, Phase 3 #61):
    - Anonymization leaks — real name appearing despite people/ profile marking
    - Tidy-lesson endings — chapters that close on a moral instead of a moment
    - Reflective platitude density — retrospective commentary overuse per chapter
    - Timeline ambiguity — temporal hand-waving density per chapter
    - Real-people name consistency — inconsistent name forms across chapters

    Returns the structured findings as JSON. When `write_report` is true,
    also writes a human-readable Markdown report to
    `<book>/research/manuscript-report.md` and returns the path.

    Args:
        book_slug: The book project slug.
        min_occurrences: Minimum number of times a phrase must appear to count
            as a repetition. Default 2.
        write_report: When true, also writes the Markdown report file.
        max_findings_per_category: Cap per category to keep the report focused.
    """
    config = _app.load_config()
    book_path = resolve_project_path(config, book_slug)
    if not book_path.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found at {book_path}"})

    result = scan_repetitions(
        book_path=book_path,
        min_occurrences=min_occurrences,
        max_findings_per_category=max_findings_per_category,
    )

    report_path: str | None = None
    if write_report:
        research_dir = book_path / "research"
        research_dir.mkdir(parents=True, exist_ok=True)
        report_file = research_dir / "manuscript-report.md"
        report_file.write_text(render_report(result), encoding="utf-8")
        report_path = str(report_file)

    legacy = {
        "book_slug": book_slug,
        "chapters_scanned": result["chapters_scanned"],
        "findings_count": len(result["findings"]),
        "summary": result["summary"],
        "report_path": report_path,
        "findings": result["findings"],
    }
    gate = derive_from_manuscript_scan(result)
    return json.dumps(wrap_legacy(legacy, gate))


@mcp.tool()
def validate_timeline_consistency(book_slug: str) -> str:
    """Cross-validate chapter anchors and draft prose against plot/timeline.md.

    For each chapter that has a parseable ``## Chapter Timeline`` anchor in its
    README, scans the draft for relative time phrases (``yesterday``,
    ``tomorrow``, ``last week``, ``this morning``, ...) and checks whether the
    implied story-date matches the event calendar in ``plot/timeline.md``. Flags
    any drift greater than zero calendar days.

    Also reports chapters that are missing a parseable anchor so the writer
    knows which READMEs need a ``## Chapter Timeline`` section.

    Results are persisted to ``<book>/reports/timeline-validation.json`` and
    also returned as JSON.

    Args:
        book_slug: The book project slug.
    """
    config = _app.load_config()
    book_path = resolve_project_path(config, book_slug)
    if not book_path.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found at {book_path}"})
    try:
        result = validate_timeline(book_path)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc), "book_slug": book_slug})
    gate = derive_from_timeline_validation(result)
    return json.dumps(wrap_legacy(result, gate), indent=2, ensure_ascii=False)


@mcp.tool()
def verify_callbacks(book_slug: str) -> str:
    """Check the book's Callback Register against all drafted chapters.

    Parses ``## Callback Register`` from the book's CLAUDE.md and searches
    each drafted chapter for every registered callback name and its derived
    keywords.

    Returns three status buckets:
    - ``satisfied``           — callback found in at least one chapter, no overdue deadline
    - ``deferred``            — callback never appeared, or silent without a must-not-forget flag
    - ``potentially_dropped`` — expected-return deadline passed without appearance,
                                OR must-not-forget callback silent for >10 chapters

    Args:
        book_slug: The book project slug.
    """
    config = _app.load_config()
    book_path = resolve_project_path(config, book_slug)
    if not book_path.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found at {book_path}"})

    claudemd_path = book_path / "CLAUDE.md"
    if not claudemd_path.exists():
        return json.dumps({
            "error": f"No CLAUDE.md found for '{book_slug}'. Run init_book_claudemd first.",
        })

    claudemd_text = claudemd_path.read_text(encoding="utf-8")
    result = _verify_callbacks_impl(book_path, claudemd_text)
    gate = derive_from_callback_verification(result)
    return json.dumps(wrap_legacy(result, gate))


@mcp.tool()
def check_memoir_consent(book_slug: str) -> str:
    """Check consent status and ethics risk for all people in a memoir book.

    Reads every profile in ``people/`` and classifies each person as:
    - PASS  — confirmed-consent or not-required
    - WARN  — pending, not-asking, missing or unknown consent_status or
              person_category (incomplete profile)
    - FAIL  — refused (person explicitly declined — publication blocked)

    Overall verdict: FAIL beats WARN beats PASS.

    Returns a JSON object with:
        book_slug    — slug string
        overall      — "PASS" | "WARN" | "FAIL"
        people       — per-person list with verdict + reason
        pass_count   — int
        warn_count   — int
        fail_count   — int

    Only runs on memoir books (book_category: memoir). Returns an error
    for fiction books.

    Args:
        book_slug: The book project slug.
    """
    config = _app.load_config()
    book_path = resolve_project_path(config, book_slug)
    if not book_path.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found at {book_path}"})
    try:
        result = _check_consent_impl(book_path)
    except ValueError as exc:
        return json.dumps({"error": str(exc), "book_slug": book_slug})
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc), "book_slug": book_slug})
    gate = derive_from_consent_check(result)
    return json.dumps(wrap_legacy(result, gate))


@mcp.tool()
def validate_chapter(book_slug: str, chapter_slug: str) -> str:
    """Validate a chapter's draft.md against the same rules the PostToolUse
    linter hook applies (#119).

    Runs the full validator pipeline — book CLAUDE.md banlist, author
    vocabulary, POV-knowledge boundary, time-anchor relative phrases,
    meta-narrative leakage, AI-tells, and sentence-variance — and
    returns the findings plus a uniform ``gate`` envelope.

    Status mapping (per the gate contract — see
    ``reference/gate-contract.md``):

    - **FAIL** when the chapter has blocking findings AND the resolved
      linter mode is ``strict`` (the hook would reject the write).
    - **WARN** when findings exist but the hook would not block (warn
      mode, or only warn-severity findings).
    - **PASS** when no findings.

    Args:
        book_slug: The book project slug.
        chapter_slug: The chapter slug (directory name under
            ``chapters/``, e.g. ``01-opening``).
    """
    config = _app.load_config()
    book_path = resolve_project_path(config, book_slug)
    if not book_path.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found at {book_path}"})

    draft_path = book_path / "chapters" / chapter_slug / "draft.md"
    if not draft_path.is_file():
        return json.dumps({
            "error": f"Chapter draft not found at {draft_path}",
            "book_slug": book_slug,
            "chapter_slug": chapter_slug,
        })

    result = _validate_chapter_path_impl(str(draft_path))
    payload = result.to_json_dict()
    payload["book_slug"] = book_slug
    payload["chapter_slug"] = chapter_slug
    return json.dumps(payload)


@mcp.tool()
def validate_book_structure(book_slug: str) -> str:
    """Validate book project structure completeness."""
    config = _app.load_config()
    project_dir = resolve_project_path(config, book_slug)

    if not project_dir.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    checks = []

    # Issue #17: accept aliases (worldbuilding/, world-building/) for the
    # world directory so non-canonical scaffolds still validate.
    world_dir = resolve_world_dir(project_dir) or (project_dir / "world")
    world_setting = world_dir / "setting.md"

    # Required files
    for name, path in [
        ("README.md", project_dir / "README.md"),
        ("synopsis.md", project_dir / "synopsis.md"),
        ("plot/outline.md", project_dir / "plot" / "outline.md"),
        ("characters/INDEX.md", project_dir / "characters" / "INDEX.md"),
        (f"{world_dir.name}/setting.md", world_setting),
    ]:
        checks.append({"check": name, "status": "PASS" if path.exists() else "FAIL"})

    # Chapter checks
    chapters = find_chapters(config, book_slug)
    checks.append({
        "check": "Has chapters",
        "status": "PASS" if chapters else "WARN",
        "detail": f"{len(chapters)} chapters found",
    })

    # Character checks
    chars = list((project_dir / "characters").glob("*.md"))
    char_count = len([c for c in chars if c.name != "INDEX.md"])
    checks.append({
        "check": "Has characters",
        "status": "PASS" if char_count > 0 else "WARN",
        "detail": f"{char_count} characters found",
    })

    passed = sum(1 for c in checks if c["status"] == "PASS")
    total = len(checks)

    legacy = {
        "book": book_slug,
        "checks": checks,
        "passed": passed,
        "total": total,
        "verdict": "PASS" if passed == total else "NEEDS WORK",
    }
    gate = derive_from_structure_validation(legacy)
    return json.dumps(wrap_legacy(legacy, gate))


@mcp.tool()
def run_pre_export_gates(book_slug: str) -> str:
    """Run quality gates before export."""
    state = _app._cache.get()
    book = state.get("books", {}).get(book_slug)
    if not book:
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    gates = []

    # All chapters must be Final
    chapters = book.get("chapters_data", {})
    non_final = [s for s, c in chapters.items() if c.get("status") != "Final"]
    gates.append({
        "gate": "All chapters Final",
        "status": "FAIL" if non_final else "PASS",
        "blocking": True,
        "detail": f"Not final: {', '.join(non_final)}" if non_final else "All final",
    })

    # Has at least one chapter
    gates.append({
        "gate": "Has chapters",
        "status": "PASS" if chapters else "FAIL",
        "blocking": True,
        "detail": f"{len(chapters)} chapters",
    })

    # Word count check
    total_words = book.get("total_words", 0)
    target = book.get("target_word_count", 0)
    word_ok = total_words >= target * 0.8 if target else total_words > 0
    gates.append({
        "gate": "Word count target",
        "status": "PASS" if word_ok else "WARN",
        "blocking": False,
        "detail": f"{total_words}/{target} words ({round(total_words/target*100) if target else 0}%)",
    })

    # Has synopsis
    config = _app.load_config()
    synopsis = resolve_project_path(config, book_slug) / "synopsis.md"
    synopsis_words = count_words_in_file(synopsis) if synopsis.exists() else 0
    gates.append({
        "gate": "Synopsis written",
        "status": "PASS" if synopsis_words > 50 else "WARN",
        "blocking": False,
        "detail": f"{synopsis_words} words",
    })

    blocking_fails = [g for g in gates if g["blocking"] and g["status"] == "FAIL"]
    verdict = "BLOCKED" if blocking_fails else "READY"

    # Build the uniform gate envelope. Blocking failures map to FAIL,
    # non-blocking warnings map to WARN, otherwise PASS.
    if blocking_fails:
        envelope = GateResult.failed(
            reasons=[f"Export blocked by {len(blocking_fails)} gate(s)."],
            metadata={"verdict": verdict, "blocking_fails": len(blocking_fails)},
        )
    elif any(g["status"] == "WARN" for g in gates):
        envelope = GateResult.warned(
            reasons=["Ready for export, but optional gates have warnings."],
            metadata={"verdict": verdict},
        )
    else:
        envelope = GateResult.passed(
            reasons=["All export gates pass."],
            metadata={"verdict": verdict},
        )

    legacy = {
        "book": book_slug,
        "gates": gates,
        "verdict": verdict,
        "message": f"{'Export blocked by ' + str(len(blocking_fails)) + ' gate(s)' if blocking_fails else 'Ready for export'}",
    }
    return json.dumps(wrap_legacy(legacy, envelope))


@mcp.tool()
def run_quality_gates(book_slug: str) -> str:
    """Run every available quality checker for a book and aggregate the results.

    Calls each checker that produces a ``GateResult``-shaped output and
    returns one combined envelope.  Used by skills that want a single
    pass/warn/fail signal for a book without orchestrating each checker
    individually.

    Per-checker results are preserved in ``results[<name>]`` so callers
    can still drill into individual findings.

    Args:
        book_slug: The book project slug.
    """
    config = _app.load_config()
    book_path = resolve_project_path(config, book_slug)
    if not book_path.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found at {book_path}"})

    # Resolve book_category from disk (README frontmatter) — more robust than
    # relying on the state cache, which may be empty for freshly scaffolded
    # books or stale during quick edits.
    book_category = "fiction"
    readme = book_path / "README.md"
    if readme.is_file():
        meta, _ = parse_frontmatter(readme.read_text(encoding="utf-8"))
        book_category = str(meta.get("book_category") or "fiction")

    per_gate: dict[str, dict[str, Any]] = {}
    gates: list[GateResult] = []

    # --- Structure ---------------------------------------------------
    structure_legacy = json.loads(validate_book_structure(book_slug))
    if "gate" in structure_legacy:
        per_gate["structure"] = structure_legacy["gate"]
        gates.append(GateResult.from_dict(structure_legacy["gate"]))

    # --- Manuscript scan --------------------------------------------
    try:
        scan_result = scan_repetitions(book_path=book_path)
        scan_gate = derive_from_manuscript_scan(scan_result)
        per_gate["manuscript"] = scan_gate.to_json_dict()
        gates.append(scan_gate)
    except Exception as exc:  # noqa: BLE001
        per_gate["manuscript"] = {
            "status": "WARN",
            "reasons": [f"manuscript scan skipped: {exc}"],
            "findings": [],
            "metadata": {},
        }

    # --- Timeline ---------------------------------------------------
    try:
        timeline_result = validate_timeline(book_path)
        timeline_gate = derive_from_timeline_validation(timeline_result)
        per_gate["timeline"] = timeline_gate.to_json_dict()
        gates.append(timeline_gate)
    except Exception as exc:  # noqa: BLE001
        per_gate["timeline"] = {
            "status": "WARN",
            "reasons": [f"timeline validation skipped: {exc}"],
            "findings": [],
            "metadata": {},
        }

    # --- Callbacks (only if CLAUDE.md exists) -----------------------
    claudemd_path = book_path / "CLAUDE.md"
    if claudemd_path.exists():
        try:
            cb_result = _verify_callbacks_impl(
                book_path, claudemd_path.read_text(encoding="utf-8")
            )
            cb_gate = derive_from_callback_verification(cb_result)
            per_gate["callbacks"] = cb_gate.to_json_dict()
            gates.append(cb_gate)
        except Exception as exc:  # noqa: BLE001
            per_gate["callbacks"] = {
                "status": "WARN",
                "reasons": [f"callback verification skipped: {exc}"],
                "findings": [],
                "metadata": {},
            }

    # --- Memoir consent (memoir only) -------------------------------
    if book_category == "memoir":
        try:
            consent_result = _check_consent_impl(book_path)
            consent_gate = derive_from_consent_check(consent_result)
            per_gate["consent"] = consent_gate.to_json_dict()
            gates.append(consent_gate)
        except (ValueError, FileNotFoundError) as exc:
            per_gate["consent"] = {
                "status": "WARN",
                "reasons": [f"consent check skipped: {exc}"],
                "findings": [],
                "metadata": {},
            }

    aggregated = aggregate_gates(
        gates,
        metadata={
            "book_slug": book_slug,
            "book_category": book_category,
            "checkers_run": list(per_gate.keys()),
        },
    )

    return json.dumps({
        "book_slug": book_slug,
        "book_category": book_category,
        "results": per_gate,
        "gate": aggregated.to_json_dict(),
    })
