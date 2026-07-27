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
def db_dir(content_root: Path) -> Path:
    # Issue #476: get_book_progress now opens the canon_facts DB too — without
    # redirecting DB_DIR these tests would create real sqlite files under the
    # user's ~/.storyforge/db/ (same pattern as test_add_canon_fact.py).
    return content_root.parent / "db"


@pytest.fixture
def mock_config(content_root: Path, db_dir: Path):
    fake_config = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(content_root / "authors"),
        },
        "defaults": {"language": "en", "book_type": "novel"},
    }

    import routers._app as server_mod
    import tools.db.connection as db_conn_mod
    from tools.state import indexer as indexer_mod

    # Redirect the persistent state cache to the tmp dir so tests don't
    # collide with the user's real ~/.storyforge/cache/state.json.
    fake_state_path = content_root / "_cache" / "state.json"

    with (
        patch.object(server_mod, "load_config", return_value=fake_config),
        patch.object(server_mod, "get_content_root", return_value=content_root),
        patch.object(indexer_mod, "load_config", return_value=fake_config),
        patch.object(indexer_mod, "STATE_PATH", fake_state_path),
        patch.object(indexer_mod, "CACHE_DIR", fake_state_path.parent),
        patch.object(db_conn_mod, "DB_DIR", db_dir),
    ):
        server_mod._cache.invalidate()
        yield fake_config


@pytest.fixture
def server_module(mock_config):  # noqa: F811
    import server as server_mod

    return server_mod


def _write_book(content_root: Path, slug: str, status: str = "Idea") -> Path:
    project = content_root / "projects" / slug
    project.mkdir(parents=True)
    (project / "README.md").write_text(
        f'---\ntitle: "Test"\nslug: "{slug}"\nstatus: "{status}"\ntarget_word_count: 30000\n---\n# Test\n',
        encoding="utf-8",
    )
    (project / "chapters").mkdir()
    return project


def _write_chapter(book_dir: Path, slug: str, status: str, words: int = 0) -> Path:
    ch_dir = book_dir / "chapters" / slug
    ch_dir.mkdir(parents=True)
    (ch_dir / "README.md").write_text("# Body\n", encoding="utf-8")
    (ch_dir / "chapter.yaml").write_text(f'title: "{slug}"\nstatus: "{status}"\n', encoding="utf-8")
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

    # ------------------------------------------------------------------
    # Issue #21: higher tiers (Revision, Proofread) auto-derived
    # ------------------------------------------------------------------

    def test_all_review_escalates_to_revision(self):
        # User's workflow: chapter.yaml uses lowercase "review" for
        # completed first drafts. Should map to Revision rank.
        chapters = {
            "01": {"status": "review"},
            "02": {"status": "review"},
            "03": {"status": "review"},
        }
        assert derive_book_status("Idea", chapters) == "Revision"

    def test_all_revision_canonical_escalates_to_revision(self):
        chapters = {
            "01": {"status": "Revision"},
            "02": {"status": "Revision"},
        }
        assert derive_book_status("Drafting", chapters) == "Revision"

    def test_mixed_revision_polished_final_stays_revision(self):
        # Every chapter >= Revision rank; lowest tier wins.
        chapters = {
            "01": {"status": "Revision"},
            "02": {"status": "Polished"},
            "03": {"status": "Final"},
        }
        assert derive_book_status("Drafting", chapters) == "Revision"

    def test_one_outline_blocks_revision_tier(self):
        # Any lingering Outline keeps the book at Drafting.
        chapters = {
            "01": {"status": "review"},
            "02": {"status": "review"},
            "03": {"status": "Outline"},
        }
        assert derive_book_status("Idea", chapters) == "Drafting"

    def test_one_draft_blocks_revision_tier(self):
        # Draft (rank 1) is below Revision — blocks the tier.
        chapters = {
            "01": {"status": "Revision"},
            "02": {"status": "Draft"},
        }
        assert derive_book_status("Idea", chapters) == "Drafting"

    def test_all_polished_escalates_to_revision(self):
        # Polished is above Revision rank but we don't auto-derive Editing
        # (too fuzzy a distinction). Stays at Revision tier.
        chapters = {
            "01": {"status": "Polished"},
            "02": {"status": "Polished"},
        }
        assert derive_book_status("Idea", chapters) == "Revision"

    def test_all_final_escalates_to_proofread(self):
        chapters = {
            "01": {"status": "Final"},
            "02": {"status": "Final"},
        }
        assert derive_book_status("Idea", chapters) == "Proofread"

    def test_one_non_final_blocks_proofread_tier(self):
        chapters = {
            "01": {"status": "Final"},
            "02": {"status": "Polished"},
        }
        assert derive_book_status("Idea", chapters) == "Revision"

    def test_published_never_regresses(self):
        # Even all-Outline chapters can't pull a Published book backward.
        chapters = {"01": {"status": "Outline"}, "02": {"status": "Outline"}}
        assert derive_book_status("Published", chapters) == "Published"

    def test_export_ready_not_regressed_by_final_chapters(self):
        # Export Ready is explicit; all-Final shouldn't pull it back to Proofread.
        chapters = {"01": {"status": "Final"}, "02": {"status": "Final"}}
        assert derive_book_status("Export Ready", chapters) == "Export Ready"

    def test_unknown_chapter_status_ranks_as_draft(self):
        # Custom statuses (not in alias table) count as drafted but don't
        # escalate to Revision — safe default.
        chapters = {
            "01": {"status": "weird-custom-status"},
            "02": {"status": "weird-custom-status"},
        }
        assert derive_book_status("Idea", chapters) == "Drafting"


