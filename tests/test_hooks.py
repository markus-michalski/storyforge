"""Tests for StoryForge PostToolUse hooks."""

from hooks.validate_chapter import validate_chapter
from hooks.validate_character import validate_character


class TestValidateChapter:
    def test_ignores_non_chapter_files(self):
        assert validate_chapter("/some/other/file.md") == []

    def test_ignores_readme(self):
        assert validate_chapter("/project/chapters/01-intro/README.md") == []

    def test_detects_ai_tells(self, tmp_path):
        ch_dir = tmp_path / "project" / "chapters" / "01-intro"
        ch_dir.mkdir(parents=True)
        draft = ch_dir / "draft.md"
        draft.write_text(
            "# Chapter 1\n\n"
            "She delved into the tapestry of nuanced experiences, "
            "each thread a vibrant testament to the intricate myriad "
            "of unprecedented journeys she had embarked upon. "
            "The beacon of hope resonated with a pivotal force. " * 3,
            encoding="utf-8",
        )

        issues = validate_chapter(str(draft))
        # Should find multiple AI-tell words
        ai_warns = [i for i in issues if "AI-tell" in i]
        assert len(ai_warns) > 3

    def test_clean_prose_passes(self, tmp_path):
        ch_dir = tmp_path / "project" / "chapters" / "01-intro"
        ch_dir.mkdir(parents=True)
        draft = ch_dir / "draft.md"
        draft.write_text(
            "# Chapter 1\n\n"
            "The door slammed. She froze, one hand on the railing, "
            "the other clutching a paper bag from the Korean grocery "
            "on Seventh. The stairs smelled like wet concrete and old "
            "cigarettes. Three flights up, apartment 4B, the deadbolt "
            "she'd been meaning to replace since February. "
            "Her keys jangled. Too loud in the silence. "
            "Something was wrong. She could feel it — that prickle "
            "at the back of her neck, the one her mother called "
            "'the animal knowing.' Twenty-eight years of ignoring it. "
            "Tonight she listened." * 3,
            encoding="utf-8",
        )

        issues = validate_chapter(str(draft))
        ai_warns = [i for i in issues if "AI-tell" in i]
        assert len(ai_warns) == 0

    def test_skips_short_drafts(self, tmp_path):
        ch_dir = tmp_path / "project" / "chapters" / "01-intro"
        ch_dir.mkdir(parents=True)
        draft = ch_dir / "draft.md"
        draft.write_text("# Chapter 1\n\n", encoding="utf-8")

        issues = validate_chapter(str(draft))
        assert len(issues) == 0


class TestValidateCharacter:
    def test_ignores_non_character_files(self):
        assert validate_character("/some/other/file.md") == []

    def test_ignores_index(self):
        assert validate_character("/project/characters/INDEX.md") == []

    def test_valid_character(self, tmp_path):
        chars_dir = tmp_path / "project" / "characters"
        chars_dir.mkdir(parents=True)
        char_file = chars_dir / "alex.md"
        char_file.write_text(
            '---\nname: "Alex"\nrole: "protagonist"\nstatus: "Concept"\n---\n\n'
            "# Alex\n\n## Want vs. Need\n\nContent.\n\n## Fatal Flaw\n\nContent.\n",
            encoding="utf-8",
        )

        issues = validate_character(str(char_file))
        assert len(issues) == 0

    def test_missing_frontmatter(self, tmp_path):
        chars_dir = tmp_path / "project" / "characters"
        chars_dir.mkdir(parents=True)
        char_file = chars_dir / "alex.md"
        char_file.write_text("# Alex\n\nNo frontmatter here.\n", encoding="utf-8")

        issues = validate_character(str(char_file))
        assert any("Missing YAML frontmatter" in i for i in issues)

    def test_missing_required_sections(self, tmp_path):
        chars_dir = tmp_path / "project" / "characters"
        chars_dir.mkdir(parents=True)
        char_file = chars_dir / "alex.md"
        char_file.write_text(
            '---\nname: "Alex"\nrole: "protagonist"\nstatus: "Concept"\n---\n\n'
            "# Alex\n\nNo required sections.\n",
            encoding="utf-8",
        )

        issues = validate_character(str(char_file))
        assert any("Want vs. Need" in i for i in issues)
        assert any("Fatal Flaw" in i for i in issues)

    def test_minor_characters_skip_sections(self, tmp_path):
        chars_dir = tmp_path / "project" / "characters"
        chars_dir.mkdir(parents=True)
        char_file = chars_dir / "barista.md"
        char_file.write_text(
            '---\nname: "Barista"\nrole: "minor"\nstatus: "Concept"\n---\n\n'
            "# Barista\n\nJust a minor character.\n",
            encoding="utf-8",
        )

        issues = validate_character(str(char_file))
        # Minor characters don't need Want vs. Need or Fatal Flaw
        assert not any("Want vs. Need" in i for i in issues)
