"""Tests for the PostToolUse hook's global shape-ban scanner (Issue #213).

The hook surfaces catalog-level Section 11 shapes as warn-severity findings
so every author's chapter drafts get the same baseline AI-tell shape
detection, without requiring per-author profile copies.
"""

from __future__ import annotations

from pathlib import Path

from tools.analysis.chapter_validator import (
    SEVERITY_BLOCK,
    SEVERITY_WARN,
    validate_chapter,
)


def _write_book(tmp_path: Path) -> Path:
    book = tmp_path / "demo-book"
    (book / "chapters" / "01-opening").mkdir(parents=True)
    (book / "characters").mkdir()
    (book / "world").mkdir()
    (book / "README.md").write_text(
        "---\nslug: demo-book\nbook_category: fiction\n---\n\n# Demo Book\n",
        encoding="utf-8",
    )
    (book / "CLAUDE.md").write_text("# Demo Book\n", encoding="utf-8")
    return book


def _write_draft(book: Path, text: str) -> Path:
    chapter = book / "chapters" / "01-opening"
    draft = chapter / "draft.md"
    draft.write_text(text, encoding="utf-8")
    (chapter / "README.md").write_text("# Chapter 1\n", encoding="utf-8")
    return draft


class TestHookGlobalShapes:
    def test_offending_phrase_produces_warn_finding(self, tmp_path: Path):
        book = _write_book(tmp_path)
        # The real Section 11 has the room-as-receiver pattern. A draft that
        # contains it should produce a warn-severity global_shape_violation.
        prose = "The room received it without complaint that morning. " * 30
        draft = _write_draft(book, prose)

        findings = validate_chapter(str(draft))
        global_findings = [
            f for f in findings if f.category == "global_shape_violation"
        ]
        assert global_findings, "expected at least one global_shape_violation"
        # Catalog-level patterns are warn-only — not blocking.
        assert all(f.severity == SEVERITY_WARN for f in global_findings)

    def test_clean_prose_no_finding(self, tmp_path: Path):
        book = _write_book(tmp_path)
        prose = "Theo walked across the floor and considered the morning. " * 30
        draft = _write_draft(book, prose)

        findings = validate_chapter(str(draft))
        global_findings = [
            f for f in findings if f.category == "global_shape_violation"
        ]
        assert not global_findings

    def test_warn_does_not_block_write(self, tmp_path: Path):
        """A global shape hit must not trigger exit-2 on its own. Block
        severity is reserved for vocabulary/Don'ts/Recurring-Tics."""
        from tools.analysis.chapter_validator import validate_chapter_path

        book = _write_book(tmp_path)
        prose = "The room received it without comment that morning. " * 30
        draft = _write_draft(book, prose)

        result = validate_chapter_path(str(draft))
        global_findings = [
            f for f in result.findings if f.category == "global_shape_violation"
        ]
        assert global_findings
        # Strict mode + warn-severity finding → no block.
        # (will_block requires at least one severity=block finding.)
        block_count = sum(
            1 for f in result.findings if f.severity == SEVERITY_BLOCK
        )
        if block_count == 0:
            assert not result.will_block
