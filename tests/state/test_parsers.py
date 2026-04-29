"""Tests for StoryForge frontmatter parsers."""

from tools.state.parsers import (
    parse_frontmatter,
    parse_book_readme,
    parse_chapter_readme,
    parse_character_file,
    count_words_in_file,
    _normalize_book_status,
    _normalize_chapter_status,
    _normalize_character_status,
)


class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        text = "---\ntitle: Test\nstatus: Draft\n---\n\nBody text here."
        meta, body = parse_frontmatter(text)
        assert meta["title"] == "Test"
        assert meta["status"] == "Draft"
        assert body.strip() == "Body text here."

    def test_no_frontmatter(self):
        text = "Just some text without frontmatter."
        meta, body = parse_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_empty_frontmatter(self):
        text = "---\n\n---\n\nBody."
        meta, body = parse_frontmatter(text)
        assert meta == {}
        assert body.strip() == "Body."

    def test_invalid_yaml(self):
        text = "---\n: invalid: yaml: [[\n---\n\nBody."
        meta, body = parse_frontmatter(text)
        assert meta == {}

    def test_frontmatter_with_lists(self):
        text = "---\ngenres:\n  - horror\n  - fantasy\ntone:\n  - sarcastic\n---\n\nBody."
        meta, body = parse_frontmatter(text)
        assert meta["genres"] == ["horror", "fantasy"]
        assert meta["tone"] == ["sarcastic"]


class TestStatusNormalization:
    def test_book_status_normalization(self):
        assert _normalize_book_status("idea") == "Idea"
        assert _normalize_book_status("CONCEPT") == "Concept"
        assert _normalize_book_status("plot outlined") == "Plot Outlined"
        assert _normalize_book_status("") == "Idea"
        assert _normalize_book_status("Custom Status") == "Custom Status"

    def test_chapter_status_normalization(self):
        assert _normalize_chapter_status("outline") == "Outline"
        assert _normalize_chapter_status("DRAFT") == "Draft"
        assert _normalize_chapter_status("final") == "Final"
        assert _normalize_chapter_status("") == "Outline"

    def test_character_status_normalization(self):
        assert _normalize_character_status("concept") == "Concept"
        assert _normalize_character_status("arc defined") == "Arc Defined"
        assert _normalize_character_status("") == "Concept"


class TestParseBookReadme:
    def test_parse_book(self, tmp_path):
        book_dir = tmp_path / "my-book"
        book_dir.mkdir()
        readme = book_dir / "README.md"
        readme.write_text(
            '---\ntitle: "My Book"\nauthor: "test-author"\n'
            'genres: ["horror", "fantasy"]\nbook_type: "novel"\n'
            'status: "Drafting"\nlanguage: "en"\n'
            "target_word_count: 80000\n---\n\n# My Book\n",
            encoding="utf-8",
        )

        result = parse_book_readme(readme)
        assert result["slug"] == "my-book"
        assert result["title"] == "My Book"
        assert result["author"] == "test-author"
        assert result["genres"] == ["horror", "fantasy"]
        assert result["status"] == "Drafting"
        assert result["target_word_count"] == 80000


class TestParseChapterReadme:
    def test_parse_chapter(self, tmp_path):
        ch_dir = tmp_path / "01-the-beginning"
        ch_dir.mkdir()
        readme = ch_dir / "README.md"
        readme.write_text(
            '---\ntitle: "The Beginning"\nnumber: 1\nstatus: "Draft"\npov_character: "Alex"\n---\n\n# Chapter 1\n',
            encoding="utf-8",
        )

        result = parse_chapter_readme(readme)
        assert result["slug"] == "01-the-beginning"
        assert result["title"] == "The Beginning"
        assert result["number"] == 1
        assert result["status"] == "Draft"
        assert result["pov_character"] == "Alex"


class TestParseCharacterFile:
    def test_parse_character(self, tmp_path):
        char_file = tmp_path / "alex.md"
        char_file.write_text(
            '---\nname: "Alex"\nrole: "protagonist"\nstatus: "Arc Defined"\nage: "28"\n---\n\n# Alex\n',
            encoding="utf-8",
        )

        result = parse_character_file(char_file)
        assert result["slug"] == "alex"
        assert result["name"] == "Alex"
        assert result["role"] == "protagonist"
        assert result["status"] == "Arc Defined"


class TestCountWords:
    def test_count_words(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text(
            "---\ntitle: Test\n---\n\nThis is a test with exactly eight words here.",
            encoding="utf-8",
        )
        assert count_words_in_file(f) == 9  # "This is a test with exactly eight words here."

    def test_count_words_no_file(self, tmp_path):
        f = tmp_path / "nonexistent.md"
        assert count_words_in_file(f) == 0
