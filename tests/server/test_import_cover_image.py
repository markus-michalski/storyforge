"""Tests for import_cover_image() MCP tool — Issue #551."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

import routers._app as _app
import routers.cover as cover_module
from routers.cover import import_cover_image


def _symlinks_supported() -> bool:
    """Probe whether the current process can create symlinks.

    On Windows, os.symlink()/Path.symlink_to() require either an elevated
    (admin) process or Developer Mode enabled — a stock, non-elevated dev
    machine without Developer Mode raises OSError (WinError 1314,
    ERROR_PRIVILEGE_NOT_HELD) for every call, independent of anything the
    test under it actually exercises (issue #541 established this probe
    pattern; reused here rather than duplicated with variations).
    """
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "target"
        target.mkdir()
        try:
            (Path(tmp) / "link").symlink_to(target, target_is_directory=True)
        except OSError:
            return False
    return True


_SYMLINKS_SUPPORTED = _symlinks_supported()


class _FailingWriter:
    """Wraps a real binary file handle; the first write() lands, then
    raises — simulating a disk-full/mid-copy failure after some bytes
    already made it to disk (#555 M-2 orphan-cleanup regression test).
    A plain function-attribute swap doesn't work here: the file objects
    returned by Path.open() are C-implemented io types with no per-instance
    __dict__, so wrapping is the reliable way to inject the fault.
    """

    def __init__(self, real):
        self._real = real

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self._real.close()
        return False

    def write(self, data):
        self._real.write(data)
        raise OSError("simulated disk-full mid-copy")

    def close(self):
        self._real.close()


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
_MAGIC_PREFIXES = {
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".gif": b"GIF89a",
    ".webp": b"RIFF\x00\x00\x00\x00WEBP",
}


def _make_source_image(tmp_path: Path, name: str = "cover.png", data: bytes = b"fake-png-bytes") -> Path:
    external = tmp_path / "external"
    external.mkdir(exist_ok=True)
    src = external / name
    prefix = _MAGIC_PREFIXES.get(Path(name).suffix.lower(), b"")
    src.write_bytes(prefix + data)
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
        assert dest.read_bytes() == _MAGIC_PREFIXES[".png"] + b"fake-png-bytes"
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
        src2.write_bytes(_MAGIC_PREFIXES[".png"] + b"version-two")
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
        src2.write_bytes(_MAGIC_PREFIXES[".png"] + b"version-two")
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


class TestImportCoverImageHardening:
    """Issue #555: findings M-1, M-5, L-5, L-6 from the #551 code review."""

    def test_relative_source_path_rejected(self, mock_env, content_root: Path, tmp_path: Path, monkeypatch):
        _make_book(content_root, "firelight")
        _make_source_image(tmp_path)
        monkeypatch.chdir(tmp_path)
        result = json.loads(import_cover_image(book_slug="firelight", source_path="external/cover.png"))
        assert "error" in result
        assert "absolute" in result["error"]

    def test_empty_source_file_rejected(self, mock_env, content_root: Path, tmp_path: Path):
        _make_book(content_root, "firelight")
        external = tmp_path / "external"
        external.mkdir()
        src = external / "cover.png"
        src.write_bytes(b"")
        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src)))
        assert "error" in result
        assert "empty" in result["error"]

    def test_oversized_source_file_rejected(self, mock_env, content_root: Path, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(cover_module, "_MAX_COVER_IMAGE_BYTES", 16)
        _make_book(content_root, "firelight")
        src = _make_source_image(tmp_path, data=b"0123456789012345")  # 16 bytes + magic prefix > cap
        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src)))
        assert "error" in result
        assert "size cap" in result["error"]

    def test_wrong_magic_bytes_rejected(self, mock_env, content_root: Path, tmp_path: Path):
        _make_book(content_root, "firelight")
        external = tmp_path / "external"
        external.mkdir()
        src = external / "cover.png"
        src.write_bytes(b"this is not actually a png file")
        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src)))
        assert "error" in result
        assert "magic-byte" in result["error"]

    def test_book_root_escaping_content_root_is_rejected(
        self, mock_env, content_root: Path, tmp_path: Path, monkeypatch
    ):
        """#555 M-1: dest_dir was previously built from the *unresolved*
        book_root while content_root is always .resolve()d — assert
        containment explicitly rather than relying on the two staying
        consistent by construction."""
        _make_book(content_root, "firelight")
        src = _make_source_image(tmp_path)
        outside = tmp_path / "outside-content-root"
        outside.mkdir()
        monkeypatch.setattr(cover_module, "resolve_project_path", lambda config, slug: outside)

        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src)))

        assert "error" in result
        assert "content_root" in result["error"]

    @pytest.mark.skipif(
        not _SYMLINKS_SUPPORTED,
        reason="symlink creation needs elevated privileges or Developer Mode on Windows (issue #541)",
    )
    def test_symlinked_cover_art_dir_escaping_content_root_is_rejected(
        self, mock_env, content_root: Path, tmp_path: Path
    ):
        """#555 M-1 (HIGH-1 from review): the book_root containment check
        alone doesn't cover dest_dir, which adds "cover"/"art" components
        after that check — if either is a symlink pointing outside
        content_root, mkdir()/the copy would follow it right out of the
        managed tree. This pins that dest_dir itself must be re-resolved
        and re-checked."""
        book_dir = _make_book(content_root, "firelight")
        art_dir = book_dir / "cover" / "art"
        art_dir.rmdir()  # replace the plain directory with a symlink out
        outside = tmp_path / "outside-content-root"
        outside.mkdir()
        art_dir.symlink_to(outside, target_is_directory=True)

        src = _make_source_image(tmp_path)
        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src)))

        assert "error" in result
        assert "content_root" in result["error"]
        assert list(outside.iterdir()) == []

    def test_size_cap_boundary_is_inclusive(self, mock_env, content_root: Path, tmp_path: Path, monkeypatch):
        """Exactly at the cap must be accepted — only strictly over it
        should be rejected."""
        monkeypatch.setattr(cover_module, "_MAX_COVER_IMAGE_BYTES", 32)
        _make_book(content_root, "firelight")
        payload = b"0" * (32 - len(_MAGIC_PREFIXES[".png"]))
        src = _make_source_image(tmp_path, data=payload)

        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src)))

        assert result.get("success") is True

    @pytest.mark.parametrize("ext", [".png", ".jpg", ".jpeg", ".gif", ".webp"])
    def test_each_allowed_extension_with_valid_magic_bytes_is_accepted(
        self, mock_env, content_root: Path, tmp_path: Path, ext
    ):
        _make_book(content_root, "firelight")
        src = _make_source_image(tmp_path, name=f"cover{ext}", data=b"payload")

        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src)))

        assert result.get("success") is True

    def test_webp_riff_container_without_webp_marker_is_rejected(
        self, mock_env, content_root: Path, tmp_path: Path
    ):
        """A RIFF-format file that isn't WebP (e.g. a renamed .wav) must not
        pass just because it shares the generic RIFF container header."""
        _make_book(content_root, "firelight")
        external = tmp_path / "external"
        external.mkdir()
        src = external / "cover.webp"
        src.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")

        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src)))

        assert "error" in result
        assert "magic-byte" in result["error"]

    def test_copy_failure_leaves_no_orphaned_partial_file(
        self, mock_env, content_root: Path, tmp_path: Path, monkeypatch
    ):
        """#555 M-2: a mid-copy failure must not leave a truncated file with
        no matching cover_images row — that file would permanently block
        re-importing the same name (every retry sees it as an existing,
        different file)."""
        book_dir = _make_book(content_root, "firelight")
        src = _make_source_image(tmp_path, data=b"a lot of payload bytes here")

        original_open = Path.open

        def _flaky_open(self, mode="r", *args, **kwargs):
            handle = original_open(self, mode, *args, **kwargs)
            if self.name == "cover.png" and "x" in mode:
                return _FailingWriter(handle)
            return handle

        monkeypatch.setattr(Path, "open", _flaky_open)

        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src)))

        assert "error" in result
        art_files = list((book_dir / "cover" / "art").iterdir())
        assert art_files == []

    def test_source_inside_authors_root_is_rejected(self, mock_env, content_root: Path, tmp_path: Path):
        _make_book(content_root, "firelight")
        authors_root = Path(mock_env["paths"]["authors_root"])
        authors_root.mkdir(parents=True, exist_ok=True)
        src = authors_root / "headshot.png"
        src.write_bytes(_MAGIC_PREFIXES[".png"] + b"x")
        result = json.loads(import_cover_image(book_slug="firelight", source_path=str(src)))
        assert "error" in result


