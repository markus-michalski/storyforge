"""Tests for the delete_author MCP tool — Issue #385.

delete_author removes an author profile directory plus every author_discoveries
row for the author. It refuses when a book's README ``author`` field still
references the slug (unless force=True), so deleting an author can't silently
orphan books.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.authors import delete_author
from tools.db.author_discoveries import get_discoveries, insert_discovery


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def author_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Config pointing at tmp dirs with an ``ethan-cole`` author profile.

    Patches tools.db.connection.DB_DIR so authors.db lands in tmp_path.
    """
    content_root = tmp_path / "books"
    content_root.mkdir()
    authors_root = tmp_path / "authors"
    authors_root.mkdir()

    author_dir = authors_root / "ethan-cole"
    author_dir.mkdir()
    (author_dir / "profile.md").write_text(
        '---\nname: "Ethan Cole"\nslug: "ethan-cole"\n---\n\n# Ethan Cole\n',
        encoding="utf-8",
    )
    # A couple of subdir files, to prove the whole tree is removed.
    (author_dir / "vocabulary.md").write_text("# vocab\n", encoding="utf-8")
    (author_dir / "studied-works").mkdir()

    config = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(authors_root),
        },
    }
    monkeypatch.setattr(_app, "load_config", lambda: config)
    _app._cache.invalidate()

    import tools.db.connection as conn_mod
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(conn_mod, "DB_DIR", db_dir)

    return {
        "config": config,
        "authors_root": authors_root,
        "author_dir": author_dir,
        "content_root": content_root,
        "db_dir": db_dir,
    }


def _make_book(content_root: Path, slug: str, author: str) -> Path:
    """Create a minimal book project README referencing ``author`` (a slug)."""
    proj = content_root / "projects" / slug
    proj.mkdir(parents=True)
    (proj / "README.md").write_text(
        f'---\ntitle: "{slug}"\nauthor: "{author}"\n---\n\n# {slug}\n',
        encoding="utf-8",
    )
    return proj


def _seed_discovery(text: str, author_slug: str = "ethan-cole") -> None:
    from tools.db.connection import open_authors_db

    conn = open_authors_db()
    try:
        insert_discovery(conn, author_slug=author_slug, discovery_type="donts", text=text)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestDeleteAuthor:
    def test_deletes_existing_author_directory(self, author_env):
        result = json.loads(delete_author("ethan-cole"))

        assert result["success"] is True
        assert result["slug"] == "ethan-cole"
        assert not author_env["author_dir"].exists()
        assert result["referencing_books"] == []

    def test_removes_discoveries_from_db(self, author_env):
        _seed_discovery("**thing** — concretize on sight.")
        _seed_discovery("**stuff** — name it.")

        result = json.loads(delete_author("ethan-cole"))
        assert result["success"] is True
        assert result["removed_discoveries"] == 2

        from tools.db.connection import open_authors_db

        conn = open_authors_db()
        try:
            assert get_discoveries(conn, "ethan-cole") == []
        finally:
            conn.close()

    def test_invalidates_cache(self, author_env, monkeypatch):
        # A successful delete must invalidate the shared state cache so later
        # list_authors()/get_author() calls don't surface the removed author.
        calls = {"n": 0}
        original = _app._cache.invalidate
        monkeypatch.setattr(
            _app._cache,
            "invalidate",
            lambda: (calls.__setitem__("n", calls["n"] + 1), original())[1],
        )

        result = json.loads(delete_author("ethan-cole"))
        assert result["success"] is True
        assert calls["n"] >= 1


# ---------------------------------------------------------------------------
# Reference integrity
# ---------------------------------------------------------------------------


class TestReferenceIntegrity:
    def test_refuses_when_a_book_references_the_author(self, author_env):
        _make_book(author_env["content_root"], "midnight-run", "ethan-cole")

        result = json.loads(delete_author("ethan-cole"))

        assert "error" in result
        assert "midnight-run" in result["referencing_books"]
        assert "midnight-run" in result["error"]
        # Nothing deleted.
        assert author_env["author_dir"].exists()

    def test_force_deletes_despite_reference(self, author_env):
        _make_book(author_env["content_root"], "midnight-run", "ethan-cole")

        result = json.loads(delete_author("ethan-cole", force=True))

        assert result["success"] is True
        assert result["referencing_books"] == ["midnight-run"]
        assert not author_env["author_dir"].exists()
        # Message should warn about the now-orphaned book.
        assert "midnight-run" in result["message"]

    def test_detects_reference_in_series_nested_book(self, author_env):
        # find_projects() also scans content_root/series/*/ — a series-nested
        # book referencing the author must block just like a projects/ book.
        series_book = author_env["content_root"] / "series" / "firelight" / "book-one"
        series_book.mkdir(parents=True)
        (series_book / "README.md").write_text(
            '---\ntitle: "Book One"\nauthor: "ethan-cole"\n---\n\n# Book One\n',
            encoding="utf-8",
        )

        result = json.loads(delete_author("ethan-cole"))

        assert "error" in result
        assert "book-one" in result["referencing_books"]
        assert author_env["author_dir"].exists()

    def test_reference_check_ignores_other_authors(self, author_env):
        _make_book(author_env["content_root"], "someone-elses-book", "other-author")

        result = json.loads(delete_author("ethan-cole"))

        assert result["success"] is True
        assert not author_env["author_dir"].exists()


# ---------------------------------------------------------------------------
# Guard rails
# ---------------------------------------------------------------------------


class TestGuardRails:
    def test_author_not_found(self, author_env):
        result = json.loads(delete_author("ghost-writer"))
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_rejects_empty_slug(self, author_env):
        result = json.loads(delete_author("   "))
        assert "error" in result
        # authors_root itself must never be touched.
        assert author_env["authors_root"].exists()

    def test_rejects_path_traversal_slug(self, author_env):
        result = json.loads(delete_author("../authors"))
        assert "error" in result
        assert author_env["author_dir"].exists()
