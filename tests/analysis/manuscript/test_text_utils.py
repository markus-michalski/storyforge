"""Unit tests for tools.analysis.manuscript.text_utils."""

from __future__ import annotations

from pathlib import Path

from tools.analysis.manuscript.text_utils import (
    _make_snippet,
    _ngrams_in_line,
    _read_chapter_drafts,
    _strip_dialogue,
    _strip_markdown,
    _tokenise,
)


class TestStripMarkdown:
    def test_removes_frontmatter(self) -> None:
        out = _strip_markdown("---\ntitle: Foo\n---\n\nProse here.\n")
        assert "title" not in out
        assert "Prose here" in out

    def test_removes_headings(self) -> None:
        out = _strip_markdown("# Heading\n\nProse.\n")
        assert "Heading" not in out
        assert "Prose" in out

    def test_strips_emphasis_chars(self) -> None:
        out = _strip_markdown("Some *italic* and **bold** words.")
        assert "*" not in out
        assert "italic" in out and "bold" in out


class TestTokenise:
    def test_lowercases(self) -> None:
        assert _tokenise("Hello World") == ["hello", "world"]

    def test_preserves_apostrophes(self) -> None:
        assert _tokenise("don't say can't") == ["don't", "say", "can't"]

    def test_normalizes_curly_apostrophe(self) -> None:
        assert _tokenise("don’t") == ["don't"]


class TestStripDialogue:
    def test_removes_double_quotes(self) -> None:
        out = _strip_dialogue('She said "Hello there." and walked.')
        assert "Hello" not in out
        assert "walked" in out

    def test_keeps_unquoted_text(self) -> None:
        out = _strip_dialogue("She walked alone.")
        assert "walked" in out

    def test_handles_curly_quotes(self) -> None:
        out = _strip_dialogue("She said “Hello.” quietly.")
        assert "Hello" not in out


class TestMakeSnippet:
    def test_short_line_returns_full(self) -> None:
        line = "Short prose line."
        assert _make_snippet(line, "short") == line

    def test_long_line_truncates_around_match(self) -> None:
        line = "x" * 100 + "needle" + "y" * 100
        snippet = _make_snippet(line, "needle", max_len=50)
        assert "needle" in snippet
        assert len(snippet) <= 60  # max_len + ellipsis padding


class TestNgramsInLine:
    def test_skips_all_stopword_windows(self) -> None:
        # All stopwords → no n-grams emitted.
        out = _ngrams_in_line(["the", "and", "of", "a", "in"], (4,))
        assert out == []

    def test_emits_content_ngrams(self) -> None:
        tokens = ["the", "ghost", "of", "a", "memory"]
        out = _ngrams_in_line(tokens, (4,))
        assert any(p[2] == "the ghost of a" for p in out)

    def test_skips_short_lines(self) -> None:
        assert _ngrams_in_line(["hello", "world"], (4,)) == []


class TestReadChapterDrafts:
    def test_reads_drafts_in_order(self, tmp_path: Path) -> None:
        chapters = tmp_path / "chapters"
        for slug in ("02-second", "01-first", "03-third"):
            (chapters / slug).mkdir(parents=True)
            (chapters / slug / "draft.md").write_text(f"draft of {slug}", encoding="utf-8")
        drafts = _read_chapter_drafts(tmp_path)
        assert [slug for slug, _ in drafts] == ["01-first", "02-second", "03-third"]

    def test_skips_chapters_without_draft(self, tmp_path: Path) -> None:
        (tmp_path / "chapters" / "01-no-draft").mkdir(parents=True)
        ch = tmp_path / "chapters" / "02-with-draft"
        ch.mkdir()
        (ch / "draft.md").write_text("hi", encoding="utf-8")
        drafts = _read_chapter_drafts(tmp_path)
        assert [slug for slug, _ in drafts] == ["02-with-draft"]

    def test_no_chapters_dir_returns_empty(self, tmp_path: Path) -> None:
        assert _read_chapter_drafts(tmp_path) == []