# ---------------------------------------------------------------------------
# get_book_progress: drafted count + completion_percent + derived status
# ---------------------------------------------------------------------------


class TestGetBookProgress:
    def test_drafted_count_includes_lowercase_review(self, server_module, content_root: Path):
        # Reproduces the issue exactly: chapter.yaml status: review
        project = _write_book(content_root, "review-book")
        for n in range(1, 4):
            _write_chapter(project, f"{n:02d}-c", status="review", words=1000)
        _write_chapter(project, "04-c", status="Outline")

        result = json.loads(server_module.get_book_progress("review-book"))

        assert result["chapters_total"] == 4
        assert result["chapters_drafted"] == 3, "Bug #19: 'review' chapters must count toward chapters_drafted"

    def test_drafted_count_includes_canonical_statuses(self, server_module, content_root: Path):
        project = _write_book(content_root, "canon-book")
        _write_chapter(project, "01-a", status="Draft")
        _write_chapter(project, "02-b", status="Revision")
        _write_chapter(project, "03-c", status="Polished")
        _write_chapter(project, "04-d", status="Final")
        _write_chapter(project, "05-e", status="Outline")

        result = json.loads(server_module.get_book_progress("canon-book"))

        assert result["chapters_drafted"] == 4
        assert result["chapters_final"] == 1

    def test_completion_percent_uses_drafted_not_final(self, server_module, content_root: Path):
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

    def test_status_derived_from_chapter_state(self, server_module, content_root: Path):
        # Bug #19: book disk-status "Idea" + drafted chapters → effective "Drafting".
        project = _write_book(content_root, "stuck-on-idea", status="Idea")
        _write_chapter(project, "01-c", status="review", words=3000)
        _write_chapter(project, "02-c", status="Outline")

        result = json.loads(server_module.get_book_progress("stuck-on-idea"))

        assert result["status"] == "Drafting", (
            "Bug #19: status must reflect chapter-derived progress, not stale frontmatter"
        )

    def test_status_does_not_regress_when_book_past_drafting(self, server_module, content_root: Path):
        project = _write_book(content_root, "in-revision", status="Revision")
        _write_chapter(project, "01-c", status="Draft")  # backward chapter state

        result = json.loads(server_module.get_book_progress("in-revision"))

        assert result["status"] == "Revision"

    def test_status_unchanged_when_no_chapters_drafted(self, server_module, content_root: Path):
        project = _write_book(content_root, "still-planning", status="Plot Outlined")
        _write_chapter(project, "01-c", status="Outline")
        _write_chapter(project, "02-c", status="Outline")

        result = json.loads(server_module.get_book_progress("still-planning"))

        assert result["status"] == "Plot Outlined"


# ---------------------------------------------------------------------------
# get_book_progress: canon_facts_count per chapter (Issue #476)
# ---------------------------------------------------------------------------


