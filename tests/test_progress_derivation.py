"""Tests for book-progress aggregation and status derivation (Issue #19).

After #16 fixed per-chapter status reporting, two aggregation bugs remained:

1. ``chapters_drafted`` only counted a hardcoded set of canonical statuses
   ({Draft, Revision, Polished, Final}). Non-canonical-but-clearly-drafted
   states (e.g. ``"review"`` from a user's chapter.yaml) fell through to
   zero. The right rule: anything past ``Outline`` counts as drafted.

2. Book-level ``status`` stayed at whatever the README frontmatter said.
   A book with 17 reviewed chapters reported ``status: "Idea"``. We now
   derive an effective status from chapter aggregates and surface it via
   ``get_book_progress`` (and the indexer for downstream consumers),
   without writing back to disk.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.state.parsers import derive_book_status


# ---------------------------------------------------------------------------
# Fixtures (mirrored from test_ideas.py / test_scaffold_conventions.py)
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

    # Redirect the persistent state cache to the tmp dir so tests don't
    # collide with the user's real ~/.storyforge/cache/state.json.
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


def _write_book(content_root: Path, slug: str, status: str = "Idea") -> Path:
    project = content_root / "projects" / slug
    project.mkdir(parents=True)
    (project / "README.md").write_text(
        f'---\ntitle: "Test"\nslug: "{slug}"\nstatus: "{status}"\n'
        f'target_word_count: 30000\n---\n# Test\n',
        encoding="utf-8",
    )
    (project / "chapters").mkdir()
    return project


def _write_chapter(book_dir: Path, slug: str, status: str, words: int = 0) -> Path:
    ch_dir = book_dir / "chapters" / slug
    ch_dir.mkdir(parents=True)
    (ch_dir / "README.md").write_text("# Body\n", encoding="utf-8")
    (ch_dir / "chapter.yaml").write_text(
        f'title: "{slug}"\nstatus: "{status}"\n', encoding="utf-8"
    )
    if words:
        (ch_dir / "draft.md").write_text(" ".join(["word"] * words), encoding="utf-8")
    return ch_dir


# ---------------------------------------------------------------------------
# derive_book_status helper
# ---------------------------------------------------------------------------


class TestDeriveBookStatus:
    def test_no_chapters_keeps_current_status(self):
        assert derive_book_status("Idea", {}) == "Idea"
        assert derive_book_status("Plot Outlined", {}) == "Plot Outlined"

    def test_all_outline_keeps_current_status(self):
        chapters = {
            "01": {"status": "Outline"},
            "02": {"status": "Outline"},
        }
        assert derive_book_status("Idea", chapters) == "Idea"
        assert derive_book_status("Plot Outlined", chapters) == "Plot Outlined"

    def test_any_draft_escalates_to_drafting(self):
        chapters = {
            "01": {"status": "Draft"},
            "02": {"status": "Outline"},
        }
        assert derive_book_status("Idea", chapters) == "Drafting"

    def test_lowercase_review_escalates_to_drafting(self):
        # Bug-report case: chapter.yaml uses lowercase "review"
        chapters = {
            "01": {"status": "review"},
            "02": {"status": "Outline"},
        }
        assert derive_book_status("Idea", chapters) == "Drafting"

    def test_does_not_regress_past_drafting(self):
        # If the book is already past Drafting (e.g. Revision), a chapter
        # at Draft should not pull the book status backward.
        chapters = {"01": {"status": "Draft"}}
        assert derive_book_status("Revision", chapters) == "Revision"
        assert derive_book_status("Editing", chapters) == "Editing"
        assert derive_book_status("Published", chapters) == "Published"

    def test_unknown_current_status_passes_through_when_no_drafts(self):
        # Don't mangle unrecognized custom statuses if there's no signal.
        chapters = {"01": {"status": "Outline"}}
        assert derive_book_status("Custom Status", chapters) == "Custom Status"


# ---------------------------------------------------------------------------
# get_book_progress: drafted count + completion_percent + derived status
# ---------------------------------------------------------------------------


class TestGetBookProgress:
    def test_drafted_count_includes_lowercase_review(
        self, server_module, content_root: Path
    ):
        # Reproduces the issue exactly: chapter.yaml status: review
        project = _write_book(content_root, "review-book")
        for n in range(1, 4):
            _write_chapter(project, f"{n:02d}-c", status="review", words=1000)
        _write_chapter(project, "04-c", status="Outline")

        result = json.loads(server_module.get_book_progress("review-book"))

        assert result["chapters_total"] == 4
        assert result["chapters_drafted"] == 3, (
            "Bug #19: 'review' chapters must count toward chapters_drafted"
        )

    def test_drafted_count_includes_canonical_statuses(
        self, server_module, content_root: Path
    ):
        project = _write_book(content_root, "canon-book")
        _write_chapter(project, "01-a", status="Draft")
        _write_chapter(project, "02-b", status="Revision")
        _write_chapter(project, "03-c", status="Polished")
        _write_chapter(project, "04-d", status="Final")
        _write_chapter(project, "05-e", status="Outline")

        result = json.loads(server_module.get_book_progress("canon-book"))

        assert result["chapters_drafted"] == 4
        assert result["chapters_final"] == 1

    def test_completion_percent_uses_drafted_not_final(
        self, server_module, content_root: Path
    ):
        # Bug #19: 17 of 34 reviewed should be ~50%, not 0%.
        project = _write_book(content_root, "halfway")
        for n in range(1, 18):
            _write_chapter(project, f"{n:02d}-c", status="review", words=2000)
        for n in range(18, 35):
            _write_chapter(project, f"{n:02d}-c", status="Outline")

        result = json.loads(server_module.get_book_progress("halfway"))

        assert result["chapters_total"] == 34
        assert result["chapters_drafted"] == 17
        assert result["chapters_final"] == 0
        assert result["completion_percent"] == 50

    def test_status_derived_from_chapter_state(
        self, server_module, content_root: Path
    ):
        # Bug #19: book disk-status "Idea" + drafted chapters → effective "Drafting".
        project = _write_book(content_root, "stuck-on-idea", status="Idea")
        _write_chapter(project, "01-c", status="review", words=3000)
        _write_chapter(project, "02-c", status="Outline")

        result = json.loads(server_module.get_book_progress("stuck-on-idea"))

        assert result["status"] == "Drafting", (
            "Bug #19: status must reflect chapter-derived progress, not stale frontmatter"
        )

    def test_status_does_not_regress_when_book_past_drafting(
        self, server_module, content_root: Path
    ):
        project = _write_book(content_root, "in-revision", status="Revision")
        _write_chapter(project, "01-c", status="Draft")  # backward chapter state

        result = json.loads(server_module.get_book_progress("in-revision"))

        assert result["status"] == "Revision"

    def test_status_unchanged_when_no_chapters_drafted(
        self, server_module, content_root: Path
    ):
        project = _write_book(content_root, "still-planning", status="Plot Outlined")
        _write_chapter(project, "01-c", status="Outline")
        _write_chapter(project, "02-c", status="Outline")

        result = json.loads(server_module.get_book_progress("still-planning"))

        assert result["status"] == "Plot Outlined"


# ---------------------------------------------------------------------------
# Indexer surfaces derived status (so list_books, get_book, etc. are consistent)
# ---------------------------------------------------------------------------


class TestIndexerDerivedStatus:
    def test_list_books_reflects_derived_status(
        self, server_module, content_root: Path
    ):
        project = _write_book(content_root, "indexed-book", status="Idea")
        _write_chapter(project, "01-c", status="review", words=2000)

        result = json.loads(server_module.list_books())
        book = next(b for b in result["books"] if b["slug"] == "indexed-book")

        assert book["status"] == "Drafting", (
            "Bug #19: list_books must reflect derived status from chapter state"
        )
