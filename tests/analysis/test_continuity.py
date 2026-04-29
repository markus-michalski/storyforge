"""Tests for tools.analysis.continuity — Issue #124."""

from __future__ import annotations

from pathlib import Path

from tools.analysis.continuity import (
    check_character_consistency,
    check_timeline,
    extract_character_mentions,
)


# ---------------------------------------------------------------------------
# extract_character_mentions — pure function
# ---------------------------------------------------------------------------


class TestExtractCharacterMentions:
    def test_finds_mention(self):
        result = extract_character_mentions("Marcus walked in.", ["Marcus", "Lena"])
        assert "Marcus" in result
        assert result["Marcus"] == [1]

    def test_case_insensitive(self):
        result = extract_character_mentions("MARCUS said hello.", ["Marcus"])
        assert "Marcus" in result

    def test_multiple_lines(self):
        text = "Marcus spoke.\nLena replied.\nMarcus left."
        result = extract_character_mentions(text, ["Marcus", "Lena"])
        assert result["Marcus"] == [1, 3]
        assert result["Lena"] == [2]

    def test_missing_character_excluded(self):
        result = extract_character_mentions("Nobody here.", ["Marcus"])
        assert "Marcus" not in result

    def test_empty_text(self):
        result = extract_character_mentions("", ["Marcus"])
        assert result == {}

    def test_empty_names(self):
        result = extract_character_mentions("Marcus walked.", [])
        assert result == {}


# ---------------------------------------------------------------------------
# check_character_consistency
# ---------------------------------------------------------------------------


def _make_book(tmp_path: Path) -> Path:
    book = tmp_path / "my-book"
    (book / "characters").mkdir(parents=True)
    (book / "chapters").mkdir()
    return book


class TestCheckCharacterConsistency:
    def test_unused_character_flagged(self, tmp_path):
        book = _make_book(tmp_path)
        (book / "characters" / "marcus.md").write_text(
            '---\nname: "Marcus"\n---\n', encoding="utf-8"
        )
        ch = book / "chapters" / "01-intro"
        ch.mkdir()
        (ch / "draft.md").write_text("Nobody important here.", encoding="utf-8")

        issues = check_character_consistency(book)
        assert any(i["type"] == "unused_character" for i in issues)
        assert any("Marcus" in i["message"] for i in issues)

    def test_mentioned_character_not_flagged(self, tmp_path):
        book = _make_book(tmp_path)
        (book / "characters" / "marcus.md").write_text(
            '---\nname: "Marcus"\n---\n', encoding="utf-8"
        )
        ch = book / "chapters" / "01-intro"
        ch.mkdir()
        (ch / "draft.md").write_text("Marcus walked in.", encoding="utf-8")

        issues = check_character_consistency(book)
        assert not any(i["type"] == "unused_character" for i in issues)

    def test_no_chapters_dir_returns_empty(self, tmp_path):
        book = tmp_path / "my-book"
        (book / "characters").mkdir(parents=True)
        (book / "characters" / "marcus.md").write_text(
            '---\nname: "Marcus"\n---\n', encoding="utf-8"
        )
        # No chapters dir

        issues = check_character_consistency(book)
        assert issues == []

    def test_no_characters_dir_returns_empty(self, tmp_path):
        book = tmp_path / "my-book"
        (book / "chapters").mkdir(parents=True)

        issues = check_character_consistency(book)
        assert issues == []

    def test_index_md_skipped(self, tmp_path):
        book = _make_book(tmp_path)
        (book / "characters" / "INDEX.md").write_text("# Characters\n", encoding="utf-8")

        issues = check_character_consistency(book)
        assert issues == []

    def test_character_without_name_field_uses_stem(self, tmp_path):
        book = _make_book(tmp_path)
        (book / "characters" / "lena.md").write_text("# Lena\n", encoding="utf-8")
        ch = book / "chapters" / "01-intro"
        ch.mkdir()
        (ch / "draft.md").write_text("lena was there.", encoding="utf-8")

        issues = check_character_consistency(book)
        assert not any("lena" in i.get("message", "") for i in issues)

    def test_chapter_without_draft_skipped(self, tmp_path):
        book = _make_book(tmp_path)
        (book / "characters" / "marcus.md").write_text(
            '---\nname: "Marcus"\n---\n', encoding="utf-8"
        )
        ch = book / "chapters" / "01-intro"
        ch.mkdir()
        # No draft.md

        issues = check_character_consistency(book)
        assert any(i["type"] == "unused_character" for i in issues)

    def test_severity_is_warning(self, tmp_path):
        book = _make_book(tmp_path)
        (book / "characters" / "ghost.md").write_text(
            '---\nname: "Ghost"\n---\n', encoding="utf-8"
        )
        ch = book / "chapters" / "01-intro"
        ch.mkdir()
        (ch / "draft.md").write_text("Nobody.", encoding="utf-8")

        issues = check_character_consistency(book)
        assert all(i["severity"] == "warning" for i in issues)


# ---------------------------------------------------------------------------
# check_timeline
# ---------------------------------------------------------------------------


class TestCheckTimeline:
    def test_missing_timeline_returns_info(self, tmp_path):
        book = tmp_path / "my-book"
        book.mkdir()

        issues = check_timeline(book)
        assert len(issues) == 1
        assert issues[0]["type"] == "missing_timeline"
        assert issues[0]["severity"] == "info"

    def test_present_timeline_returns_no_issues(self, tmp_path):
        book = tmp_path / "my-book"
        (book / "plot").mkdir(parents=True)
        (book / "plot" / "timeline.md").write_text("# Timeline\n", encoding="utf-8")

        issues = check_timeline(book)
        assert issues == []
