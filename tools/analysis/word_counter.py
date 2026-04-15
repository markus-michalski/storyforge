"""Word counting and reading time estimation for StoryForge."""

from __future__ import annotations

import re
from pathlib import Path


def count_words(text: str) -> int:
    """Count words in text, excluding markdown formatting."""
    # Remove frontmatter
    text = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
    # Remove markdown headers
    text = re.sub(r"^#+\s+.*$", "", text, flags=re.MULTILINE)
    # Remove markdown formatting
    text = re.sub(r"[*_`~\[\]()]", "", text)
    return len(text.split())


def estimate_reading_time(word_count: int, wpm: int = 250) -> str:
    """Estimate reading time at given words-per-minute."""
    minutes = word_count / wpm
    if minutes < 1:
        return "< 1 min"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins} min"


def count_chapter_words(chapter_dir: Path) -> int:
    """Count words in a chapter's draft.md."""
    draft = chapter_dir / "draft.md"
    if not draft.exists():
        return 0
    return count_words(draft.read_text(encoding="utf-8"))


def count_book_words(project_dir: Path) -> dict[str, int]:
    """Count words per chapter and total for a book project."""
    chapters_dir = project_dir / "chapters"
    if not chapters_dir.exists():
        return {"total": 0, "chapters": {}}

    chapters = {}
    total = 0
    for ch_dir in sorted(chapters_dir.iterdir()):
        if ch_dir.is_dir():
            words = count_chapter_words(ch_dir)
            chapters[ch_dir.name] = words
            total += words

    return {"total": total, "chapters": chapters}


def analyze_sentence_lengths(text: str) -> dict:
    """Analyze sentence length distribution — key AI detection metric."""
    # Remove frontmatter and headers
    text = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
    text = re.sub(r"^#+\s+.*$", "", text, flags=re.MULTILINE)

    # Split into sentences (rough but functional)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s for s in sentences if len(s.split()) > 0]

    if not sentences:
        return {"count": 0, "mean": 0, "std_dev": 0, "min": 0, "max": 0, "variance_rating": "N/A"}

    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(lengths)
    variance = sum((n - mean) ** 2 for n in lengths) / len(lengths)
    std_dev = variance ** 0.5

    # Human writing typically has std_dev > 8
    # AI writing typically has std_dev < 5
    if std_dev > 8:
        rating = "Human-like (high variance)"
    elif std_dev > 5:
        rating = "Borderline"
    else:
        rating = "AI-like (low variance)"

    return {
        "count": len(lengths),
        "mean": round(mean, 1),
        "std_dev": round(std_dev, 1),
        "min": min(lengths),
        "max": max(lengths),
        "variance_rating": rating,
    }
