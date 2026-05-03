"""Tests for StoryForge frontmatter parsers."""

from pathlib import Path

from tools.state.parsers import (
    parse_author_profile,
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


class TestParseAuthorProfile:
    """Issue #151 — parse_author_profile must extract the body's Writing
    Discoveries section so chapter-writer / chapter-reviewer can load author
    tics, style principles, and don'ts that emerged across books."""

    def _write_profile(self, tmp_path: Path, body: str, frontmatter_extras: str = "") -> Path:
        author_dir = tmp_path / "ethan-cole"
        author_dir.mkdir()
        profile = author_dir / "profile.md"
        fm = (
            '---\nname: "Ethan Cole"\nslug: "ethan-cole"\n'
            'primary_genres: ["dark-fantasy"]\nnarrative_voice: "third-limited"\n'
            'tense: "past"\ntone: ["brooding"]\n'
            f"{frontmatter_extras}---\n\n"
        )
        profile.write_text(fm + body, encoding="utf-8")
        return profile

    def test_legacy_profile_without_discoveries_returns_empty_lists(self, tmp_path):
        """Books written before #151 must keep working — empty discoveries OK."""
        profile = self._write_profile(tmp_path, "# Ethan Cole\n\n## Writing Style\n\nDark and lean.\n")

        result = parse_author_profile(profile)

        assert result["slug"] == "ethan-cole"
        assert result["name"] == "Ethan Cole"
        assert result["writing_discoveries"] == {
            "recurring_tics": [],
            "style_principles": [],
            "donts": [],
        }

    def test_parses_recurring_tics_with_origin(self, tmp_path):
        body = (
            "# Ethan Cole\n\n## Writing Discoveries\n\n"
            "_Insights that emerged across books._\n\n"
            "### Recurring Tics\n\n"
            "- **\"math\" as analytical metaphor** — cut on sight unless POV demands. "
            "_(emerged from firelight, 2026-05)_\n"
            "- **Blocking pattern \"[Character] moved to [location]\"** — replace with sensory anchor. "
            "_(emerged from firelight, 2026-05)_\n"
        )
        profile = self._write_profile(tmp_path, body)

        result = parse_author_profile(profile)

        tics = result["writing_discoveries"]["recurring_tics"]
        assert len(tics) == 2
        assert "math" in tics[0]["text"]
        assert tics[0]["origins"] == [{"book": "firelight", "date": "2026-05"}]
        assert "Blocking pattern" in tics[1]["text"]

    def test_parses_style_principles_and_donts(self, tmp_path):
        body = (
            "# Ethan Cole\n\n## Writing Discoveries\n\n"
            "### Style Principles\n\n"
            "- Fast dialog without tags works up to ~8 turns. _(emerged from firelight, 2026-05)_\n\n"
            "### Don'ts (beyond banned phrases)\n\n"
            "- Never start a chapter with weather. _(emerged from firelight, 2026-05)_\n"
        )
        profile = self._write_profile(tmp_path, body)

        result = parse_author_profile(profile)
        disc = result["writing_discoveries"]

        assert len(disc["style_principles"]) == 1
        assert "Fast dialog" in disc["style_principles"][0]["text"]
        assert len(disc["donts"]) == 1
        assert "weather" in disc["donts"][0]["text"]

    def test_multiple_origins_for_recurring_pattern(self, tmp_path):
        """When a pattern resurfaces in a second book, both origin tags survive."""
        body = (
            "# Ethan Cole\n\n## Writing Discoveries\n\n"
            "### Recurring Tics\n\n"
            "- **\"math\" as analytical metaphor** — cut on sight. "
            "_(emerged from firelight, 2026-05)_ _(emerged from emberkeep, 2026-09)_\n"
        )
        profile = self._write_profile(tmp_path, body)

        tic = parse_author_profile(profile)["writing_discoveries"]["recurring_tics"][0]
        assert tic["origins"] == [
            {"book": "firelight", "date": "2026-05"},
            {"book": "emberkeep", "date": "2026-09"},
        ]

    def test_entry_without_origin_tag_still_parses(self, tmp_path):
        """User-edited entries may lack an origin tag — must not crash."""
        body = (
            "# Ethan Cole\n\n## Writing Discoveries\n\n"
            "### Recurring Tics\n\n"
            "- **\"just\" as a hedge** — strike when not load-bearing.\n"
        )
        profile = self._write_profile(tmp_path, body)

        tic = parse_author_profile(profile)["writing_discoveries"]["recurring_tics"][0]
        assert "just" in tic["text"]
        assert tic["origins"] == []

    def test_empty_subsections_are_tolerated(self, tmp_path):
        """A bare `_Frei._` placeholder under a heading must not register as a finding."""
        body = (
            "# Ethan Cole\n\n## Writing Discoveries\n\n"
            "### Recurring Tics\n\n"
            "- **\"math\"** — analytical tic. _(emerged from firelight, 2026-05)_\n\n"
            "### Style Principles\n\n"
            "_Frei._\n\n"
            "### Don'ts (beyond banned phrases)\n\n"
            "_Frei._\n"
        )
        profile = self._write_profile(tmp_path, body)

        disc = parse_author_profile(profile)["writing_discoveries"]
        assert len(disc["recurring_tics"]) == 1
        assert disc["style_principles"] == []
        assert disc["donts"] == []


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