class TestGetBookProgressCanonFactsCount:
    def test_reports_zero_for_chapter_with_no_facts(self, server_module, content_root: Path):
        project = _write_book(content_root, "no-facts-book")
        _write_chapter(project, "01-c", status="Draft", words=100)

        result = json.loads(server_module.get_book_progress("no-facts-book"))

        assert result["chapters"]["01-c"]["canon_facts_count"] == 0

    def test_reports_count_from_canon_facts_db(self, server_module, content_root: Path):
        from tools.db.canon_facts import insert_fact
        from tools.db.connection import open_canon_db

        project = _write_book(content_root, "facted-book")
        _write_chapter(project, "01-c", status="Draft", words=100)
        _write_chapter(project, "02-c", status="Draft", words=100)

        conn = open_canon_db("facted-book")
        try:
            insert_fact(conn, book_num=1, chapter_num=1, subject="A", fact="Fact A")
            insert_fact(conn, book_num=1, chapter_num=1, subject="B", fact="Fact B")
        finally:
            conn.close()

        result = json.loads(server_module.get_book_progress("facted-book"))

        assert result["chapters"]["01-c"]["canon_facts_count"] == 2
        assert result["chapters"]["02-c"]["canon_facts_count"] == 0

    def test_missing_readme_degrades_to_empty(self, server_module, content_root: Path):
        # Defensive path inside _canon_facts_per_chapter: a project directory
        # with no README.md (can't resolve book_num/db_slug from it) must
        # degrade to {} rather than raise.
        import routers.books as books_mod

        project = content_root / "projects" / "no-readme-book"
        project.mkdir(parents=True)

        assert books_mod._canon_facts_per_chapter("no-readme-book") == {}

    def test_unsafe_series_frontmatter_degrades_to_empty(self, server_module, content_root: Path):
        # A hand-edited `series:` value is unvalidated on read — get_db_slug_for_book
        # passes it straight to get_canon_db_path, whose slug validation raises
        # ValueError on path separators. That must degrade to {}, not propagate
        # out of a helper whose whole job is "never break get_book_progress".
        import routers.books as books_mod

        project = content_root / "projects" / "unsafe-series-book"
        project.mkdir(parents=True)
        (project / "README.md").write_text(
            '---\ntitle: "Test"\nslug: "unsafe-series-book"\nseries: "some/bad/slug"\n---\n\n# Test\n',
            encoding="utf-8",
        )

        assert books_mod._canon_facts_per_chapter("unsafe-series-book") == {}

    def test_quoted_chapter_number_still_resolves_fact_count(self, server_module, content_root: Path):
        # Issue #476 follow-up: a hand-edited `number: "3"` (quoted string,
        # not native int) must not silently miss the int-keyed fact_counts
        # dict via _coerce_chapter_number.
        from tools.db.canon_facts import insert_fact
        from tools.db.connection import open_canon_db

        project = _write_book(content_root, "quoted-number-book")
        ch_dir = project / "chapters" / "01-c"
        ch_dir.mkdir(parents=True)
        (ch_dir / "README.md").write_text("# Body\n", encoding="utf-8")
        (ch_dir / "chapter.yaml").write_text('title: "01-c"\nnumber: "1"\nstatus: "Draft"\n', encoding="utf-8")
        (ch_dir / "draft.md").write_text("word " * 100, encoding="utf-8")

        conn = open_canon_db("quoted-number-book")
        try:
            insert_fact(conn, book_num=1, chapter_num=1, subject="A", fact="Fact A")
        finally:
            conn.close()

        result = json.loads(server_module.get_book_progress("quoted-number-book"))

        assert result["chapters"]["01-c"]["canon_facts_count"] == 1

    def test_coerce_chapter_number_direct(self):
        import routers.books as books_mod

        assert books_mod._coerce_chapter_number(3) == 3
        assert books_mod._coerce_chapter_number("3") == 3
        assert books_mod._coerce_chapter_number("not-a-number") == 0
        assert books_mod._coerce_chapter_number(None) == 0

    def test_db_error_during_canon_facts_lookup_degrades_to_empty(
        self, server_module, content_root: Path, db_dir: Path
    ):
        # The except tuple also covers OSError/sqlite3.Error, not just the
        # ValueError (unsafe slug) path already regression-tested above.
        # Simulate a DB file that exists but is corrupted/unreadable.
        project = _write_book(content_root, "corrupt-db-book")
        _write_chapter(project, "01-c", status="Draft", words=100)

        db_dir.mkdir(parents=True, exist_ok=True)
        (db_dir / "corrupt-db-book.db").write_text("not a sqlite file", encoding="utf-8")

        result = json.loads(server_module.get_book_progress("corrupt-db-book"))

        assert result["chapters"]["01-c"]["canon_facts_count"] == 0

    def test_does_not_create_db_file_for_book_with_no_facts(self, server_module, content_root: Path, db_dir: Path):
        # get_book_progress carries readOnlyHint=True — it must not materialize
        # an empty <slug>.db as a side effect of a book that has no canon facts.
        project = _write_book(content_root, "no-side-effect-book")
        _write_chapter(project, "01-c", status="Draft", words=100)

        server_module.get_book_progress("no-side-effect-book")

        assert not (db_dir / "no-side-effect-book.db").exists()