class TestCopyExclusiveWithRetry:
    """Issue #555 L-6: TOCTOU between _resolve_dest_path()'s .exists()
    check and the actual write. These exercise _copy_exclusive_with_retry()
    directly by simulating a race — pre-creating the destination between
    the (already-run) decision and the write it's given."""

    def test_writes_when_destination_is_free(self, tmp_path: Path):
        dest_dir = tmp_path / "art"
        dest_dir.mkdir()
        src = tmp_path / "src.png"
        src.write_bytes(b"content")
        dest = dest_dir / "cover.png"

        result = cover_module._copy_exclusive_with_retry(dest_dir, src, dest)

        assert result == dest
        assert dest.read_bytes() == b"content"

    def test_race_with_different_content_retries_to_next_suffix(self, tmp_path: Path):
        dest_dir = tmp_path / "art"
        dest_dir.mkdir()
        src = tmp_path / "cover.png"
        src.write_bytes(b"new-content")
        dest = dest_dir / "cover.png"
        # Simulate a concurrent import winning the race and claiming `dest`
        # with different content after _resolve_dest_path already decided
        # this call should use it.
        dest.write_bytes(b"raced-content")

        result = cover_module._copy_exclusive_with_retry(dest_dir, src, dest)

        assert result == dest_dir / "cover-2.png"
        assert result.read_bytes() == b"new-content"
        assert dest.read_bytes() == b"raced-content"

    def test_race_with_identical_content_reuses_file(self, tmp_path: Path):
        dest_dir = tmp_path / "art"
        dest_dir.mkdir()
        src = tmp_path / "src.png"
        src.write_bytes(b"same-content")
        dest = dest_dir / "cover.png"
        dest.write_bytes(b"same-content")

        result = cover_module._copy_exclusive_with_retry(dest_dir, src, dest)

        assert result == dest

    def test_overflow_raises_runtime_error(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(cover_module, "_MAX_COVER_VARIANTS", 2)
        dest_dir = tmp_path / "art"
        dest_dir.mkdir()
        src = tmp_path / "cover.png"
        src.write_bytes(b"new-content")
        dest = dest_dir / "cover.png"
        dest.write_bytes(b"raced-a")
        (dest_dir / "cover-2.png").write_bytes(b"raced-b")

        with pytest.raises(RuntimeError):
            cover_module._copy_exclusive_with_retry(dest_dir, src, dest)
