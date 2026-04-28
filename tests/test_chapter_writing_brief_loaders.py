"""Per-loader tests for the chapter_writing_brief decomposition (Issue #121).

Each loader is small enough that a focused test surface is cheap. The
end-to-end ``build_chapter_writing_brief`` integration is already
covered by ``tests/test_chapter_writing_brief.py`` and
``tests/test_chapter_writing_brief_memoir.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.state.loaders.chapter_meta import (
    load_book_category,
    load_chapter_meta,
    parse_overview_table,
    serialize_chapter_meta,
)
from tools.state.loaders.claudemd_sections import (
    callback_register_bullets,
    classify_rule,
    litmus_questions,
    rule_bullets,
)
from tools.state.loaders.people import (
    consent_status_warnings,
    person_payload,
    scan_for_named_characters,
)
from tools.state.loaders.recent_chapters import (
    collect_recent_chapters,
    count_similes,
    last_paragraph,
)


# ---------------------------------------------------------------------------
# chapter_meta
# ---------------------------------------------------------------------------


class TestParseOverviewTable:
    def test_extracts_lowercase_keys(self) -> None:
        text = (
            "## Overview\n\n"
            "| Title | The Storm |\n"
            "| POV | Lena |\n"
        )
        cells = parse_overview_table(text)
        assert cells["title"] == "The Storm"
        assert cells["pov"] == "Lena"

    def test_skips_dash_only_values(self) -> None:
        text = (
            "| Title | - |\n"
            "| POV | Lena |\n"
        )
        cells = parse_overview_table(text)
        assert "title" not in cells
        assert cells["pov"] == "Lena"

    def test_no_table_returns_empty(self) -> None:
        assert parse_overview_table("# Plain prose\n") == {}


class TestLoadChapterMeta:
    def test_overview_table_fills_missing_pov(self, tmp_path: Path) -> None:
        chapter_dir = tmp_path / "chapters" / "01-storm"
        chapter_dir.mkdir(parents=True)
        readme = chapter_dir / "README.md"
        readme.write_text(
            "## Overview\n\n"
            "| Field | Value |\n"
            "|---|---|\n"
            "| Title | The Storm |\n"
            "| POV | Lena |\n",
            encoding="utf-8",
        )
        meta, pov, overview = load_chapter_meta(readme, "01-storm")
        assert pov == "Lena"
        assert meta["title"] == "The Storm"
        assert overview["title"] == "The Storm"
        assert overview["pov"] == "Lena"

    def test_missing_readme_returns_empty(self, tmp_path: Path) -> None:
        meta, pov, overview = load_chapter_meta(
            tmp_path / "nope.md", "01-storm"
        )
        assert meta == {}
        assert pov == ""
        assert overview == {}


class TestSerializeChapterMeta:
    def test_passes_through_safe_keys(self) -> None:
        out = serialize_chapter_meta({
            "slug": "01", "title": "Opening", "number": 1,
            "extra_key": "ignored",
        })
        assert out == {"slug": "01", "title": "Opening", "number": 1}

    def test_coerces_non_scalars_to_str(self) -> None:
        out = serialize_chapter_meta({"title": ["x", "y"]})
        assert isinstance(out["title"], str)


class TestLoadBookCategory:
    def test_reads_frontmatter(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text(
            "---\nbook_category: memoir\n---\n\n# Book\n",
            encoding="utf-8",
        )
        assert load_book_category(tmp_path) == "memoir"

    def test_defaults_to_fiction(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# No frontmatter\n", encoding="utf-8")
        assert load_book_category(tmp_path) == "fiction"

    def test_missing_readme_defaults_to_fiction(self, tmp_path: Path) -> None:
        assert load_book_category(tmp_path) == "fiction"


# ---------------------------------------------------------------------------
# claudemd_sections
# ---------------------------------------------------------------------------


CLAUDEMD = """\
# Book CLAUDE.md

## Rules

- Avoid `passive voice` in action scenes.
- Always anchor the POV to the character's senses.

## Callback Register

