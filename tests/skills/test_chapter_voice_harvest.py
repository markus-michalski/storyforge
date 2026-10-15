"""Structural and contract tests for the chapter-voice-harvest skill — Epic #663 / Issue #668."""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest
import yaml

import server as server_mod
from tests.smoke._helpers import registered_tool_names
from tools.analysis.voice_candidates import build_voice_candidates

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


def section(body: str, heading: str) -> str:
    """Text of one H2 section, up to the next H2."""
    start = body.index(f"## {heading}")
    nxt = body.find("\n## ", start + 1)
    return body[start: nxt if nxt != -1 else len(body)]


def _split_args(raw: str) -> list[str]:
    parts, depth, current = [], 0, ""
    for ch in raw:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())
    return parts


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


class TestToolContracts:
    CALL_RE = re.compile(r"`(?:mcp__storyforge-mcp__)?([a-z_]+)\(([^`]*?)\)`", re.DOTALL)

    def _calls(self, body: str):
        return [(m.group(1), _split_args(" ".join(m.group(2).split())))
                for m in self.CALL_RE.finditer(body)
                if m.group(1) in registered_tool_names()]

    def test_the_whole_feedback_tool_chain_is_used(self, body):
        used = {name for name, _ in self._calls(body)}
        expected = {
            "get_book_full", "get_session", "get_craft_reference", "list_pending_feedback",
            "set_feedback_classification", "get_voice_candidates", "get_author",
            "write_author_discovery", "mark_feedback_harvested", "discard_feedback",
            "log_review_feedback", "get_self_edit_hunks", "refresh_draft_baseline",
        }
        assert expected <= used, sorted(expected - used)

    def test_every_call_matches_the_registered_signature(self, body):
        problems = []
        for name, args in self._calls(body):
            params = list(inspect.signature(getattr(server_mod, name)).parameters)
            positional = [a for a in args if "=" not in a or a.startswith(('"', "'"))]
            if len(positional) > len(params):
                problems.append(f"{name}: {len(positional)} positional args, {len(params)} params")
            for arg in args:
                if "=" in arg and not arg.startswith(('"', "'")):
                    kw = arg.split("=", 1)[0].strip()
                    if kw not in params:
                        problems.append(f"{name}: unknown keyword {kw!r}")
        assert not problems, problems

    def test_tool_names_in_prose_are_registered(self, body):
        named = set(re.findall(r"`(?:mcp__storyforge-mcp__)?([a-z_]+)\(", body))
        unknown = {n for n in named if n not in registered_tool_names()}
        assert not unknown, sorted(unknown)


class TestCandidateFields:
    def test_walk_template_uses_only_real_candidate_fields(self, body):
        rows = [
            {"id": i, "author_slug": "a", "book_slug": "b", "chapter_slug": f"{i:02d}",
             "book_category": "fiction", "genres": "drama", "source_skill": "reviewer",
             "decision": "accepted", "dimension": "sentence_rhythm", "direction": "shorter",
             "normalized_rule": "Shorter.", "status": "classified"}
            for i in range(1, 4)
        ]
        candidate = build_voice_candidates(rows)["candidates"][0]
        template = section(body, "Step 5 — Walk the candidates")
        fenced = re.search(r"```\n(.*?)```", template, re.DOTALL).group(1)
        fields = set(re.findall(r"\{([a-z_]+)", fenced)) - {"n", "total", "universal"}
        assert fields <= set(candidate) | {"genres"}, sorted(fields - set(candidate))

    def test_conflict_step_uses_real_side_keys(self, body):
        step = section(body, "Step 4 — Conflicts first")
        for key in ("sides[0]", "sides[1]", "evidence_ids", "chapter_count"):
            assert key in step


