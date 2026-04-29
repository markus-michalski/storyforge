"""Smoketest for the validate_chapter MCP tool (Issue #119).

Verifies the MCP wrapper around chapter_validator returns the gate
envelope, preserves the request slug context, and surfaces missing-book
or missing-chapter as a clean error rather than crashing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.gates import validate_chapter


def _build_book(content_root: Path, slug: str = "demo-book") -> Path:
    book = content_root / "projects" / slug
    (book / "chapters" / "01-opening").mkdir(parents=True)
    (book / "characters").mkdir()
    (book / "world").mkdir()

    (book / "README.md").write_text(
        "---\nslug: demo-book\nbook_category: fiction\n---\n\n# Demo Book\n",
        encoding="utf-8",
    )
    (book / "CLAUDE.md").write_text("# Book CLAUDE.md\n", encoding="utf-8")
    return book


def _write_draft(book: Path, text: str, chapter_slug: str = "01-opening") -> None:
    chapter = book / "chapters" / chapter_slug
    (chapter / "draft.md").write_text(text, encoding="utf-8")
    (chapter / "README.md").write_text("# Chapter 1\n\n## Chapter Timeline\n\n", encoding="utf-8")


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    content_root = tmp_path / "content"
    book = _build_book(content_root)
    _write_draft(
        book,
        " ".join(
            [
                "The hero walked through a quiet field with no fanfare at all.",
                "Birds fell silent above the broken road as he passed by.",
                "Every step landed with deliberate weight on dry earth.",
                "He thought about the choice ahead in plain words.",
                "Morning would come no matter what he chose.",
                "The wind shifted; rain seemed possible by afternoon.",
            ]
        ),
    )
    cfg = {"paths": {"content_root": str(content_root)}}
    monkeypatch.setattr(_app, "load_config", lambda: cfg)
    return cfg


class TestValidateChapterMcp:
    def test_clean_chapter_returns_pass_gate(self, config: dict) -> None:
        result = json.loads(validate_chapter("demo-book", "01-opening"))
        assert result["book_slug"] == "demo-book"
        assert result["chapter_slug"] == "01-opening"
        assert "gate" in result
        gate = result["gate"]
        assert gate["status"] == "PASS"
        assert "metadata" in gate and gate["metadata"]["mode"] == "strict"
        assert result["blocking_count"] == 0

    def test_blocking_meta_narrative_yields_fail(self, config: dict, tmp_path: Path) -> None:
        # Replace the draft with one that triggers a meta-narrative block.
        draft = tmp_path / "content" / "projects" / "demo-book" / "chapters" / "01-opening" / "draft.md"
        draft.write_text(
            "The flame is a callback to last winter, but he never lit it himself.\n"
            + ("The river ran cold past the camp. " * 30),
            encoding="utf-8",
        )
        result = json.loads(validate_chapter("demo-book", "01-opening"))
        gate = result["gate"]
        assert gate["status"] == "FAIL"
        assert any(f["code"] == "META_NARRATIVE" for f in gate["findings"])

    def test_missing_book(self, config: dict) -> None:
        result = json.loads(validate_chapter("does-not-exist", "01-opening"))
        assert "error" in result

    def test_missing_chapter(self, config: dict) -> None:
        result = json.loads(validate_chapter("demo-book", "99-missing"))
        assert "error" in result
        assert result["book_slug"] == "demo-book"
