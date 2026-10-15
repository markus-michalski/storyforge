"""Structural tests for the chapter-voice-harvest skill — Epic #663 / Issue #668."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from tests.smoke._helpers import registered_tool_names

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL = PLUGIN_ROOT / "skills" / "chapter-voice-harvest" / "SKILL.md"


@pytest.fixture(scope="module")
def text() -> str:
    return SKILL.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def frontmatter(text: str) -> dict:
    return yaml.safe_load(text.split("---", 2)[1])


@pytest.fixture(scope="module")
def body(text: str) -> str:
    return text.split("---", 2)[2]


class TestFrontmatter:
    def test_name_matches_directory(self, frontmatter):
        assert frontmatter["name"] == "chapter-voice-harvest"

    def test_required_fields(self, frontmatter):
        assert frontmatter["model"] == "claude-opus-5"
        assert frontmatter["user-invocable"] is True
        assert frontmatter["argument-hint"]

    def test_description_has_use_when_triggers(self, frontmatter):
        description = frontmatter["description"]
        assert "Use when" in description
        assert "voice harvest" in description.lower()


class TestBudget:
    def test_under_the_skill_size_budget(self, body):
        assert len(body.encode("utf-8")) < 25_000
        assert len(body.splitlines()) < 400


class TestToolReferences:
    EXPECTED = {
        "get_book_full", "get_session", "get_craft_reference", "list_pending_feedback",
        "set_feedback_classification", "get_voice_candidates", "get_author",
        "write_author_discovery", "mark_feedback_harvested", "discard_feedback",
    }

    def test_every_mcp_tool_named_in_the_skill_exists(self, body):
        named = set(re.findall(r"`(?:mcp__storyforge-mcp__)?([a-z_]+)\(", body))
        registered = set(registered_tool_names())
        unknown = {n for n in named if n not in registered and n not in {"Edit", "Read"}}
        assert not unknown, f"skill names tools that are not registered: {sorted(unknown)}"

    def test_uses_the_whole_feedback_tool_chain(self, body):
        missing = {t for t in self.EXPECTED if t not in body}
        assert not missing, sorted(missing)


class TestGuards:
    def test_empty_log_exits_without_a_walk(self, body):
        assert "Nothing to harvest" in body or "nothing to harvest" in body.lower()

    def test_promotion_requires_confirmation(self, body):
        assert "AskUserQuestion" in body
        assert re.search(r"never (write|promote)[^.]*without", body, re.IGNORECASE)

    def test_promotion_goes_through_write_author_discovery_with_scope(self, body):
        assert "universal=" in body
        assert "genres=" in body

    def test_candidates_are_closed_after_promotion(self, body):
        assert body.index("write_author_discovery") < body.index("mark_feedback_harvested")

    def test_memoir_privacy_rules_are_stated(self, body):
        lowered = body.lower()
        assert "memoir" in lowered
        assert "never" in lowered and "name" in lowered
        assert "before/after" in lowered or "raw text" in lowered

    def test_does_not_reclassify_or_invent_feedback(self, body):
        lowered = body.lower()
        assert "classify once" in lowered
        assert "never invent" in lowered or "never fabricate" in lowered

    def test_humanizer_and_proofreader_carry_over(self, body):
        assert "carry" in body.lower()
