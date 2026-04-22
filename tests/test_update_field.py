"""Regression tests for the ``update_field`` MCP tool.

Issue: update_field treated chapter.yaml as a markdown file and wrapped the
existing plain-YAML content in frontmatter delimiters (``---``), producing a
multi-document YAML stream. yaml.safe_load then threw ComposerError, so
parse_chapter_readme fell back to an empty dict and defaulted the chapter
status to "Outline" — making chapters appear undrafted even after review.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Fixtures
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

    import server as server_mod
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
    import server as server_mod
    return server_mod


# ---------------------------------------------------------------------------
# update_field — YAML files
# ---------------------------------------------------------------------------


class TestUpdateFieldYaml:
    def test_updates_plain_yaml_without_frontmatter_markers(
        self, server_module, tmp_path: Path
    ):
        """update_field on a .yaml file must NOT wrap content in --- delimiters."""
        chapter_yaml = tmp_path / "chapter.yaml"
        chapter_yaml.write_text(
            "status: Draft\ntitle: Test Chapter\n", encoding="utf-8"
        )

        result = json.loads(
            server_module.update_field(str(chapter_yaml), "status", "Review")
        )

        assert result["success"] is True
        content = chapter_yaml.read_text(encoding="utf-8")
        # Must be parseable as plain YAML — no ComposerError
        meta = yaml.safe_load(content)
        assert isinstance(meta, dict), "chapter.yaml must remain a valid plain-YAML dict"
        assert meta["status"] == "Review"
        assert "---" not in content, "chapter.yaml must never contain frontmatter markers"

    def test_preserves_existing_fields_in_yaml(
        self, server_module, tmp_path: Path
    ):
        chapter_yaml = tmp_path / "chapter.yaml"
        chapter_yaml.write_text(
            "status: Draft\ntitle: Bruises\nnumber: 20\n", encoding="utf-8"
        )

        server_module.update_field(str(chapter_yaml), "status", "Review")

        meta = yaml.safe_load(chapter_yaml.read_text(encoding="utf-8"))
        assert meta["title"] == "Bruises"
        assert meta["number"] == 20
        assert meta["status"] == "Review"

    def test_regression_broken_double_frontmatter(
        self, server_module, tmp_path: Path
    ):
        """Regression: the exact broken file shape from the bug report.

        Before the fix, update_field on a plain-YAML chapter.yaml produced:
            ---
            status: Review
            ---
            status: Draft

        yaml.safe_load raises ComposerError on this, causing parse_chapter_readme
        to return status "Outline" even though the chapter is reviewed.
        """
        chapter_yaml = tmp_path / "chapter.yaml"
        # Simulate the broken state written by the old code path
        chapter_yaml.write_text(
            "---\nstatus: Review\n---\nstatus: Draft\n", encoding="utf-8"
        )

        # A subsequent update must heal the file, not make it worse
        result = json.loads(
            server_module.update_field(str(chapter_yaml), "status", "Review")
        )

        assert result["success"] is True
        meta = yaml.safe_load(chapter_yaml.read_text(encoding="utf-8"))
        assert isinstance(meta, dict)
        assert meta["status"] == "Review"

    def test_start_chapter_draft_then_update_field_roundtrip(
        self, server_module, content_root: Path
    ):
        """Full workflow: start_chapter_draft writes plain YAML, update_field
        transitions status forward — parse_chapter_readme must read correctly."""
        from tools.state.parsers import parse_chapter_readme

        book_dir = content_root / "projects" / "test-book"
        ch_dir = book_dir / "chapters" / "20-bruises"
        ch_dir.mkdir(parents=True)
        (book_dir / "README.md").write_text(
            '---\ntitle: "Test"\nstatus: "Drafting"\n---\n', encoding="utf-8"
        )
        (ch_dir / "README.md").write_text("# Bruises\n\nOutline.\n", encoding="utf-8")
        (ch_dir / "chapter.yaml").write_text(
            'title: "Bruises"\nnumber: 20\nstatus: "Outline"\n', encoding="utf-8"
        )

        # Step 1 — chapter-writer calls start_chapter_draft
        server_module.start_chapter_draft("test-book", "20-bruises")
        meta_after_draft = yaml.safe_load((ch_dir / "chapter.yaml").read_text(encoding="utf-8"))
        assert meta_after_draft["status"] == "Draft"

        # Step 2 — chapter-reviewer calls update_field to advance to Review
        chapter_yaml_path = str(ch_dir / "chapter.yaml")
        server_module.update_field(chapter_yaml_path, "status", "Review")

        # parse_chapter_readme must reflect the new status — not fall back to Outline
        parsed = parse_chapter_readme(ch_dir / "README.md")
        assert parsed["status"] == "Review", (
            "parse_chapter_readme must read 'Review' from chapter.yaml after "
            "update_field — ComposerError would silently return 'Outline'"
        )


# ---------------------------------------------------------------------------
# update_field — Markdown files (existing behaviour must be unchanged)
# ---------------------------------------------------------------------------


class TestUpdateFieldMarkdown:
    def test_updates_existing_frontmatter_field(self, server_module, tmp_path: Path):
        md = tmp_path / "README.md"
        md.write_text("---\nstatus: Draft\ntitle: Test\n---\n\nBody text.\n", encoding="utf-8")

        result = json.loads(server_module.update_field(str(md), "status", "Review"))

        assert result["success"] is True
        content = md.read_text(encoding="utf-8")
        assert "status: Review" in content
        assert "Body text." in content

    def test_adds_field_when_absent_in_frontmatter(self, server_module, tmp_path: Path):
        md = tmp_path / "README.md"
        md.write_text("---\ntitle: Test\n---\n\nBody.\n", encoding="utf-8")

        server_module.update_field(str(md), "status", "Revision")

        content = md.read_text(encoding="utf-8")
        assert "status: Revision" in content

    def test_creates_frontmatter_when_none_exists(self, server_module, tmp_path: Path):
        md = tmp_path / "README.md"
        md.write_text("Just a body without frontmatter.\n", encoding="utf-8")

        server_module.update_field(str(md), "status", "Draft")

        content = md.read_text(encoding="utf-8")
        assert "---" in content
        assert "status: Draft" in content
