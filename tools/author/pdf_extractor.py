"""PDF text extraction for author style analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF file using PyMuPDF (fitz).

    Returns the full text content with page breaks preserved.
    """
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


def extract_text_from_file(file_path: Path) -> str:
    """Extract text from PDF, TXT, or MD files."""
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    elif suffix in (".txt", ".md", ".markdown"):
        return file_path.read_text(encoding="utf-8")
    elif suffix == ".epub":
        return _extract_from_epub(file_path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")


def _extract_from_epub(epub_path: Path) -> str:
    """Extract text from an EPUB file."""
    import zipfile
    import re

    text_parts = []

    with zipfile.ZipFile(str(epub_path), 'r') as zf:
        for name in zf.namelist():
            if name.endswith(('.xhtml', '.html', '.htm')):
                content = zf.read(name).decode('utf-8', errors='ignore')
                # Strip HTML tags (rough but functional)
                clean = re.sub(r'<[^>]+>', ' ', content)
                clean = re.sub(r'\s+', ' ', clean).strip()
                if len(clean) > 100:  # Skip short files (TOC, metadata)
                    text_parts.append(clean)

    return "\n\n---\n\n".join(text_parts)


def get_text_stats(text: str) -> dict[str, Any]:
    """Get basic statistics about extracted text."""
    words = text.split()
    paragraphs = [p for p in text.split("\n\n") if p.strip()]

    return {
        "word_count": len(words),
        "paragraph_count": len(paragraphs),
        "character_count": len(text),
        "estimated_pages": len(words) // 250,  # ~250 words per page
    }
