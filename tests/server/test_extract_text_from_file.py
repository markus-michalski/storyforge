"""Tests for the extract_text_from_file MCP tool (Issue #314, #320).

Verifies the MCP wrapper in routers.authors correctly delegates to
tools.author.pdf_extractor and returns JSON-encoded results.
Also verifies path containment guard (Issue #320 — arbitrary file read fix).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from routers.authors import extract_text_from_file


def _make_config(content_root: Path, authors_root: Path | None = None) -> dict:
    return {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(authors_root or content_root / "authors"),
        }
    }


class TestExtractTextFromFileMCPTool:
    def test_txt_file_returns_text_and_stats(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.txt"
        f.write_text("Hello world. This is a test.", encoding="utf-8")

        with patch("routers.authors._app.load_config", return_value=_make_config(tmp_path)):
            result = json.loads(extract_text_from_file(str(f)))

        assert "text" in result
        assert "Hello world" in result["text"]
        assert "stats" in result
        assert result["stats"]["word_count"] == 6

    def test_missing_file_returns_error(self, tmp_path: Path) -> None:
        with patch("routers.authors._app.load_config", return_value=_make_config(tmp_path)):
            result = json.loads(extract_text_from_file(str(tmp_path / "ghost.txt")))

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_unsupported_format_returns_error(self, tmp_path: Path) -> None:
        f = tmp_path / "file.xyz"
        f.write_text("content", encoding="utf-8")

        with patch("routers.authors._app.load_config", return_value=_make_config(tmp_path)):
            result = json.loads(extract_text_from_file(str(f)))

        assert "error" in result
        assert "Unsupported format" in result["error"]

    def test_file_too_large_returns_error(self, tmp_path: Path) -> None:
        f = tmp_path / "big.txt"
        f.write_text("word " * 100, encoding="utf-8")

        from tools.author import pdf_extractor

        with (
            patch("routers.authors._app.load_config", return_value=_make_config(tmp_path)),
            patch.object(pdf_extractor.Path, "stat") as mock_stat,
        ):
            mock_stat.return_value.st_size = pdf_extractor.MAX_FILE_SIZE_BYTES + 1
            result = json.loads(extract_text_from_file(str(f)))

        assert "error" in result

    def test_md_file_extracted_correctly(self, tmp_path: Path) -> None:
        f = tmp_path / "notes.md"
        f.write_text("# Title\n\nSome content here.", encoding="utf-8")

        with patch("routers.authors._app.load_config", return_value=_make_config(tmp_path)):
            result = json.loads(extract_text_from_file(str(f)))

        assert "text" in result
        assert "Title" in result["text"]

    def test_stats_keys_present(self, tmp_path: Path) -> None:
        f = tmp_path / "check.txt"
        f.write_text("one two three", encoding="utf-8")

        with patch("routers.authors._app.load_config", return_value=_make_config(tmp_path)):
            result = json.loads(extract_text_from_file(str(f)))

        stats = result["stats"]
        for key in ("word_count", "paragraph_count", "character_count", "estimated_pages", "sampled"):
            assert key in stats, f"Missing stats key: {key}"

    def test_importable_from_server(self) -> None:
        from server import extract_text_from_file as server_fn

        assert callable(server_fn)


class TestExtractTextFromFilePathContainment:
    """Issue #320 — path containment guard prevents arbitrary file reads."""

    def _make_config(self, content_root: Path, authors_root: Path) -> dict:
        return {
            "paths": {
                "content_root": str(content_root),
                "authors_root": str(authors_root),
            }
        }

    def test_rejects_path_outside_allowed_roots(self, tmp_path: Path) -> None:
        content_root = tmp_path / "books"
        authors_root = tmp_path / "authors"
        content_root.mkdir()
        authors_root.mkdir()

        evil = tmp_path / "secret.txt"
        evil.write_text("secret", encoding="utf-8")

        with patch("routers.authors._app.load_config", return_value=self._make_config(content_root, authors_root)):
            result = json.loads(extract_text_from_file(str(evil)))

        assert "error" in result
        assert "content_root or authors_root" in result["error"]

    def test_rejects_etc_passwd(self, tmp_path: Path) -> None:
        content_root = tmp_path / "books"
        authors_root = tmp_path / "authors"
        content_root.mkdir()
        authors_root.mkdir()

        with patch("routers.authors._app.load_config", return_value=self._make_config(content_root, authors_root)):
            result = json.loads(extract_text_from_file("/etc/passwd"))

        assert "error" in result
        assert "content_root or authors_root" in result["error"]

    def test_accepts_file_inside_content_root(self, tmp_path: Path) -> None:
        content_root = tmp_path / "books"
        authors_root = tmp_path / "authors"
        content_root.mkdir()
        authors_root.mkdir()

        legit = content_root / "my-book.txt"
        legit.write_text("Once upon a time.", encoding="utf-8")

        with patch("routers.authors._app.load_config", return_value=self._make_config(content_root, authors_root)):
            result = json.loads(extract_text_from_file(str(legit)))

        assert "text" in result
        assert "Once upon a time" in result["text"]

    def test_accepts_file_inside_authors_root(self, tmp_path: Path) -> None:
        content_root = tmp_path / "books"
        authors_root = tmp_path / "authors"
        content_root.mkdir()
        authors_root.mkdir()

        legit = authors_root / "sample.txt"
        legit.write_text("Author voice sample.", encoding="utf-8")

        with patch("routers.authors._app.load_config", return_value=self._make_config(content_root, authors_root)):
            result = json.loads(extract_text_from_file(str(legit)))

        assert "text" in result
        assert "Author voice" in result["text"]

    def test_rejects_null_byte_in_path(self, tmp_path: Path) -> None:
        content_root = tmp_path / "books"
        authors_root = tmp_path / "authors"
        content_root.mkdir()
        authors_root.mkdir()

        with patch("routers.authors._app.load_config", return_value=self._make_config(content_root, authors_root)):
            result = json.loads(extract_text_from_file("/tmp/\x00evil.txt"))

        assert "error" in result
        assert "Invalid file_path" in result["error"]

    def test_rejects_traversal_via_symlink_resolution(self, tmp_path: Path) -> None:
        content_root = tmp_path / "books"
        authors_root = tmp_path / "authors"
        content_root.mkdir()
        authors_root.mkdir()

        secret = tmp_path / "secret.md"
        secret.write_text("# Secret", encoding="utf-8")

        # Symlink inside content_root pointing outside
        link = content_root / "escape.md"
        link.symlink_to(secret)

        with patch("routers.authors._app.load_config", return_value=self._make_config(content_root, authors_root)):
            # resolve() follows symlinks — the resolved path is outside content_root
            result = json.loads(extract_text_from_file(str(link)))

        # Symlink target is outside content_root — must be rejected
        assert "error" in result
        assert "content_root or authors_root" in result["error"]
