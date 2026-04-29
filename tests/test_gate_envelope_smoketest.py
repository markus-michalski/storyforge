"""End-to-end smoketest for the GateResult envelope (Issue #122).

Exercises every checker MCP tool against a real on-disk fixture book and
asserts the uniform ``gate`` envelope is present and well-shaped.  The
aggregator (``run_quality_gates``) is also covered.

Each checker test uses ``monkeypatch`` to stub ``routers._app.load_config`` so
the tool reads from a temporary content_root.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.chapters import verify_tactical_setup
from routers.gates import (
    check_memoir_consent,
    run_quality_gates,
    scan_manuscript,
    validate_book_structure,
    validate_timeline_consistency,
    verify_callbacks,
)


REQUIRED_GATE_KEYS = {"status", "reasons", "findings", "metadata"}
ALLOWED_STATUSES = {"PASS", "WARN", "FAIL"}


def _assert_gate_envelope(payload: dict, *, name: str) -> dict:
    """Common assertions for a tool that returns a wrap_legacy() envelope."""
    assert "gate" in payload, f"{name}: missing 'gate' envelope"
    gate = payload["gate"]
    assert REQUIRED_GATE_KEYS.issubset(gate.keys()), f"{name}: gate keys = {sorted(gate.keys())}"
    assert gate["status"] in ALLOWED_STATUSES, f"{name}: bad status {gate['status']!r}"
    assert isinstance(gate["reasons"], list)
    assert isinstance(gate["findings"], list)
    assert isinstance(gate["metadata"], dict)
    for f in gate["findings"]:
        assert {"code", "message", "severity"}.issubset(f.keys()), f"{name}: finding shape = {sorted(f.keys())}"
        assert f["severity"] in ALLOWED_STATUSES
    return gate


# ---------------------------------------------------------------------------
# Fixture book
# ---------------------------------------------------------------------------


def _write_fiction_book(content_root: Path, slug: str = "demo-book") -> Path:
    """Build a minimal fiction book with all directories the checkers expect."""
    book = content_root / "projects" / slug
    (book / "plot").mkdir(parents=True)
    (book / "characters").mkdir()
    (book / "world").mkdir()
    (book / "research").mkdir()
    (book / "chapters" / "01-opening").mkdir(parents=True)

    (book / "README.md").write_text(
        "---\nslug: demo-book\nbook_category: fiction\n---\n\n# Demo Book\n",
        encoding="utf-8",
    )
    (book / "synopsis.md").write_text("Synopsis: a hero faces a choice.\n", encoding="utf-8")
    (book / "plot" / "outline.md").write_text("# Outline\n", encoding="utf-8")
    (book / "plot" / "timeline.md").write_text(
        "| Day | Chapter | Event |\n|---|---|---|\n| Day 1 | 1 | Opening scene |\n",
        encoding="utf-8",
    )
    (book / "characters" / "INDEX.md").write_text("# Characters\n", encoding="utf-8")
    (book / "world" / "setting.md").write_text("# Setting\n", encoding="utf-8")

    chapter_readme = book / "chapters" / "01-opening" / "README.md"
    chapter_readme.write_text(
        "# Chapter 1\n\n## Chapter Timeline\n\nDay 1, morning.\n",
        encoding="utf-8",
    )
    chapter_draft = book / "chapters" / "01-opening" / "draft.md"
    chapter_draft.write_text(
        "The hero walked through the field. Birds sang above the road.\n"
        "He thought of the choice ahead. The morning was clear.\n",
        encoding="utf-8",
    )

    (book / "CLAUDE.md").write_text(
        "# Book CLAUDE.md\n\n## Rules\n\n## Callback Register\n\n_No callbacks yet._\n",
        encoding="utf-8",
    )
    return book


def _write_memoir_book(content_root: Path, slug: str = "demo-memoir") -> Path:
    book = content_root / "projects" / slug
    (book / "plot").mkdir(parents=True)
    (book / "people").mkdir()
    (book / "research").mkdir()
    (book / "chapters" / "01-childhood").mkdir(parents=True)
    (book / "characters").mkdir()  # legacy fallback honored by indexer
    (book / "world").mkdir()

    (book / "README.md").write_text(
        "---\nslug: demo-memoir\nbook_category: memoir\n---\n\n# Demo Memoir\n",
        encoding="utf-8",
    )
    (book / "synopsis.md").write_text("Memoir synopsis.\n", encoding="utf-8")
    (book / "plot" / "outline.md").write_text("# Outline\n", encoding="utf-8")
    (book / "characters" / "INDEX.md").write_text("# (legacy)\n", encoding="utf-8")
    (book / "world" / "setting.md").write_text("# Setting\n", encoding="utf-8")
    (book / "chapters" / "01-childhood" / "draft.md").write_text(
        "I was eight. The kitchen smelled of bread.\n", encoding="utf-8"
    )
    (book / "chapters" / "01-childhood" / "README.md").write_text("# Ch 1\n", encoding="utf-8")

    # Two people: one with consent OK, one refused → expected FAIL gate
    (book / "people" / "alice.md").write_text(
        "---\n"
        "slug: alice\n"
        "person_category: public-figure\n"
        "consent_status: not-required\n"
        "anonymization: none\n"
        "---\n\n# Alice\n",
        encoding="utf-8",
    )
    (book / "people" / "bob.md").write_text(
        "---\n"
        "slug: bob\n"
        "person_category: private-living-person\n"
        "consent_status: refused\n"
        "anonymization: none\n"
        "---\n\n# Bob\n",
        encoding="utf-8",
    )
    return book


@pytest.fixture
def fiction_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    content_root = tmp_path / "content"
    _write_fiction_book(content_root)
    config = {"paths": {"content_root": str(content_root)}}
    monkeypatch.setattr(_app, "load_config", lambda: config)
    return config


@pytest.fixture
def memoir_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    content_root = tmp_path / "content"
    _write_memoir_book(content_root)
    config = {"paths": {"content_root": str(content_root)}}
    monkeypatch.setattr(_app, "load_config", lambda: config)
    return config


# ---------------------------------------------------------------------------
# Per-checker envelope assertions
# ---------------------------------------------------------------------------


class TestGateEnvelopePerChecker:
    def test_scan_manuscript_envelope(self, fiction_config: dict) -> None:
        result = json.loads(scan_manuscript("demo-book", write_report=False))
        gate = _assert_gate_envelope(result, name="scan_manuscript")
        # Tiny draft, no rule violations expected → PASS.
        assert gate["status"] == "PASS"
        # Legacy keys preserved.
        assert "findings" in result
        assert "chapters_scanned" in result

    def test_validate_timeline_envelope(self, fiction_config: dict) -> None:
        result = json.loads(validate_timeline_consistency("demo-book"))
        gate = _assert_gate_envelope(result, name="validate_timeline_consistency")
        # Minimal anchor present, no drift → PASS or WARN allowed.
        assert gate["status"] in {"PASS", "WARN"}
        assert "missing_anchors" in result

    def test_verify_callbacks_envelope(self, fiction_config: dict) -> None:
        result = json.loads(verify_callbacks("demo-book"))
        gate = _assert_gate_envelope(result, name="verify_callbacks")
        # Empty callback register → PASS.
        assert gate["status"] == "PASS"
        assert "satisfied" in result

    def test_validate_book_structure_envelope(self, fiction_config: dict) -> None:
        result = json.loads(validate_book_structure("demo-book"))
        gate = _assert_gate_envelope(result, name="validate_book_structure")
        assert gate["status"] in {"PASS", "WARN", "FAIL"}
        assert "checks" in result and "verdict" in result

    def test_check_memoir_consent_envelope_pass(self, memoir_config: dict, tmp_path: Path) -> None:
        # memoir-consent on a memoir book with one refused person → FAIL
        result = json.loads(check_memoir_consent("demo-memoir"))
        gate = _assert_gate_envelope(result, name="check_memoir_consent")
        assert gate["status"] == "FAIL"
        assert any(f["code"] == "CONSENT_FAIL" for f in gate["findings"])
        assert result["overall"] == "FAIL"  # legacy key still set

    def test_check_memoir_consent_rejects_fiction(self, fiction_config: dict) -> None:
        result = json.loads(check_memoir_consent("demo-book"))
        # Fiction book → tool returns error, no gate is emitted by design.
        assert "error" in result

    def test_verify_tactical_setup_envelope(self, fiction_config: dict) -> None:
        result = json.loads(
            verify_tactical_setup(
                "demo-book",
                scene_outline_text="Two characters walk through the woods.",
                characters_present=[],
            )
        )
        gate = _assert_gate_envelope(result, name="verify_tactical_setup")
        assert gate["status"] in {"PASS", "WARN"}


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


class TestRunQualityGates:
    def test_fiction_aggregator_emits_envelope(self, fiction_config: dict) -> None:
        result = json.loads(run_quality_gates("demo-book"))
        assert "gate" in result, "aggregator missing gate envelope"
        gate = result["gate"]
        assert REQUIRED_GATE_KEYS.issubset(gate.keys())
        assert gate["status"] in ALLOWED_STATUSES
        # All per-checker results preserved for drill-down.
        assert "results" in result
        assert "structure" in result["results"]
        assert "manuscript" in result["results"]
        assert "timeline" in result["results"]
        assert "callbacks" in result["results"]
        # Fiction book skips the consent checker.
        assert "consent" not in result["results"]
        # Aggregator metadata records which checkers ran.
        assert "checkers_run" in gate["metadata"]

    def test_memoir_aggregator_includes_consent(self, memoir_config: dict) -> None:
        result = json.loads(run_quality_gates("demo-memoir"))
        gate = result["gate"]
        assert "consent" in result["results"]
        # Refused-consent person → consent gate FAIL → aggregator FAIL.
        assert gate["status"] == "FAIL"

    def test_aggregator_handles_missing_book(self, fiction_config: dict) -> None:
        result = json.loads(run_quality_gates("does-not-exist"))
        assert "error" in result


# ---------------------------------------------------------------------------
# Skill alignment with the gate contract
# ---------------------------------------------------------------------------

PLUGIN_ROOT = Path(__file__).resolve().parent.parent

# Skills that call an MCP tool which already emits the gate envelope: the
# SKILL.md must reference the envelope so the skill author surfaces it.
SKILLS_REFERENCING_GATE_ENVELOPE = {
    "manuscript-checker",
    "memoir-ethics-checker",
}

# Skills that produce their own report (no underlying MCP gate tool): they
# must end the report with a "VERDICT: PASS | WARN | FAIL" line so an
# aggregator can parse the verdict without re-implementing the rubric.
SKILLS_REQUIRING_VERDICT_LINE = {
    "chapter-reviewer",
    "continuity-checker",
    "voice-checker",
    "sensitivity-reader",
}


class TestSkillAlignment:
    @pytest.mark.parametrize("skill_name", sorted(SKILLS_REFERENCING_GATE_ENVELOPE))
    def test_skill_references_gate_envelope(self, skill_name: str) -> None:
        path = PLUGIN_ROOT / "skills" / skill_name / "SKILL.md"
        assert path.is_file(), f"missing {path}"
        text = path.read_text(encoding="utf-8")
        assert "gate" in text and ("gate.status" in text or '"gate"' in text), (
            f"{skill_name}: SKILL.md must document the gate envelope"
        )

    @pytest.mark.parametrize("skill_name", sorted(SKILLS_REQUIRING_VERDICT_LINE))
    def test_skill_emits_verdict_line(self, skill_name: str) -> None:
        path = PLUGIN_ROOT / "skills" / skill_name / "SKILL.md"
        assert path.is_file(), f"missing {path}"
        text = path.read_text(encoding="utf-8")
        assert "VERDICT: PASS | WARN | FAIL" in text, (
            f"{skill_name}: SKILL.md must instruct the skill to end its "
            f"report with 'VERDICT: PASS | WARN | FAIL' for aggregator parsing"
        )
