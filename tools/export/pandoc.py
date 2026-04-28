"""Pandoc wrapper for StoryForge — EPUB, PDF, and MOBI generation."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

# Audit M1 (#117): pandoc forwards LaTeX, and xelatex respects
# ``-shell-escape``. Without an allowlist these args could carry
# ``\input{/etc/passwd}``, ``\write18{...}``, or shell-escape pivots.
_ALLOWED_PDF_ENGINES = frozenset({
    "xelatex",
    "lualatex",
    "pdflatex",
    "context",
    "tectonic",
    "wkhtmltopdf",
    "weasyprint",
    "prince",
})

# Fonts: alphanumerics, spaces, hyphens, dots, underscores. Excludes the
# shell metacharacters and LaTeX command introducers (``\``, ``{``, ``}``,
# ``$``, ``;``, ``|``, newlines).
_FONT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-_.]{0,63}$")

# font_size: 1–2 digits + pt or em, e.g. "11pt", "12pt", "1em"
_FONT_SIZE_PATTERN = re.compile(r"^\d{1,2}(pt|em)$")

# margin: integer or decimal + cm/mm/in/em/pt, e.g. "1in", "2.5cm", "20mm"
_MARGIN_PATTERN = re.compile(r"^\d{1,2}(\.\d+)?(cm|mm|in|em|pt)$")


def _validate_pdf_args(
    pdf_engine: str, font: str, font_size: str, margin: str
) -> str | None:
    """Return None if all args are safe, else an error message."""
    if pdf_engine not in _ALLOWED_PDF_ENGINES:
        allowed = ", ".join(sorted(_ALLOWED_PDF_ENGINES))
        return (
            f"Unsupported pdf_engine '{pdf_engine}'. "
            f"Allowed: {allowed}"
        )
    if not _FONT_PATTERN.match(font):
        return (
            f"Invalid font '{font}': must match "
            f"[A-Za-z0-9][A-Za-z0-9 \\-_.]{{0,63}} (no LaTeX or shell metachars)"
        )
    if not _FONT_SIZE_PATTERN.match(font_size):
        return (
            f"Invalid font_size '{font_size}': must match \\d{{1,2}}(pt|em)"
        )
    if not _MARGIN_PATTERN.match(margin):
        return (
            f"Invalid margin '{margin}': must match \\d{{1,2}}(\\.\\d+)?(cm|mm|in|em|pt)"
        )
    return None


def check_pandoc() -> dict[str, Any]:
    """Check if Pandoc is installed and return version info."""
    try:
        result = subprocess.run(
            ["pandoc", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        version = result.stdout.splitlines()[0] if result.stdout else "unknown"
        return {"installed": True, "version": version}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"installed": False, "version": None}


def check_calibre() -> dict[str, Any]:
    """Check if Calibre's ebook-convert is installed."""
    try:
        result = subprocess.run(
            ["ebook-convert", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        version = result.stdout.strip() if result.stdout else "unknown"
        return {"installed": True, "version": version}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"installed": False, "version": None}


def generate_epub(
    manuscript_path: Path,
    output_path: Path,
    title: str,
    author: str,
    language: str = "en",
    cover_image: Path | None = None,
    css_path: Path | None = None,
) -> dict[str, Any]:
    """Generate EPUB from a Markdown manuscript."""
    cmd = [
        "pandoc", str(manuscript_path),
        "-o", str(output_path),
        "--metadata", f"title={title}",
        "--metadata", f"author={author}",
        "--metadata", f"lang={language}",
        "--toc", "--toc-depth=1",
        "--epub-chapter-level=1",
    ]

    if cover_image and cover_image.exists():
        cmd.extend(["--epub-cover-image", str(cover_image)])

    if css_path and css_path.exists():
        cmd.extend(["--css", str(css_path)])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        return {"success": False, "error": result.stderr}

    size = output_path.stat().st_size if output_path.exists() else 0
    return {
        "success": True,
        "path": str(output_path),
        "size_bytes": size,
        "size_human": _human_size(size),
    }


def generate_pdf(
    manuscript_path: Path,
    output_path: Path,
    title: str,
    author: str,
    pdf_engine: str = "xelatex",
    font: str = "Linux Libertine O",
    font_size: str = "11pt",
    margin: str = "1in",
) -> dict[str, Any]:
    """Generate PDF from a Markdown manuscript."""
    error = _validate_pdf_args(pdf_engine, font, font_size, margin)
    if error is not None:
        return {"success": False, "error": error}

    cmd = [
        "pandoc", str(manuscript_path),
        "-o", str(output_path),
        f"--pdf-engine={pdf_engine}",
        "--metadata", f"title={title}",
        "--metadata", f"author={author}",
        "--toc",
        "-V", f"geometry:margin={margin}",
        "-V", f"fontsize={font_size}",
        "-V", f"mainfont={font}",
        "-V", "documentclass=book",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        return {"success": False, "error": result.stderr}

    size = output_path.stat().st_size if output_path.exists() else 0
    return {
        "success": True,
        "path": str(output_path),
        "size_bytes": size,
        "size_human": _human_size(size),
    }


def generate_mobi(
    epub_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Convert EPUB to MOBI using Calibre's ebook-convert."""
    if not epub_path.exists():
        return {"success": False, "error": f"EPUB not found: {epub_path}"}

    cmd = ["ebook-convert", str(epub_path), str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        return {"success": False, "error": result.stderr}

    size = output_path.stat().st_size if output_path.exists() else 0
    return {
        "success": True,
        "path": str(output_path),
        "size_bytes": size,
        "size_human": _human_size(size),
    }


def assemble_manuscript(
    project_dir: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Assemble all chapters into a single manuscript file."""
    parts = []

    # Front matter
    front = project_dir / "export" / "front-matter.md"
    if front.exists():
        text = front.read_text(encoding="utf-8")
        # Remove frontmatter from front-matter file
        import re
        text = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
        parts.append(text)
        parts.append("\n\\newpage\n")

    # Chapters in order
    chapters_dir = project_dir / "chapters"
    if chapters_dir.exists():
        for ch_dir in sorted(chapters_dir.iterdir()):
            draft = ch_dir / "draft.md"
            if draft.exists():
                content = draft.read_text(encoding="utf-8")
                # Remove any frontmatter from draft
                import re
                content = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)
                parts.append(content)
                parts.append("\n\\newpage\n")

    # Back matter
    back = project_dir / "export" / "back-matter.md"
    if back.exists():
        parts.append(back.read_text(encoding="utf-8"))

    manuscript = "\n\n".join(parts)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(manuscript, encoding="utf-8")

    word_count = len(manuscript.split())
    return {
        "path": str(output_path),
        "word_count": word_count,
        "chapters_included": len([
            d for d in (chapters_dir.iterdir() if chapters_dir.exists() else [])
            if d.is_dir() and (d / "draft.md").exists()
        ]),
    }


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
