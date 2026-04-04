"""Text extraction from various book formats for author style analysis."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Limits
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_WORDS = 200_000
SAMPLE_WORDS = 30_000  # Per section when sampling large texts

SUPPORTED_FORMATS = {".pdf", ".epub", ".txt", ".md", ".markdown", ".docx"}


def extract_text_from_file(file_path: Path) -> str:
    """Extract text from PDF, EPUB, DOCX, TXT, or MD files.

    Supported formats: .pdf, .epub, .docx, .txt, .md
    Max file size: 50 MB
    Max extracted text: 200,000 words (sampled if larger)
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Check file size
    size = file_path.stat().st_size
    if size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File too large: {size / 1024 / 1024:.1f} MB "
            f"(max {MAX_FILE_SIZE_MB} MB)"
        )

    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported format: {suffix}. "
            f"Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    if suffix == ".pdf":
        text = _extract_from_pdf(file_path)
    elif suffix == ".epub":
        text = _extract_from_epub(file_path)
    elif suffix == ".docx":
        text = _extract_from_docx(file_path)
    else:
        text = file_path.read_text(encoding="utf-8")

    # Apply word limit — sample if too large
    words = text.split()
    if len(words) > MAX_WORDS:
        text = _sample_text(text, words)

    return text


def _extract_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF file using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError(
            "PyMuPDF is required for PDF extraction. "
            "Install with: pip install pymupdf"
        )

    doc = fitz.open(str(pdf_path))
    pages = []

    for page in doc:
        text = page.get_text("text")
        if text.strip():
            pages.append(text)

    doc.close()
    return "\n\n---\n\n".join(pages)


def _extract_from_epub(epub_path: Path) -> str:
    """Extract text from an EPUB file (ZIP archive with XHTML content)."""
    import zipfile

    text_parts = []

    with zipfile.ZipFile(str(epub_path), "r") as zf:
        for name in sorted(zf.namelist()):
            if name.endswith((".xhtml", ".html", ".htm")):
                content = zf.read(name).decode("utf-8", errors="ignore")
                clean = re.sub(r"<[^>]+>", " ", content)
                clean = re.sub(r"\s+", " ", clean).strip()
                if len(clean) > 100:  # Skip short files (TOC, metadata)
                    text_parts.append(clean)

    return "\n\n---\n\n".join(text_parts)


def _extract_from_docx(docx_path: Path) -> str:
    """Extract text from a DOCX file."""
    try:
        from docx import Document
    except ImportError:
        raise ImportError(
            "python-docx is required for DOCX extraction. "
            "Install with: pip install python-docx"
        )

    doc = Document(str(docx_path))
    paragraphs = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


def _sample_text(text: str, words: list[str]) -> str:
    """Sample text from beginning, middle, and end for large documents.

    Takes ~30,000 words from each third to get a representative style sample
    while staying within the 200,000 word limit.
    """
    total = len(words)
    third = total // 3

    # Beginning: first SAMPLE_WORDS words
    start_end = min(SAMPLE_WORDS, third)
    beginning = " ".join(words[:start_end])

    # Middle: SAMPLE_WORDS words from the center
    mid_start = (total // 2) - (SAMPLE_WORDS // 2)
    mid_end = mid_start + min(SAMPLE_WORDS, third)
    middle = " ".join(words[mid_start:mid_end])

    # End: last SAMPLE_WORDS words
    end_start = max(total - SAMPLE_WORDS, total - third)
    ending = " ".join(words[end_start:])

    sampled = (
        f"[--- BEGINNING (words 1-{start_end:,}) ---]\n\n"
        f"{beginning}\n\n"
        f"[--- MIDDLE (words {mid_start:,}-{mid_end:,}) ---]\n\n"
        f"{middle}\n\n"
        f"[--- END (words {end_start:,}-{total:,}) ---]\n\n"
        f"{ending}"
    )

    return sampled


def get_text_stats(text: str) -> dict[str, Any]:
    """Get statistics about extracted text."""
    words = text.split()
    paragraphs = [p for p in text.split("\n\n") if p.strip()]

    return {
        "word_count": len(words),
        "paragraph_count": len(paragraphs),
        "character_count": len(text),
        "estimated_pages": len(words) // 250,
        "sampled": "[--- BEGINNING" in text,
    }


def get_supported_formats() -> list[str]:
    """Return list of supported file extensions."""
    return sorted(SUPPORTED_FORMATS)