class TestGates:
    def test_empty_log_exits_without_a_walk(self, body):
        step = section(body, "Step 1 — Count what is there")
        assert "Nothing to harvest" in step
        assert "Never start a walk on an empty log" in step

    def test_every_write_path_asks_first(self, body):
        step5 = section(body, "Step 5 — Walk the candidates")
        assert "AskUserQuestion" in step5
        assert "Never write or promote without an explicit answer" in step5
        assert "AskUserQuestion" in section(body, "Step 2 — Classify the open entries")

    def test_entries_are_closed_only_after_the_write(self, body):
        step = section(body, "Step 6 — Promote")
        assert step.index("write_author_discovery(") < step.index("mark_feedback_harvested(")
        assert "already_present" in step

    def test_fiction_scope_parameters(self, body):
        step = section(body, "Step 6 — Promote")
        assert "scope.genres" in step and "scope.universal" in step

    def test_banlist_sections_are_not_targets(self, text, body):
        assert "donts and recurring_tics are not targets" in body
        assert "(as style_principles)" in text
        step = section(body, "Step 6 — Promote")
        assert 'section="style_principles"' in step


class TestMemoir:
    def test_memoir_promotion_is_not_universal_and_has_no_example(self, body):
        step = section(body, "Step 6 — Promote")
        assert 'genres="memoir"' in step
        assert "universal=False" in step
        assert "no `example`" in step

    def test_memoir_never_prints_raw_text_or_names(self, body):
        rules = section(body, "Memoir rules")
        assert "Never print, quote or reconstruct" in rules
        assert "names of real people" in rules

    def test_memoir_gets_no_examples_in_the_walk(self, body):
        assert "Memoir: no examples at all" in section(body, "Step 5 — Walk the candidates")

    def test_other_category_entries_are_left_alone(self, body):
        step = section(body, "Step 1 — Count what is there")
        assert "Entries of the other\ncategory stay untouched" in step or "stay untouched" in step


class TestClassification:
    def test_classify_once_with_one_stated_exception(self, body):
        assert "classify once" in body.lower()
        assert "exception to \"classify once\"" in body

    def test_never_invents_feedback(self, body):
        assert "Never invent feedback" in body

    def test_late_entries_carry_over_to_the_next_chapter(self, body):
        step = section(body, "Step 1 — Count what is there")
        assert "picked up by the next chapter's harvest" in step

    def test_mixed_comments_are_split_via_log_review_feedback(self, body):
        step = section(body, "Step 2 — Classify the open entries")
        assert "log_review_feedback(" in step


class TestManualEdits:
    def test_step_only_runs_on_the_authors_say_so(self, body):
        step = section(body, "Step 0 — Manual edits (only when the author said they changed the text)")
        assert " ".join(step.split()).count("Never on your own initiative") == 1

    def test_step_handles_every_status_and_resets_the_baseline(self, body):
        step = section(body, "Step 0 — Manual edits (only when the author said they changed the text)")
        for status in ("memoir_unsupported", "no_baseline", "stale"):
            assert status in step
        assert step.index("get_self_edit_hunks(") < step.index("log_review_feedback(")
        assert step.rindex("refresh_draft_baseline(") > step.index("log_review_feedback(")

    def test_hunks_are_logged_as_self_edit_unclassified(self, body):
        step = section(body, "Step 0 — Manual edits (only when the author said they changed the text)")
        assert 'source_skill="self_edit"' in step
        assert 'decision="self_edit"' in step
        assert "classification empty" in " ".join(step.split())

    def test_description_triggers_on_the_authors_phrase(self, text):
        assert "Ich habe den Text noch etwas geändert" in text

    def test_hunks_are_paged_confirmed_and_logged_before_the_baseline_resets(self, body):
        step = " ".join(section(
            body, "Step 0 — Manual edits (only when the author said they changed the text)").split())
        assert "`offset`" in step and "`truncated`" in step
        assert "AskUserQuestion" in step
        assert "per machine" in step
        assert "only when every confirmed hunk was logged" in step
        assert step.index("AskUserQuestion") < step.index("log_review_feedback(")