# ---------------------------------------------------------------------------
# get_book_progress: reviewer/humanizer/proofreader pass tracking (Issue #479)
# ---------------------------------------------------------------------------


class TestGetBookProgressPassTracking:
    def test_defaults_false_when_fields_absent(self, server_module, content_root: Path):
        project = _write_book(content_root, "untracked-book")
        _write_chapter(project, "01-c", status="Draft", words=100)

        result = json.loads(server_module.get_book_progress("untracked-book"))

        chapter = result["chapters"]["01-c"]
        assert chapter["reviewer_pass_done"] is False
        assert chapter["humanizer_pass_done"] is False
        assert chapter["proofreader_pass_done"] is False

    def test_reports_true_after_update_field_writes(self, server_module, content_root: Path):
        project = _write_book(content_root, "tracked-book")
        ch_dir = _write_chapter(project, "01-c", status="Revision", words=100)
        (ch_dir / "chapter.yaml").write_text(
            'title: "01-c"\nstatus: "Revision"\n'
            "reviewer_pass_done: 'true'\nhumanizer_pass_done: 'true'\n",
            encoding="utf-8",
        )

        result = json.loads(server_module.get_book_progress("tracked-book"))

        chapter = result["chapters"]["01-c"]
        assert chapter["reviewer_pass_done"] is True
        assert chapter["humanizer_pass_done"] is True
        assert chapter["proofreader_pass_done"] is False

    def test_update_field_write_is_readable_by_get_book_progress(self, server_module, content_root: Path):
        # Integration test (as opposed to the two tests above, which hand-write
        # chapter.yaml to simulate what update_field() is believed to produce):
        # calls the real update_field() MCP tool — targeting chapter.yaml's
        # full-reserialize branch, the one the three revision skills actually
        # use — and reads the result back through the real get_book_progress().
        project = _write_book(content_root, "live-update-book")
        ch_dir = _write_chapter(project, "01-c", status="Revision", words=100)

        result = json.loads(server_module.update_field(str(ch_dir / "chapter.yaml"), "reviewer_pass_done", "true"))
        assert result.get("success") is True
        result = json.loads(server_module.update_field(str(ch_dir / "chapter.yaml"), "humanizer_pass_done", "true"))
        assert result.get("success") is True

        progress = json.loads(server_module.get_book_progress("live-update-book"))

        chapter = progress["chapters"]["01-c"]
        assert chapter["reviewer_pass_done"] is True
        assert chapter["humanizer_pass_done"] is True
        assert chapter["proofreader_pass_done"] is False


# ---------------------------------------------------------------------------
# Indexer surfaces derived status (so list_books, get_book, etc. are consistent)
# ---------------------------------------------------------------------------


class TestIndexerDerivedStatus:
    def test_list_books_reflects_derived_status(self, server_module, content_root: Path):
        # One drafted chapter + one still Outline → Drafting tier
        # (blocks Revision because not all chapters are at Revision rank).
        project = _write_book(content_root, "indexed-book", status="Idea")
        _write_chapter(project, "01-c", status="review", words=2000)
        _write_chapter(project, "02-c", status="Outline")

        result = json.loads(server_module.list_books())
        book = next(b for b in result["books"] if b["slug"] == "indexed-book")

        assert book["status"] == "Drafting", "Bug #19: list_books must reflect derived status from chapter state"

    def test_list_books_reflects_revision_tier(self, server_module, content_root: Path):
        # Issue #21: all chapters at review-rank → book auto-escalates to Revision.
        project = _write_book(content_root, "all-reviewed", status="Idea")
        _write_chapter(project, "01-c", status="review", words=2000)
        _write_chapter(project, "02-c", status="review", words=2000)

        result = json.loads(server_module.list_books())
        book = next(b for b in result["books"] if b["slug"] == "all-reviewed")

        assert book["status"] == "Revision"