- The cracked lantern (introduced Ch. 2)
- Lena's promise to her mother (Ch. 4)
"""


class TestClaudeMdSections:
    def test_rule_bullets_extracts_each(self) -> None:
        bullets = rule_bullets(CLAUDEMD)
        assert len(bullets) == 2
        assert "passive voice" in bullets[0]

    def test_callback_register_bullets(self) -> None:
        bullets = callback_register_bullets(CLAUDEMD)
        assert len(bullets) == 2
        assert "cracked lantern" in bullets[0]

    @pytest.mark.parametrize(
        "rule,expected",
        [
            ("Avoid `dropdown` phrasing", "block"),
            ("Banned: `synergy`", "block"),
            ("Anchor every scene to senses", "advisory"),
            ("Use `quotes` for emphasis", "advisory"),  # has backtick but no ban cue
        ],
    )
    def test_classify_rule(self, rule: str, expected: str) -> None:
        assert classify_rule(rule) == expected


class TestLitmusQuestions:
    def test_extracts_numbered(self) -> None:
        text = (
            "# Tone\n\n"
            "## Litmus Test\n\n"
            "1. Does the POV character earn the realisation?\n"
            "2. Is the metaphor anchored to a sense?\n"
        )
        questions = litmus_questions(text)
        assert len(questions) == 2
        assert "POV character" in questions[0]

    def test_no_section_returns_empty(self) -> None:
        assert litmus_questions("# unrelated\n") == []


# ---------------------------------------------------------------------------
# people
# ---------------------------------------------------------------------------


def _write_person(path: Path, **fields: str) -> None:
    fm_lines = [f"{k}: {v}" for k, v in fields.items()]
    path.write_text(
        "---\n" + "\n".join(fm_lines) + "\n---\n\n# Person\n",
        encoding="utf-8",
    )


class TestPersonPayload:
    def test_excludes_real_name(self, tmp_path: Path) -> None:
        path = tmp_path / "alice.md"
        _write_person(
            path,
            name="Alice",
            real_name="Alice Smith",  # private — must not leak
            consent_status="confirmed-consent",
            person_category="public-figure",
            anonymization="none",
            relationship="mentor",
            description="poet",
        )
        payload = person_payload(path)
        assert payload["slug"] == "alice"
        assert payload["name"] == "Alice"
        assert "real_name" not in payload
        assert payload["consent_status"] == "confirmed-consent"


class TestScanForNamedCharacters:
    def test_finds_by_name_not_slug(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        chars_dir.mkdir()
        (chars_dir / "lena.md").write_text(
            "---\nname: Lena\n---\n\n# Lena\n", encoding="utf-8"
        )
        (chars_dir / "bystander.md").write_text(
            "---\nname: Otto\n---\n\n# Otto\n", encoding="utf-8"
        )
        outline = "Lena confronts the antagonist."
        assert scan_for_named_characters(outline, chars_dir) == ["lena"]

    def test_skips_index(self, tmp_path: Path) -> None:
        chars_dir = tmp_path / "characters"
        chars_dir.mkdir()
        (chars_dir / "INDEX.md").write_text(
            "---\nname: Lena\n---\n", encoding="utf-8"
        )
        assert scan_for_named_characters("Lena fights.", chars_dir) == []


class TestConsentStatusWarnings:
    @pytest.mark.parametrize(
        "consent_status,expected_tier",
        [
            ("", "missing"),
            ("pending", "pending"),
            ("refused", "refused"),
        ],
    )
    def test_warns_on_unsafe_status(
        self, consent_status: str, expected_tier: str,
    ) -> None:
        warnings = consent_status_warnings([
            {"name": "Bob", "consent_status": consent_status},
        ])
        assert len(warnings) == 1
        assert warnings[0]["tier"] == expected_tier

    @pytest.mark.parametrize(
        "consent_status",
        ["confirmed-consent", "not-required", "not-asking"],
    )
    def test_silent_on_safe_status(self, consent_status: str) -> None:
        assert consent_status_warnings([
            {"name": "Bob", "consent_status": consent_status},
        ]) == []


# ---------------------------------------------------------------------------
# recent_chapters
# ---------------------------------------------------------------------------


def _write_draft(chapter_dir: Path, body: str) -> None:
    chapter_dir.mkdir(parents=True, exist_ok=True)
    (chapter_dir / "draft.md").write_text(body, encoding="utf-8")


class TestRecentChapters:
    def test_count_similes_strips_frontmatter(self, tmp_path: Path) -> None:
        draft = tmp_path / "draft.md"
        draft.write_text(
            "---\nlike a thief: front-matter only\n---\n\n"
            "She moved like a shadow. The wind howled like a wolf.\n",
            encoding="utf-8",
        )
        # Two simile markers in body; the frontmatter line ignored.
        assert count_similes(draft) == 2

    def test_last_paragraph_truncates(self, tmp_path: Path) -> None:
        draft = tmp_path / "draft.md"
        long = "x " * 700
        draft.write_text(f"# Ch\n\nIntro paragraph.\n\n{long}\n", encoding="utf-8")
        assert last_paragraph(draft).endswith("...")

    def test_collect_recent_chapters_orders_numerically(
        self, tmp_path: Path,
    ) -> None:
        chapters = tmp_path / "chapters"
        for slug in ("01-a", "02-b", "03-c", "10-j"):
            (chapters / slug).mkdir(parents=True)
        recent = collect_recent_chapters(chapters, "10-j", n=3)
        assert [r.name for r in recent] == ["01-a", "02-b", "03-c"]

    def test_collect_excludes_current(self, tmp_path: Path) -> None:
        chapters = tmp_path / "chapters"
        for slug in ("01-a", "02-b", "03-c"):
            (chapters / slug).mkdir(parents=True)
        recent = collect_recent_chapters(chapters, "02-b", n=3)
        assert [r.name for r in recent] == ["01-a"]

    def test_collect_when_current_not_on_disk(self, tmp_path: Path) -> None:
        chapters = tmp_path / "chapters"
        for slug in ("01-a", "02-b", "03-c"):
            (chapters / slug).mkdir(parents=True)
        recent = collect_recent_chapters(chapters, "99-future", n=2)
        assert [r.name for r in recent] == ["02-b", "03-c"]
