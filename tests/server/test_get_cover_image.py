"""Tests for get_cover_image() MCP tool — Issue #557.

Read-side counterpart to import_cover_image(): lets export-engineer (or any
skill) ask "does this book have a final cover, and where is it?" without
reaching into the DB layer directly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.cover import get_cover_image, import_cover_image


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    root.mkdir()
    return root


@pytest.fixture
def db_dir(tmp_path: Path) -> Path:
    d = tmp_path / "db"
    d.mkdir()
    return d


@pytest.fixture
def mock_env(content_root: Path, db_dir: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    cfg = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(content_root / "authors"),
        },
        "defaults": {"language": "en"},
    }
    monkeypatch.setattr(_app, "load_config", lambda: cfg)
    monkeypatch.setattr("tools.db.connection.DB_DIR", db_dir)
    _app._cache.invalidate()
    return cfg


def _make_book(content_root: Path, book_slug: str, series: str = "") -> Path:
    book_dir = content_root / "projects" / book_slug
    (book_dir / "cover" / "art").mkdir(parents=True)
    readme = f'---\ntitle: Test\nslug: {book_slug}\nseries: "{series}"\nseries_number: 1\n---\n\n# Test\n'
    (book_dir / "README.md").write_text(readme, encoding="utf-8")
    return book_dir


# #555 M-5: import_cover_image() now magic-byte-checks source files, so
# test fixtures must produce content that actually matches its extension's
# signature rather than an arbitrary placeholder.
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _make_source_image(tmp_path: Path, name: str = "cover.png", data: bytes = b"fake-png-bytes") -> Path:
    external = tmp_path / "external"
    external.mkdir(exist_ok=True)
    src = external / name
    src.write_bytes(_PNG_MAGIC + data)
    return src


class TestGetCoverImage:
    def test_missing_book_returns_error(self, mock_env, content_root: Path):
        result = json.loads(get_cover_image(book_slug="nonexistent"))
        assert "error" in result

    def test_no_cover_at_all_returns_none(self, mock_env, content_root: Path):
        _make_book(content_root, "firelight")
        result = json.loads(get_cover_image(book_slug="firelight"))
        assert result["cover_image_path"] is None
        assert result["is_final"] is False

    def test_final_cover_recorded_in_db(self, mock_env, content_root: Path, tmp_path: Path):
        book_dir = _make_book(content_root, "firelight")
        src = _make_source_image(tmp_path, name="final.png")
        import_cover_image(book_slug="firelight", source_path=str(src), is_final=True)

        result = json.loads(get_cover_image(book_slug="firelight"))

        assert result["is_final"] is True
        assert result["cover_image_path"] == str(book_dir / "cover" / "art" / "final.png")
        assert "warning" not in result

    def test_draft_only_is_not_silently_served_as_cover(self, mock_env, content_root: Path, tmp_path: Path):
        """A deliberately-recorded draft (e.g. an image-without-text preview)
        must never be silently shipped as the cover just because it's the
        only file in cover/art/ — it's tracked, not an untracked hand-placed
        file, so it must not hit the untracked-file fallback path."""
        _make_book(content_root, "firelight")
        src = _make_source_image(tmp_path, name="draft.png")
        import_cover_image(book_slug="firelight", source_path=str(src), is_final=False)

        result = json.loads(get_cover_image(book_slug="firelight"))

        assert result["is_final"] is False
        assert result["cover_image_path"] is None
        assert "warning" in result

    def test_untracked_file_alongside_recorded_draft_still_falls_back(
        self, mock_env, content_root: Path, tmp_path: Path
    ):
        book_dir = _make_book(content_root, "firelight")
        src = _make_source_image(tmp_path, name="draft.png")
        import_cover_image(book_slug="firelight", source_path=str(src), is_final=False)
        untracked = book_dir / "cover" / "art" / "hand-placed.jpg"
        untracked.write_bytes(b"x")

        result = json.loads(get_cover_image(book_slug="firelight"))

        assert result["cover_image_path"] == str(untracked)
        assert "warning" in result

    def test_final_row_with_path_traversal_filename_is_rejected(
        self, mock_env, content_root: Path, tmp_path: Path
    ):
        """final_filename comes straight out of SQLite — a hand-edited row
        containing '..' segments must not escape cover/art/ (mirrors
        update_field's containment check in routers/state.py)."""
        _make_book(content_root, "firelight")
        secret = content_root / "secret.txt"
        secret.write_bytes(b"do not leak")

        from tools.db.connection import get_db_slug_for_book, open_canon_db
        from tools.db.cover_images import upsert_cover_image as _upsert
        from tools.shared.paths import resolve_project_path as _resolve

        book_root = _resolve(mock_env, "firelight")
        conn = open_canon_db(get_db_slug_for_book(book_root))
        try:
            _upsert(conn, book_slug="firelight", filename="../../secret.txt", is_final=True)
        finally:
            conn.close()

        result = json.loads(get_cover_image(book_slug="firelight"))

        assert "error" in result

    def test_missing_art_dir_returns_none(self, mock_env, content_root: Path):
        book_dir = content_root / "projects" / "firelight"
        readme = '---\ntitle: Test\nslug: firelight\nseries: ""\nseries_number: 1\n---\n\n# Test\n'
        (book_dir).mkdir(parents=True)
        (book_dir / "README.md").write_text(readme, encoding="utf-8")

        result = json.loads(get_cover_image(book_slug="firelight"))

        assert result["cover_image_path"] is None
        assert result["is_final"] is False

    def test_fallback_to_single_untracked_file_in_cover_art(self, mock_env, content_root: Path):
        book_dir = _make_book(content_root, "firelight")
        untracked = book_dir / "cover" / "art" / "hand-placed.jpg"
        untracked.write_bytes(b"x")

        result = json.loads(get_cover_image(book_slug="firelight"))

        assert result["cover_image_path"] == str(untracked)
        assert result["is_final"] is False
        assert "warning" in result

    def test_multiple_untracked_files_no_fallback(self, mock_env, content_root: Path):
        book_dir = _make_book(content_root, "firelight")
        (book_dir / "cover" / "art" / "a.jpg").write_bytes(b"x")
        (book_dir / "cover" / "art" / "b.jpg").write_bytes(b"y")

        result = json.loads(get_cover_image(book_slug="firelight"))

        assert result["cover_image_path"] is None
        assert "warning" in result

    def test_final_row_wins_over_other_untracked_files(self, mock_env, content_root: Path, tmp_path: Path):
        book_dir = _make_book(content_root, "firelight")
        src = _make_source_image(tmp_path, name="final.png")
        import_cover_image(book_slug="firelight", source_path=str(src), is_final=True)
        # An unrelated stray file sitting alongside the tracked final cover
        # must not confuse the DB-first lookup.
        (book_dir / "cover" / "art" / "stray.jpg").write_bytes(b"z")

        result = json.loads(get_cover_image(book_slug="firelight"))

        assert result["is_final"] is True
        assert result["cover_image_path"] == str(book_dir / "cover" / "art" / "final.png")

    def test_final_row_but_file_missing_on_disk_returns_error(self, mock_env, content_root: Path, tmp_path: Path):
        book_dir = _make_book(content_root, "firelight")
        src = _make_source_image(tmp_path, name="final.png")
        import_cover_image(book_slug="firelight", source_path=str(src), is_final=True)
        (book_dir / "cover" / "art" / "final.png").unlink()

        result = json.loads(get_cover_image(book_slug="firelight"))

        assert "error" in result

    def test_null_byte_book_slug_returns_clean_error(self, mock_env, content_root: Path):
        result = json.loads(get_cover_image(book_slug="bad\x00slug"))
        assert "error" in result

    def test_ignores_non_image_files_in_fallback_scan(self, mock_env, content_root: Path):
        book_dir = _make_book(content_root, "firelight")
        (book_dir / "cover" / "art" / "notes.txt").write_bytes(b"not an image")
        image = book_dir / "cover" / "art" / "cover.png"
        image.write_bytes(b"x")

        result = json.loads(get_cover_image(book_slug="firelight"))

        assert result["cover_image_path"] == str(image)
