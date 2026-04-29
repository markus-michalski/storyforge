"""Tests for tools.analysis.chapter_validator (Issue #119).

The hook tests in ``tests/test_hooks.py`` exercise the underlying
scanners through the hook's re-exports; this file covers the new
``validate_chapter_path`` API and ``ValidationResult`` envelope, and the
gate translation.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.analysis.chapter_validator import (
    DEFAULT_MODE,
    Finding,
    SEVERITY_BLOCK,
    SEVERITY_WARN,
    ValidationResult,
    resolve_mode,
    validate_chapter,
    validate_chapter_path,
)


def _write_book(tmp_path: Path, *, frontmatter_mode: str | None = None) -> Path:
    """Build a minimal book with a chapter directory ready for the validator."""
    book = tmp_path / "demo-book"
    (book / "chapters" / "01-opening").mkdir(parents=True)
    (book / "characters").mkdir()
    (book / "world").mkdir()

    fm = ""
    if frontmatter_mode is not None:
        fm = f"---\nlinter_mode: {frontmatter_mode}\n---\n\n"
    (book / "README.md").write_text(
        "---\nslug: demo-book\nbook_category: fiction\n---\n\n# Demo Book\n",
        encoding="utf-8",
    )
    (book / "CLAUDE.md").write_text(f"{fm}# Book CLAUDE.md\n", encoding="utf-8")
    return book


def _write_draft(book: Path, text: str, chapter_slug: str = "01-opening") -> Path:
    chapter = book / "chapters" / chapter_slug
    chapter.mkdir(parents=True, exist_ok=True)
    draft = chapter / "draft.md"
    draft.write_text(text, encoding="utf-8")
    (chapter / "README.md").write_text("# Chapter 1\n\n## Chapter Timeline\n\n", encoding="utf-8")
    return draft


class TestValidationResultEnvelope:
    def test_clean_chapter_returns_pass_gate(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path)
        prose = " ".join(
            [
                "The hero walked through a quiet field with no fanfare at all.",
                "Birds fell silent above the broken road as he passed by.",
                "Every step landed with deliberate weight on dry earth.",
                "He thought about the choice ahead in plain words.",
                "Morning would come no matter what he chose.",
                "The wind shifted; rain seemed possible by afternoon.",
            ]
        )
        draft = _write_draft(book, prose)

        result = validate_chapter_path(str(draft))
        assert isinstance(result, ValidationResult)
        gate = result.to_gate()
        assert gate.status == "PASS"
        assert gate.metadata["mode"] == DEFAULT_MODE
        assert gate.metadata["blocking_count"] == 0

    def test_blocking_finding_in_strict_fails(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path)
        # Meta-narrative trigger + enough words.
        prose = "The flame is a callback to last winter, but he never lit it himself.\n" + (
            "The river ran cold past the camp. " * 30
        )
        draft = _write_draft(book, prose)

        result = validate_chapter_path(str(draft))
        assert result.mode == "strict"
        assert result.blocking, "expected at least one blocking finding"
        assert result.will_block is True
        gate = result.to_gate()
        assert gate.status == "FAIL"
        assert any(f.severity == "FAIL" for f in gate.findings)

    def test_warn_mode_demotes_blocking_to_warn(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, frontmatter_mode="warn")
        prose = "The flame is a callback to last winter, but he never lit it himself.\n" + (
            "The river ran cold past the camp. " * 30
        )
        draft = _write_draft(book, prose)

        result = validate_chapter_path(str(draft))
        assert result.mode == "warn"
        assert result.blocking
        assert result.will_block is False
        gate = result.to_gate()
        assert gate.status == "WARN"

    def test_too_short_returns_pass(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path)
        draft = _write_draft(book, "Not enough words.")
        result = validate_chapter_path(str(draft))
        assert result.findings == []
        assert result.to_gate().status == "PASS"

    def test_render_block_report_lists_blocking(self, tmp_path: Path) -> None:
        result = ValidationResult(
            file_path="/tmp/chapters/01/draft.md",
            mode="strict",
            findings=[
                Finding(severity=SEVERITY_BLOCK, category="meta_narrative", message="callback found", line=12),
                Finding(severity=SEVERITY_WARN, category="ai_tell", message="word found", line=4),
            ],
        )
        report = result.render_block_report()
        assert "StoryForge linter blocked this write" in report
        assert "[BLOCK] draft.md line 12: callback found" in report
        assert "Plus 1 non-blocking warning" in report

    def test_render_diagnostics_caps(self, tmp_path: Path) -> None:
        result = ValidationResult(
            file_path="/tmp/chapters/01/draft.md",
            mode="warn",
            findings=[
                Finding(severity=SEVERITY_WARN, category="ai_tell", message=f"hit {i}", line=i) for i in range(15)
            ],
        )
        diag = result.render_diagnostics(cap=5)
        assert len(diag) == 5

    def test_to_json_dict_round_trips(self, tmp_path: Path) -> None:
        result = ValidationResult(
            file_path=str(tmp_path / "draft.md"),
            mode="strict",
            findings=[
                Finding(severity=SEVERITY_BLOCK, category="meta_narrative", message="callback found", line=3),
            ],
        )
        payload = json.dumps(result.to_json_dict())
        restored = json.loads(payload)
        assert restored["mode"] == "strict"
        assert restored["blocking_count"] == 1
        assert restored["gate"]["status"] == "FAIL"
        assert restored["gate"]["findings"][0]["code"] == "META_NARRATIVE"


class TestResolveMode:
    def test_default_strict(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path)
        draft = _write_draft(book, "Some prose " * 20)
        assert resolve_mode(draft) == "strict"

    def test_warn_via_frontmatter(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, frontmatter_mode="warn")
        draft = _write_draft(book, "Some prose " * 20)
        assert resolve_mode(draft) == "warn"

    def test_invalid_mode_falls_back(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path)
        # Invalid frontmatter value.
        (book / "CLAUDE.md").write_text(
            "---\nlinter_mode: nonsense\n---\n\n# Book CLAUDE.md\n",
            encoding="utf-8",
        )
        draft = _write_draft(book, "Some prose " * 20)
        assert resolve_mode(draft) == "strict"


class TestBackwardCompat:
    """Confirm the legacy ``validate_chapter`` entry point still works."""

    def test_returns_list_of_findings(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path)
        draft = _write_draft(book, "The callback arrived. " * 30)
        findings = validate_chapter(str(draft))
        assert isinstance(findings, list)
        assert all(isinstance(f, Finding) for f in findings)

    def test_returns_empty_for_non_chapter_path(self) -> None:
        assert validate_chapter("/does/not/exist.md") == []
        assert validate_chapter("/some/notes.md") == []
