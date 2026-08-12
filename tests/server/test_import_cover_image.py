"""Tests for import_cover_image() MCP tool — Issue #551."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.cover import import_cover_image


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


def _make_source_image(tmp_path: Path, name: str = "cover.png", data: bytes = b"fake-png-bytes") -> Path:
    external = tmp_path / "external"
    external.mkdir(exist_ok=True)
    src = external / name
    src.write_bytes(data)
    return src


class TestImportCoverImage:
    def test_copies_draft_into_cover_art_dir(self, mock_env, content_root: Path, tmp_path: Path):
        book_dir = _make_book(content_root, "firelight")
        src = _make_source_image(tmp_path)

        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src)))

        assert result.get("success") is True
        assert result["is_final"] is False
        dest = book_dir / "cover" / "art" / "cover.png"
        assert dest.exists()
        assert dest.read_bytes() == b"fake-png-bytes"
        assert result["cover_image_path"] == str(dest)

    def test_imports_final_version(self, mock_env, content_root: Path, tmp_path: Path):
        _make_book(content_root, "firelight")
        src = _make_source_image(tmp_path, name="final.png")

        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src), is_final=True))

        assert result.get("success") is True
        assert result["is_final"] is True

    def test_missing_book_returns_error(self, mock_env, content_root: Path, tmp_path: Path):
        src = _make_source_image(tmp_path)
        result = json.loads(import_cover_image(book_slug="nonexistent", source_path=str(src)))
        assert "error" in result

    def test_missing_source_file_returns_error(self, mock_env, content_root: Path, tmp_path: Path):
        _make_book(content_root, "firelight")
        missing = tmp_path / "external" / "does-not-exist.png"
        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(missing)))
        assert "error" in result

    def test_unsupported_extension_returns_error(self, mock_env, content_root: Path, tmp_path: Path):
        _make_book(content_root, "firelight")
        src = _make_source_image(tmp_path, name="cover.txt")
        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src)))
        assert "error" in result

    def test_source_inside_content_root_is_rejected(self, mock_env, content_root: Path, tmp_path: Path):
        _make_book(content_root, "firelight")
        # Point source_path at a file that's already inside content_root —
        # e.g. another book's cover art. Must be refused, not copied.
        other_book = _make_book(content_root, "other-book")
        src = other_book / "cover" / "art" / "existing.png"
        src.write_bytes(b"x")
        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src)))
        assert "error" in result

    def test_null_byte_book_slug_returns_clean_error(self, mock_env, content_root: Path, tmp_path: Path):
        src = _make_source_image(tmp_path)
        result = json.loads(import_cover_image(book_slug="bad\x00slug", source_path=str(src)))
        assert "error" in result

    def test_null_byte_source_path_returns_clean_error(self, mock_env, content_root: Path, tmp_path: Path):
        _make_book(content_root, "firelight")
        result = json.loads(import_cover_image(book_slug="firelight", source_path="bad\x00path.png"))
        assert "error" in result

    def test_reimport_same_file_is_idempotent(self, mock_env, content_root: Path, tmp_path: Path):
        book_dir = _make_book(content_root, "firelight")
        src = _make_source_image(tmp_path)

        import_cover_image(book_slug="firelight", source_path=str(src))
        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src), is_final=True))

        assert result.get("success") is True
        art_files = list((book_dir / "cover" / "art").glob("*.png"))
        assert len(art_files) == 1

    def test_different_file_same_name_gets_suffixed(self, mock_env, content_root: Path, tmp_path: Path):
        book_dir = _make_book(content_root, "firelight")
        src1 = _make_source_image(tmp_path, name="cover.png", data=b"version-one")
        import_cover_image(book_slug="firelight", source_path=str(src1))

        src2_dir = tmp_path / "external2"
        src2_dir.mkdir()
        src2 = src2_dir / "cover.png"
        src2.write_bytes(b"version-two")
        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src2)))

        assert result.get("success") is True
        assert result["filename"] == "cover-2.png"
        art_files = sorted(p.name for p in (book_dir / "cover" / "art").glob("*.png"))
        assert art_files == ["cover-2.png", "cover.png"]

    def test_reimport_after_name_collision_is_idempotent(self, mock_env, content_root: Path, tmp_path: Path):
        """Issue #551 code review H-1: once a source file has been stored
        under a suffixed name (because its original filename collided with
        a different file), re-importing that same source must reuse the
        suffixed file — not grow a new copy/DB row on every call."""
        book_dir = _make_book(content_root, "firelight")
        src1 = _make_source_image(tmp_path, name="cover.png", data=b"version-one")
        import_cover_image(book_slug="firelight", source_path=str(src1))

        src2_dir = tmp_path / "external2"
        src2_dir.mkdir()
        src2 = src2_dir / "cover.png"
        src2.write_bytes(b"version-two")
        import_cover_image(book_slug="firelight", source_path=str(src2))

        # Re-import src2 (already stored as cover-2.png) twice more.
        for _ in range(2):
            result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src2)))
            assert result.get("success") is True
            assert result["filename"] == "cover-2.png"

        art_files = sorted(p.name for p in (book_dir / "cover" / "art").glob("*.png"))
        assert art_files == ["cover-2.png", "cover.png"]

    def test_variant_overflow_returns_clean_error(self, mock_env, content_root: Path, tmp_path: Path, monkeypatch):
        """The _MAX_COVER_VARIANTS safety cap raises RuntimeError inside
        _resolve_dest_path(); the tool must convert that into the standard
        {"error": ...} contract, not let it propagate as a raw exception."""
        import routers.cover as cover_module

        monkeypatch.setattr(cover_module, "_MAX_COVER_VARIANTS", 2)
        book_dir = _make_book(content_root, "firelight")
        art_dir = book_dir / "cover" / "art"

        (art_dir / "cover.png").write_bytes(b"existing-1")
        (art_dir / "cover-2.png").write_bytes(b"existing-2")

        src = _make_source_image(tmp_path, name="cover.png", data=b"new-content")
        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src)))

        assert "error" in result

    def test_marking_new_final_clears_previous_final(self, mock_env, content_root: Path, tmp_path: Path):
        _make_book(content_root, "firelight")
        src1 = _make_source_image(tmp_path, name="final-a.png", data=b"a")
        src2 = _make_source_image(tmp_path, name="final-b.png", data=b"b")

        import_cover_image(book_slug="firelight", source_path=str(src1), is_final=True)
        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src2), is_final=True))

        assert result.get("success") is True

        from tools.db.connection import get_db_slug_for_book, open_canon_db
        from tools.db.cover_images import get_final_cover_image
        from tools.shared.paths import resolve_project_path

        book_root = resolve_project_path(mock_env, "firelight")
        conn = open_canon_db(get_db_slug_for_book(book_root))
        try:
            assert get_final_cover_image(conn, book_num=1) == "final-b.png"
        finally:
            conn.close()
