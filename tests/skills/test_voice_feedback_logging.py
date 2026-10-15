"""The review-feedback logging is wired through the chapter pipeline — Epic #663 / Issue #669."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools.db.review_feedback import VALID_SOURCES

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS = PLUGIN_ROOT / "skills"
SHARED = PLUGIN_ROOT / "reference" / "craft" / "chapter-writing-shared.md"
CLAUDE_MD = PLUGIN_ROOT / "CLAUDE.md"

# skill -> source_skill value it must log with (None: covered through the shared § it references)
LOGGING_SKILLS = {
    "chapter-fixer": "fixer",
    "chapter-scene-rewriter": "rewriter",
    "chapter-humanizer": "humanizer",
    "chapter-proofreader": "proofreader",
    "chapter-reviewer": "reviewer",
    "chapter-reviewer-memoir": "reviewer",
    "chapter-writer": "writer",
    "chapter-writer-memoir": "writer",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestSharedProcedure:
    def test_logging_subsection_exists_under_user_feedback_handling(self):
        text = read(SHARED)
        feedback = text.index("## § User Feedback Handling")
        logging = text.index("### Logging Voice Feedback")
        assert feedback < logging < text.index("## § Pre-Logic Audit")

    def test_names_the_tool_and_every_decision(self):
        text = read(SHARED)
        section = text[text.index("### Logging Voice Feedback"): text.index("## § Pre-Logic Audit")]
        assert "log_review_feedback(" in section
        for decision in ("accepted", "reworked", "rejected"):
            assert f"`{decision}`" in section

    def test_logging_never_blocks_the_flow(self):
        text = read(SHARED)
        section = text[text.index("### Logging Voice Feedback"): text.index("## § Pre-Logic Audit")]
        assert "never blocks" in section

    def test_memoir_is_classified_at_logging_time_without_names(self):
        text = read(SHARED)
        section = text[text.index("### Logging Voice Feedback"): text.index("## § Pre-Logic Audit")]
        assert "voice-dimensions" in section
        assert "without\n  names or facts" in section or "without names or facts" in section


@pytest.mark.parametrize("skill,source", sorted(LOGGING_SKILLS.items()))
def test_skill_logs_with_a_valid_source(skill: str, source: str):
    assert source in VALID_SOURCES
    text = read(SKILLS / skill / "SKILL.md")
    assert "Logging Voice Feedback" in text, f"{skill} does not reference the logging procedure"
    assert f'source_skill="{source}"' in text, f"{skill} must log with source_skill={source!r}"


def test_every_source_skill_value_in_skills_is_valid():
    found = set()
    for skill in SKILLS.glob("*/SKILL.md"):
        found |= set(re.findall(r'source_skill="([a-z_]+)"', read(skill)))
    assert found <= VALID_SOURCES, sorted(found - VALID_SOURCES)


class TestRoutingAndRules:
    def test_routing_table_has_the_voice_harvest_row(self):
        text = read(CLAUDE_MD)
        assert "`/storyforge:chapter-voice-harvest`" in text
        assert "| \"Voice harvest\"" in text

    def test_pipeline_places_harvest_between_review_and_humanizer(self):
        text = read(CLAUDE_MD)
        line = next(line for line in text.splitlines() if line.startswith("4. Chapter Writing"))
        assert line.index("Chapter Review") < line.index("Chapter Voice Harvest") < line.index(
            "Chapter Humanizer")
        assert text.index("10a2. `/storyforge:chapter-voice-harvest`") < text.index(
            "10b. `/storyforge:chapter-humanizer`")

    def test_rule_21_requires_logging(self):
        text = read(CLAUDE_MD)
        rule = text[text.index("21. **ALWAYS log verified author feedback**"):]
        assert "log_review_feedback" in rule.split("\n\n")[0]
        assert "never blocks" in rule.split("\n\n")[0]

    def test_memoir_tag_convention_is_documented(self):
        text = read(CLAUDE_MD)
        assert "treat `memoir` as a genre of every memoir book" in text

    @pytest.mark.parametrize("path", [
        "skills/chapter-reviewer/SKILL.md",
        "skills/chapter-reviewer-memoir/SKILL.md",
        "skills/author-check/SKILL.md",
    ])
    def test_genre_filters_know_the_memoir_tag(self, path):
        assert "`memoir`" in read(PLUGIN_ROOT / path)

    def test_shared_style_principle_activation_knows_the_memoir_tag(self):
        assert "additionally include `memoir`" in read(SHARED)


class TestBanlistSemantics:
    def test_study_author_no_longer_writes_intentional_quirks_into_recurring_tics(self):
        text = read(SKILLS / "study-author" / "SKILL.md")
        line = next(line for line in text.splitlines() if "Deliberate Imperfections" in line)
        assert 'section="recurring_tics"' not in line
        assert 'section="style_principles"' in line
