"""Unit tests for ``prev_chapter_draft`` in ``loaders.recent_chapters``.

Exercises the truncation logic directly — paragraph-break guard, word-boundary
fallback, near-end-break edge case, and short-body pass-through.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.state.loaders.recent_chapters import prev_chapter_draft


class TestPrevChapterDraftLoader:
    def test_short_body_returned_verbatim(self, tmp_path: Path):
        """Bodies shorter than max_chars are returned without modification."""
        draft = tmp_path / "draft.md"
        draft.write_text("Short content here.", encoding="utf-8")
        result = prev_chapter_draft(draft, max_chars=3500)
        assert result == "Short content here."
        assert not result.startswith("... ")

    def test_empty_file_returns_empty_string(self, tmp_path: Path):
        """Missing or empty draft returns empty string."""
        missing = tmp_path / "no-such-file.md"
        assert prev_chapter_draft(missing) == ""

        empty = tmp_path / "empty.md"
        empty.write_text("", encoding="utf-8")
        assert prev_chapter_draft(empty) == ""

    def test_frontmatter_stripped_before_measuring(self, tmp_path: Path):
        """YAML frontmatter does not count toward max_chars budget."""
        body = "word " * 100  # 500 chars, well under 3500
        draft = tmp_path / "draft.md"
        draft.write_text(f"---\ntitle: Ch\nstatus: Draft\n---\n\n{body}", encoding="utf-8")
        result = prev_chapter_draft(draft, max_chars=3500)
        assert result == body.strip()
        assert "---" not in result

    def test_paragraph_break_in_first_half_used(self, tmp_path: Path):
        """A paragraph break in the first half of the tail produces a clean start."""
        # Body (no heading) — tail of max_chars=100:
        # last 100 chars = "AA...A" (20) + "\n\n" (2) + "BB...B" (78)
        # break_pos = 20 which is < 50 (100//2) → paragraph break is used
        body = ("X" * 200) + ("A" * 20) + "\n\n" + ("B" * 78)
        draft = tmp_path / "draft.md"
        draft.write_text(body, encoding="utf-8")

        result = prev_chapter_draft(draft, max_chars=100)
        assert result.startswith("... ")
        assert result[4:].startswith("B")

    def test_paragraph_break_near_end_not_used(self, tmp_path: Path):
        """A paragraph break in the second half of the tail falls back to word boundary."""
        # Build a body where \n\n is at position 90 in a 100-char tail (> 50 = 100//2)
        body = ("X" * 200) + ("A" * 89) + "\n\n" + ("B" * 10)
        draft = tmp_path / "draft.md"
        draft.write_text(f"# Ch\n\n{body}", encoding="utf-8")

        result = prev_chapter_draft(draft, max_chars=101)
        # break_pos ~89 which is >= 101//2=50 → not used
        # Falls back to word boundary — but there are no spaces in "AAA...BB"
        # so it falls through to raw cut
        assert result.startswith("... ")

    def test_word_boundary_fallback_when_no_paragraph_break(self, tmp_path: Path):
        """When no qualifying paragraph break, first space is used as boundary."""
        # Tail has no \n\n but has spaces: "long sentence with words"
        prefix = "X" * 200
        tail_content = "long sentence with words at the end"
        body = prefix + tail_content
        draft = tmp_path / "draft.md"
        draft.write_text(f"# Ch\n\n{body}", encoding="utf-8")

        result = prev_chapter_draft(draft, max_chars=len(tail_content) + 5)
        assert result.startswith("... ")
        # Should start after the first space in the tail
        assert not result[4:].startswith(" ")

    def test_no_space_no_break_raw_cut(self, tmp_path: Path):
        """When neither paragraph break nor space exists, raw char cut is used."""
        # A single long word with no spaces or newlines
        body = "A" * 500
        draft = tmp_path / "draft.md"
        draft.write_text(f"# Ch\n\n{body}", encoding="utf-8")

        result = prev_chapter_draft(draft, max_chars=100)
        assert result.startswith("... ")
        assert len(result) <= 104  # "... " (4) + 100 chars max

    def test_exact_max_chars_not_truncated(self, tmp_path: Path):
        """Body of exactly max_chars is returned verbatim (no truncation path)."""
        # No heading — body length must be exactly max_chars to avoid truncation
        body = "word " * 700  # 3500 chars
        draft = tmp_path / "draft.md"
        draft.write_text(body, encoding="utf-8")

        result = prev_chapter_draft(draft, max_chars=3500)
        assert not result.startswith("... ")
        assert len(result) <= 3500
