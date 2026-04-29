"""Text normalization, tokenization, n-gram extraction, draft reading.

Pure stdlib helpers shared across all scanner modules. No book-state I/O
beyond reading chapter draft files.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from tools.analysis.manuscript.vocabularies import STOP_WORDS


_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^\s*#{1,6}\s.*$", re.MULTILINE)
_HORIZONTAL_RULE_RE = re.compile(r"^\s*[*_-]{3,}\s*$", re.MULTILINE)
_MD_FORMAT_RE = re.compile(r"[*_`~]")
# Punctuation to drop for the n-gram identity. We keep apostrophes inside
# words ("don't") so they aren't split, and we keep "—" as a soft separator.
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'’]*")

# Matches text inside straight or curly double-quoted spans. Non-greedy;
# must have at least 2 chars of content.
_DIALOGUE_RE = re.compile(r'(?:"([^"\n]{2,}?)"|“([^“”\n]{2,}?)”)')


def _strip_markdown(text: str) -> str:
    text = _FRONTMATTER_RE.sub("", text)
    text = _HEADING_RE.sub("", text)
    text = _HORIZONTAL_RULE_RE.sub("", text)
    text = _MD_FORMAT_RE.sub("", text)
    return text


def _tokenise(line: str) -> list[str]:
    """Lowercase tokens, apostrophes preserved inside words."""
    return [m.group(0).lower().replace("’", "'") for m in _TOKEN_RE.finditer(line)]


def _strip_dialogue(line: str) -> str:
    """Remove dialogue (quoted text) from a line, leaving narration only.

    Used by filter-word and adverb-density scans so we only count narrator
    tics, not character speech.
    """
    return _DIALOGUE_RE.sub(" ", line)


def _make_snippet(line: str, ngram_text: str, max_len: int = 140) -> str:
    """Return a trimmed snippet around the n-gram match in the original line."""
    line = line.strip()
    if len(line) <= max_len:
        return line
    idx = line.lower().find(ngram_text)
    if idx < 0:
        return line[:max_len].rstrip() + "…"
    half = max_len // 2
    start = max(0, idx - half)
    end = min(len(line), idx + len(ngram_text) + half)
    snippet = line[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(line):
        snippet = snippet + "…"
    return snippet


def _ngrams_in_line(tokens: list[str], sizes: Iterable[int]) -> list[tuple[int, int, str]]:
    """Yield (size, start_index, joined_phrase) for every n-gram in the line.

    Skips n-grams that are 100% stop-words — they're noise like "of the and a".
    """
    out: list[tuple[int, int, str]] = []
    for size in sizes:
        if len(tokens) < size:
            continue
        for i in range(len(tokens) - size + 1):
            window = tokens[i : i + size]
            if all(t in STOP_WORDS for t in window):
                continue
            out.append((size, i, " ".join(window)))
    return out


def _read_chapter_drafts(book_path: Path) -> list[tuple[str, str]]:
    """Return [(chapter_slug, draft_text), ...] sorted by chapter folder name."""
    chapters_dir = book_path / "chapters"
    if not chapters_dir.is_dir():
        return []
    drafts: list[tuple[str, str]] = []
    for chapter_dir in sorted(chapters_dir.iterdir()):
        if not chapter_dir.is_dir():
            continue
        draft_path = chapter_dir / "draft.md"
        if not draft_path.exists():
            continue
        try:
            text = draft_path.read_text(encoding="utf-8")
        except OSError:
            continue
        drafts.append((chapter_dir.name, text))
    return drafts


# Compatibility re-export for the dialogue regex (used by scanners.py).
DIALOGUE_RE = _DIALOGUE_RE


__all__ = [
    "DIALOGUE_RE",
    "_make_snippet",
    "_ngrams_in_line",
    "_read_chapter_drafts",
    "_strip_dialogue",
    "_strip_markdown",
    "_tokenise",
]
