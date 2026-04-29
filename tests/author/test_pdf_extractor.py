"""Tests for tools.author.pdf_extractor — Issue #124."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.author.pdf_extractor import (
    MAX_FILE_SIZE_BYTES,
    _sample_text,
    extract_text_from_file,
    get_supported_formats,
    get_text_stats,
)


# ---------------------------------------------------------------------------
# get_supported_formats
# ---------------------------------------------------------------------------


def test_get_supported_formats_returns_list():
    result = get_supported_formats()
    assert isinstance(result, list)
    assert ".pdf" in result
    assert ".epub" in result
    assert ".txt" in result
    assert ".docx" in result


# ---------------------------------------------------------------------------
# extract_text_from_file — error paths
# ---------------------------------------------------------------------------


class TestExtractTextErrors:
    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            extract_text_from_file(tmp_path / "missing.txt")

    def test_unsupported_format_raises(self, tmp_path):
        f = tmp_path / "book.xyz"
        f.write_text("content", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported format"):
            extract_text_from_file(f)

    def test_file_too_large_raises(self, tmp_path, monkeypatch):
        f = tmp_path / "huge.txt"
        f.write_text("x", encoding="utf-8")
        # Patch stat so size exceeds MAX_FILE_SIZE_BYTES
        mock_stat = MagicMock()
        mock_stat.st_size = MAX_FILE_SIZE_BYTES + 1
        monkeypatch.setattr(Path, "stat", lambda self, *, follow_symlinks=True: mock_stat)
        with pytest.raises(ValueError, match="File too large"):
            extract_text_from_file(f)


# ---------------------------------------------------------------------------
# extract_text_from_file — plain text formats
# ---------------------------------------------------------------------------


class TestExtractTextPlain:
    def test_txt_file(self, tmp_path):
        f = tmp_path / "book.txt"
        f.write_text("Hello world", encoding="utf-8")
        assert extract_text_from_file(f) == "Hello world"

    def test_md_file(self, tmp_path):
        f = tmp_path / "book.md"
        f.write_text("# Chapter\n\nContent.", encoding="utf-8")
        assert "Content." in extract_text_from_file(f)

    def test_markdown_extension(self, tmp_path):
        f = tmp_path / "book.markdown"
        f.write_text("Text here.", encoding="utf-8")
        assert extract_text_from_file(f) == "Text here."


# ---------------------------------------------------------------------------
# extract_text_from_file — word-limit sampling
# ---------------------------------------------------------------------------


class TestWordLimitSampling:
    def test_large_text_gets_sampled(self, tmp_path):
        words = ["word"] * 210_000
        f = tmp_path / "big.txt"
        f.write_text(" ".join(words), encoding="utf-8")
        result = extract_text_from_file(f)
        assert "[--- BEGINNING" in result
        assert "[--- MIDDLE" in result
        assert "[--- END" in result

    def test_small_text_not_sampled(self, tmp_path):
        f = tmp_path / "small.txt"
        f.write_text("Just a few words.", encoding="utf-8")
        result = extract_text_from_file(f)
        assert "[--- BEGINNING" not in result


# ---------------------------------------------------------------------------
# _sample_text — pure function
# ---------------------------------------------------------------------------


class TestSampleText:
    def test_returns_all_three_sections(self):
        words = ["w"] * 300_000
        text = " ".join(words)
        result = _sample_text(text, words)
        assert "[--- BEGINNING" in result
        assert "[--- MIDDLE" in result
        assert "[--- END" in result

    def test_sampled_text_shorter_than_original(self):
        words = ["word"] * 300_000
        text = " ".join(words)
        result = _sample_text(text, words)
        assert len(result.split()) < len(words)


# ---------------------------------------------------------------------------
# _extract_from_pdf — mocked
# ---------------------------------------------------------------------------


class TestExtractFromPdf:
    def test_pdf_extraction_calls_fitz(self, tmp_path):
        f = tmp_path / "book.pdf"
        f.write_bytes(b"%PDF-1.5\nfake pdf content")

        mock_page = MagicMock()
        mock_page.get_text.return_value = "Page text content."
        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            result = extract_text_from_file(f)

        assert "Page text content." in result
        mock_doc.close.assert_called_once()

    def test_pdf_missing_fitz_raises_import_error(self, tmp_path):
        f = tmp_path / "book.pdf"
        f.write_bytes(b"%PDF-1.5\nfake")

        with patch.dict("sys.modules", {"fitz": None}):
            with pytest.raises((ImportError, TypeError)):
                extract_text_from_file(f)


# ---------------------------------------------------------------------------
# _extract_from_epub — real zip
# ---------------------------------------------------------------------------


class TestExtractFromEpub:
    def test_epub_extracts_html_content(self, tmp_path):
        f = tmp_path / "book.epub"
        with zipfile.ZipFile(str(f), "w") as zf:
            zf.writestr(
                "OEBPS/chapter1.xhtml",
                "<html><body><p>" + "A" * 200 + "</p></body></html>",
            )
            zf.writestr("META-INF/container.xml", "<container/>")

        result = extract_text_from_file(f)
        assert "A" * 10 in result

    def test_epub_skips_short_files(self, tmp_path):
        f = tmp_path / "book.epub"
        with zipfile.ZipFile(str(f), "w") as zf:
            zf.writestr("OEBPS/toc.xhtml", "<nav><ol><li>TOC</li></ol></nav>")

        result = extract_text_from_file(f)
        assert result == ""


# ---------------------------------------------------------------------------
# _extract_from_docx — mocked
# ---------------------------------------------------------------------------


class TestExtractFromDocx:
    def test_docx_extraction_calls_docx(self, tmp_path):
        f = tmp_path / "book.docx"
        f.write_bytes(b"PK fake docx content")

        mock_para1 = MagicMock()
        mock_para1.text = "First paragraph."
        mock_para2 = MagicMock()
        mock_para2.text = ""
        mock_para3 = MagicMock()
        mock_para3.text = "Third paragraph."

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3]
        mock_docx_module = MagicMock()
        mock_docx_module.Document.return_value = mock_doc

        with patch.dict("sys.modules", {"docx": mock_docx_module}):
            result = extract_text_from_file(f)

        assert "First paragraph." in result
        assert "Third paragraph." in result

    def test_docx_missing_module_raises_import_error(self, tmp_path):
        f = tmp_path / "book.docx"
        f.write_bytes(b"PK fake")

        with patch.dict("sys.modules", {"docx": None}):
            with pytest.raises((ImportError, TypeError)):
                extract_text_from_file(f)


# ---------------------------------------------------------------------------
# get_text_stats — pure function
# ---------------------------------------------------------------------------


class TestGetTextStats:
    def test_word_count(self):
        stats = get_text_stats("one two three")
        assert stats["word_count"] == 3

    def test_paragraph_count(self):
        stats = get_text_stats("Para one.\n\nPara two.\n\nPara three.")
        assert stats["paragraph_count"] == 3

    def test_character_count(self):
        text = "hello"
        stats = get_text_stats(text)
        assert stats["character_count"] == 5

    def test_estimated_pages(self):
        text = " ".join(["word"] * 500)
        stats = get_text_stats(text)
        assert stats["estimated_pages"] == 2

    def test_sampled_flag_true(self):
        stats = get_text_stats("[--- BEGINNING (words 1-30,000) ---]\n\ncontent")
        assert stats["sampled"] is True

    def test_sampled_flag_false(self):
        stats = get_text_stats("Normal text.")
        assert stats["sampled"] is False
