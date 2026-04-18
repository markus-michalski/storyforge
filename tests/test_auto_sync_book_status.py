"""Tests for auto-sync of derived book status to README frontmatter (Issue #25).

After #19/#21, `get_book_progress` exposes a derived ``status`` (from
aggregate chapter state) alongside ``status_disk`` (raw frontmatter). The
divergence was visible but not self-healing: the user had to manually fix
README to keep the two in sync. Issue #25 closes that loop.

The indexer now writes the derived status back to the README frontmatter
whenever the derived rank is **higher** than the disk rank. The floor rule
ensures a user-set higher tier (e.g. ``Export Ready`` set by hand) is
never silently downgraded by chapter aggregates.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.state.parsers import parse_frontmatter


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


def _write_book_with_frontmatter(
    content_root: Path, slug: str, disk_status: str, extra_fields: str = ""
) -> Path:
    project = content_root / "projects" / slug
    project.mkdir(parents=True)
    (project / "README.md").write_text(
        f'---\ntitle: "Test"\nslug: "{slug}"\nstatus: "{disk_status}"\n'
        f'target_word_count: 30000\n{extra_fields}---\n\n# {slug}\n\nBody stays intact.\n',
        encoding="utf-8",
    )
    (project / "chapters").mkdir()
    return project


def _write_book_without_frontmatter(content_root: Path, slug: str) -> Path:
    # Edge case: README with no frontmatter block at all
    project = content_root / "projects" / slug
    project.mkdir(parents=True)
    (project / "README.md").write_text(
        f"# {slug}\n\nPure markdown body, no frontmatter.\n",
        encoding="utf-8",
    )
    (project / "chapters").mkdir()
    return project


def _write_chapter(book: Path, slug: str, status: str) -> Path:
    ch = book / "chapters" / slug
    ch.mkdir(parents=True)
    (ch / "README.md").write_text("# Body\n", encoding="utf-8")
    (ch / "chapter.yaml").write_text(
        f'title: "{slug}"\nstatus: "{status}"\n', encoding="utf-8"
    )
    return ch


def _read_readme_status(project: Path) -> str:
    text = (project / "README.md").read_text(encoding="utf-8")
    meta, _ = parse_frontmatter(text)
    return meta.get("status", "")


# ---------------------------------------------------------------------------
# Forward-sync cases
# ---------------------------------------------------------------------------


class TestAutoSyncForward:
    def test_syncs_idea_to_drafting_when_chapter_started(
        self, server_module, content_root: Path
    ):
        project = _write_book_with_frontmatter(content_root, "book-a", "Idea")
        _write_chapter(project, "01-c", status="Draft")

        server_module.rebuild_state()

        assert _read_readme_status(project) == "Drafting"

    def test_syncs_idea_to_revision_when_all_chapters_reviewed(
        self, server_module, content_root: Path
    ):
        # Bug scenario from #25: blood-and-binary book with lots of "review" chapters.
        project = _write_book_with_frontmatter(content_root, "book-b", "Idea")
        _write_chapter(project, "01-c", status="review")
        _write_chapter(project, "02-c", status="review")

        server_module.rebuild_state()

        assert _read_readme_status(project) == "Revision"

    def test_syncs_drafting_to_revision(self, server_module, content_root: Path):
        # User had manually set Drafting; all chapters now at review → escalate.
        project = _write_book_with_frontmatter(content_root, "book-c", "Drafting")
        _write_chapter(project, "01-c", status="review")
        _write_chapter(project, "02-c", status="review")

        server_module.rebuild_state()

        assert _read_readme_status(project) == "Revision"

    def test_syncs_idea_to_proofread_when_all_final(
        self, server_module, content_root: Path
    ):
        project = _write_book_with_frontmatter(content_root, "book-d", "Idea")
        _write_chapter(project, "01-c", status="Final")
        _write_chapter(project, "02-c", status="Final")

        server_module.rebuild_state()

        assert _read_readme_status(project) == "Proofread"


# ---------------------------------------------------------------------------
# Floor rule: never downgrade a user-set higher status
# ---------------------------------------------------------------------------


class TestFloorRule:
    def test_export_ready_not_downgraded_by_drafting_chapters(
        self, server_module, content_root: Path
    ):
        # User explicitly marked the book as Export Ready. Draft chapters
        # (derived: Drafting) must NOT pull it back.
        project = _write_book_with_frontmatter(content_root, "book-e", "Export Ready")
        _write_chapter(project, "01-c", status="Draft")

        server_module.rebuild_state()

        assert _read_readme_status(project) == "Export Ready"

    def test_published_not_touched_by_any_chapter_state(
        self, server_module, content_root: Path
    ):
        project = _write_book_with_frontmatter(content_root, "book-f", "Published")
        _write_chapter(project, "01-c", status="Outline")
        _write_chapter(project, "02-c", status="Final")

        server_module.rebuild_state()

        assert _read_readme_status(project) == "Published"

    def test_no_change_when_disk_already_matches_derived(
        self, server_module, content_root: Path
    ):
        project = _write_book_with_frontmatter(content_root, "book-g", "Drafting")
        _write_chapter(project, "01-c", status="Draft")
        _write_chapter(project, "02-c", status="Outline")

        # Capture mtime before
        readme = project / "README.md"
        import os
        mtime_before = os.path.getmtime(readme)

        # Sleep tiny bit to ensure mtime resolution catches any write
        import time
        time.sleep(0.01)

        server_module.rebuild_state()

        mtime_after = os.path.getmtime(readme)
        assert mtime_before == mtime_after, "README must not be rewritten when disk == derived"


# ---------------------------------------------------------------------------
# Edge: README has no frontmatter block at all
# ---------------------------------------------------------------------------


class TestNoFrontmatterEdgeCase:
    def test_creates_frontmatter_when_missing(
        self, server_module, content_root: Path
    ):
        # Legacy book with no frontmatter at all. The indexer should add one.
        project = _write_book_without_frontmatter(content_root, "book-h")
        _write_chapter(project, "01-c", status="review")
        _write_chapter(project, "02-c", status="review")

        server_module.rebuild_state()

        text = (project / "README.md").read_text(encoding="utf-8")
        assert text.startswith("---\n")
        meta, body = parse_frontmatter(text)
        assert meta["status"] == "Revision"
        # Body preserved
        assert "# book-h" in body or "Pure markdown body" in body


# ---------------------------------------------------------------------------
# Preserves other frontmatter and body content
# ---------------------------------------------------------------------------


class TestPreservesOtherContent:
    def test_other_frontmatter_fields_intact(
        self, server_module, content_root: Path
    ):
        project = _write_book_with_frontmatter(
            content_root,
            "book-i",
            "Idea",
            extra_fields=(
                'author: "test-author"\n'
                'genres: ["horror", "fantasy"]\n'
                'language: "en"\n'
                'description: "A gripping tale."\n'
            ),
        )
        _write_chapter(project, "01-c", status="Draft")

        server_module.rebuild_state()

        meta, _ = parse_frontmatter((project / "README.md").read_text(encoding="utf-8"))
        assert meta["status"] == "Drafting"  # updated
        assert meta["author"] == "test-author"
        assert meta["genres"] == ["horror", "fantasy"]
        assert meta["language"] == "en"
        assert meta["description"] == "A gripping tale."
        assert meta["target_word_count"] == 30000

    def test_body_content_intact(self, server_module, content_root: Path):
        project = _write_book_with_frontmatter(content_root, "book-j", "Idea")
        _write_chapter(project, "01-c", status="Draft")

        server_module.rebuild_state()

        text = (project / "README.md").read_text(encoding="utf-8")
        assert "Body stays intact." in text


# ---------------------------------------------------------------------------
# rebuild_state response includes sync log
# ---------------------------------------------------------------------------


class TestRebuildStateResponse:
    def test_response_includes_updated_books_log(
        self, server_module, content_root: Path
    ):
        project = _write_book_with_frontmatter(content_root, "book-k", "Idea")
        _write_chapter(project, "01-c", status="Draft")

        result = json.loads(server_module.rebuild_state())

        assert "synced" in result
        assert any(
            s.get("book") == "book-k"
            and s.get("from") == "Idea"
            and s.get("to") == "Drafting"
            for s in result["synced"]
        )

    def test_response_empty_sync_log_when_nothing_to_update(
        self, server_module, content_root: Path
    ):
        project = _write_book_with_frontmatter(content_root, "book-l", "Drafting")
        _write_chapter(project, "01-c", status="Draft")

        result = json.loads(server_module.rebuild_state())

        assert result.get("synced", []) == []
