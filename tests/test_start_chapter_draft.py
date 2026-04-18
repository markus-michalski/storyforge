"""Tests for the ``start_chapter_draft`` MCP tool (Issue #23).

The chapter-writer skill must flip chapter status ``Outline → Draft`` at the
start of writing, not only at Step 7 after the chapter is complete. This
keeps ``get_book_progress`` and the #21 book-tier derivation honest during
active work (otherwise books stay at Drafting-tier until chapter 1 is
finished, which defeats the purpose).

The tool encapsulates the "only flip forward" logic so skills don't have to
re-implement it. Later transitions (Draft → Review/Final) stay on Step 7's
existing ``update_field`` call path.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Fixtures (mirrored from other integration tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    root.mkdir()
    return root


@pytest.fixture
def mock_config(content_root: Path):
    fake_config = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(content_root / "authors"),
        },
        "defaults": {"language": "en", "book_type": "novel"},
    }

    import server as server_mod  # noqa: WPS433
    from tools.state import indexer as indexer_mod

    fake_state_path = content_root / "_cache" / "state.json"

    with patch.object(server_mod, "load_config", return_value=fake_config), \
         patch.object(server_mod, "get_content_root", return_value=content_root), \
         patch.object(indexer_mod, "load_config", return_value=fake_config), \
         patch.object(indexer_mod, "STATE_PATH", fake_state_path), \
         patch.object(indexer_mod, "CACHE_DIR", fake_state_path.parent):
        server_mod._cache.invalidate()
        yield fake_config


@pytest.fixture
def server_module(mock_config):
    import server as server_mod  # noqa: WPS433
    return server_mod


def _write_book(content_root: Path, slug: str = "test-book") -> Path:
    project = content_root / "projects" / slug
    project.mkdir(parents=True)
    (project / "README.md").write_text(
        f'---\ntitle: "Test"\nslug: "{slug}"\nstatus: "Idea"\n---\n# Test\n',
        encoding="utf-8",
    )
    (project / "chapters").mkdir()
    return project


def _write_chapter_with_yaml(book: Path, slug: str, status: str) -> Path:
    ch_dir = book / "chapters" / slug
    ch_dir.mkdir(parents=True)
    (ch_dir / "README.md").write_text(f"# {slug}\n\nOutline body.\n", encoding="utf-8")
    (ch_dir / "chapter.yaml").write_text(
        f'title: "{slug}"\nnumber: 1\nstatus: "{status}"\npov_character: "Alex"\n',
        encoding="utf-8",
    )
    return ch_dir


def _write_chapter_with_readme_frontmatter(book: Path, slug: str, status: str) -> Path:
    ch_dir = book / "chapters" / slug
    ch_dir.mkdir(parents=True)
    (ch_dir / "README.md").write_text(
        f'---\ntitle: "{slug}"\nnumber: 1\nstatus: "{status}"\n---\n# {slug}\n',
        encoding="utf-8",
    )
    return ch_dir


# ---------------------------------------------------------------------------
# start_chapter_draft — core contract
# ---------------------------------------------------------------------------


class TestStartChapterDraft:
    def test_flips_outline_to_draft_via_chapter_yaml(
        self, server_module, content_root: Path
    ):
        book = _write_book(content_root, "book-a")
        ch = _write_chapter_with_yaml(book, "01-start", status="Outline")

        result = json.loads(
            server_module.start_chapter_draft("book-a", "01-start")
        )

        assert result["success"] is True
        assert result["chapter_status_before"] == "Outline"
        assert result["chapter_status_after"] == "Draft"
        assert result["chapter_updated"] is True

        meta = yaml.safe_load((ch / "chapter.yaml").read_text(encoding="utf-8"))
        assert meta["status"] == "Draft"

    def test_migrates_readme_frontmatter_to_chapter_yaml_on_first_draft(
        self, server_module, content_root: Path
    ):
        # Legacy chapter without chapter.yaml — the tool migrates metadata
        # from README frontmatter into chapter.yaml (the canonical source
        # per #16) and strips the frontmatter from README.
        book = _write_book(content_root, "book-b")
        ch = _write_chapter_with_readme_frontmatter(book, "01-start", status="Outline")
        # Add extra fields to verify they migrate cleanly
        (ch / "README.md").write_text(
            '---\ntitle: "The Start"\nnumber: 1\nstatus: "Outline"\n'
            'pov_character: "Alex"\nword_count_target: 3000\n---\n\n'
            "# Chapter 1\n\nOutline text here.\n",
            encoding="utf-8",
        )

        result = json.loads(
            server_module.start_chapter_draft("book-b", "01-start")
        )

        assert result["success"] is True
        assert result["chapter_status_after"] == "Draft"
        assert result.get("migrated_to_chapter_yaml") is True

        # chapter.yaml now exists with migrated metadata + new status
        chapter_yaml_path = ch / "chapter.yaml"
        assert chapter_yaml_path.exists()
        meta = yaml.safe_load(chapter_yaml_path.read_text(encoding="utf-8"))
        assert meta["status"] == "Draft"
        assert meta["title"] == "The Start"
        assert meta["number"] == 1
        assert meta["pov_character"] == "Alex"
        assert meta["word_count_target"] == 3000

        # README frontmatter is stripped; body stays
        readme_text = (ch / "README.md").read_text(encoding="utf-8")
        assert "---\ntitle:" not in readme_text
        assert "# Chapter 1" in readme_text
        assert "Outline text here." in readme_text

    def test_noop_when_already_draft(self, server_module, content_root: Path):
        book = _write_book(content_root, "book-c")
        ch = _write_chapter_with_yaml(book, "01-mid", status="Draft")

        result = json.loads(
            server_module.start_chapter_draft("book-c", "01-mid")
        )

        assert result["success"] is True
        assert result["chapter_status_before"] == "Draft"
        assert result["chapter_status_after"] == "Draft"
        assert result["chapter_updated"] is False

        # chapter.yaml untouched
        meta = yaml.safe_load((ch / "chapter.yaml").read_text(encoding="utf-8"))
        assert meta["status"] == "Draft"

    def test_noop_when_review_status_does_not_regress(
        self, server_module, content_root: Path
    ):
        # User's lowercase "review" must not get reset to Draft.
        book = _write_book(content_root, "book-d")
        ch = _write_chapter_with_yaml(book, "01-reviewed", status="review")

        result = json.loads(
            server_module.start_chapter_draft("book-d", "01-reviewed")
        )

        assert result["chapter_updated"] is False
        meta = yaml.safe_load((ch / "chapter.yaml").read_text(encoding="utf-8"))
        assert meta["status"] == "review"

    def test_noop_when_final(self, server_module, content_root: Path):
        book = _write_book(content_root, "book-e")
        ch = _write_chapter_with_yaml(book, "01-done", status="Final")

        result = json.loads(
            server_module.start_chapter_draft("book-e", "01-done")
        )

        assert result["chapter_updated"] is False
        meta = yaml.safe_load((ch / "chapter.yaml").read_text(encoding="utf-8"))
        assert meta["status"] == "Final"

    def test_error_when_chapter_not_found(
        self, server_module, content_root: Path
    ):
        _write_book(content_root, "book-f")

        result = json.loads(
            server_module.start_chapter_draft("book-f", "99-missing")
        )

        assert "error" in result

    def test_error_when_book_not_found(
        self, server_module, content_root: Path
    ):
        result = json.loads(
            server_module.start_chapter_draft("nope", "01-chapter")
        )

        assert "error" in result

    def test_preserves_other_chapter_yaml_fields(
        self, server_module, content_root: Path
    ):
        # Make sure updating status doesn't drop other fields.
        book = _write_book(content_root, "book-g")
        ch = book / "chapters" / "01-rich"
        ch.mkdir(parents=True)
        (ch / "README.md").write_text("# Chapter\n", encoding="utf-8")
        (ch / "chapter.yaml").write_text(
            'title: "Rich"\n'
            "number: 1\n"
            'status: "Outline"\n'
            'pov_character: "Alex"\n'
            'summary: "The opening of the story."\n'
            "word_count_target: 3500\n"
            "act: 1\n",
            encoding="utf-8",
        )

        server_module.start_chapter_draft("book-g", "01-rich")

        meta = yaml.safe_load((ch / "chapter.yaml").read_text(encoding="utf-8"))
        assert meta["status"] == "Draft"
        assert meta["title"] == "Rich"
        assert meta["number"] == 1
        assert meta["pov_character"] == "Alex"
        assert meta["summary"] == "The opening of the story."
        assert meta["word_count_target"] == 3500
        assert meta["act"] == 1

    def test_get_book_progress_reflects_flip_immediately(
        self, server_module, content_root: Path
    ):
        # End-to-end: after start_chapter_draft, the book auto-escalates
        # to Drafting tier via the #21 indexer derivation.
        book = _write_book(content_root, "book-h")
        _write_chapter_with_yaml(book, "01-start", status="Outline")
        _write_chapter_with_yaml(book, "02-next", status="Outline")

        before = json.loads(server_module.get_book_progress("book-h"))
        assert before["chapters_drafted"] == 0
        assert before["status"] == "Idea"

        server_module.start_chapter_draft("book-h", "01-start")

        after = json.loads(server_module.get_book_progress("book-h"))
        assert after["chapters_drafted"] == 1
        assert after["status"] == "Drafting"
