"""Tests for the extract_text_from_file MCP tool (Issue #314).

Verifies the MCP wrapper in routers.authors correctly delegates to
tools.author.pdf_extractor and returns JSON-encoded results.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from routers.authors import extract_text_from_file


class TestExtractTextFromFileMCPTool:
    def test_txt_file_returns_text_and_stats(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.txt"
        f.write_text("Hello world. This is a test.", encoding="utf-8")

        result = json.loads(extract_text_from_file(str(f)))

        assert "text" in result
        assert "Hello world" in result["text"]
        assert "stats" in result
        assert result["stats"]["word_count"] == 6

    def test_missing_file_returns_error(self, tmp_path: Path) -> None:
        result = json.loads(extract_text_from_file(str(tmp_path / "ghost.txt")))

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_unsupported_format_returns_error(self, tmp_path: Path) -> None:
        f = tmp_path / "file.xyz"
        f.write_text("content", encoding="utf-8")

        result = json.loads(extract_text_from_file(str(f)))

        assert "error" in result
        assert "Unsupported format" in result["error"]

    def test_file_too_large_returns_error(self, tmp_path: Path) -> None:
        f = tmp_path / "big.txt"
        f.write_text("word " * 100, encoding="utf-8")

        from tools.author import pdf_extractor

        with patch.object(pdf_extractor.Path, "stat") as mock_stat:
            mock_stat.return_value.st_size = pdf_extractor.MAX_FILE_SIZE_BYTES + 1
            result = json.loads(extract_text_from_file(str(f)))

        assert "error" in result

    def test_md_file_extracted_correctly(self, tmp_path: Path) -> None:
        f = tmp_path / "notes.md"
        f.write_text("# Title\n\nSome content here.", encoding="utf-8")

        result = json.loads(extract_text_from_file(str(f)))

        assert "text" in result
        assert "Title" in result["text"]

    def test_stats_keys_present(self, tmp_path: Path) -> None:
        f = tmp_path / "check.txt"
        f.write_text("one two three", encoding="utf-8")

        result = json.loads(extract_text_from_file(str(f)))

        stats = result["stats"]
        for key in ("word_count", "paragraph_count", "character_count", "estimated_pages", "sampled"):
            assert key in stats, f"Missing stats key: {key}"

    def test_importable_from_server(self) -> None:
        from server import extract_text_from_file as server_fn

        assert callable(server_fn)
