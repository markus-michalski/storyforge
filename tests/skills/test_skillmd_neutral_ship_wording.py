"""Regression guard: skill files may not depend on a third-party git workflow command.

Which command ships a change (branch, commit, PR) is the user's own tooling.
A skill that names one specific plugin's command sends users without that
plugin to a command that does not exist.

Flagged in every Markdown file under skills/: slash commands from a namespace
other than StoryForge's own, and the bare `git-workflow` command name.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"

# The lookbehind keeps paths and URLs such as `{plugin_root}/a:b` from matching.
FOREIGN_COMMAND = re.compile(r"(?<![\w.}/-])/(?!storyforge:)[a-z][a-z0-9-]*:[a-z]|git-workflow")

GLOBAL_WRITE_NOTICES = [
    ("promote-rule", "This change is uncommitted"),
    ("report-issue", "This write is local and uncommitted"),
]


def _skill_markdown_files() -> list[Path]:
    return sorted(SKILLS_DIR.rglob("*.md"))


def test_skill_files_are_discovered() -> None:
    """An empty file list would only skip the parametrized guard, not fail it."""
    assert _skill_markdown_files(), f"no Markdown files found under {SKILLS_DIR}"


@pytest.mark.parametrize(
    "line",
    [
        "run `/git-pr-workflows:git-workflow` from `{plugin_root}`",
        "run /some-plugin:ship now",
        "use the `git-workflow` command",
    ],
)
def test_detector_flags_third_party_commands(line: str) -> None:
    assert FOREIGN_COMMAND.search(line)


@pytest.mark.parametrize(
    "line",
    [
        "run `/storyforge:promote-rule` instead",
        "using whatever git workflow you prefer",
        "see `{plugin_root}/reference:notes` and https://example.org/a:b",
    ],
)
def test_detector_accepts_own_commands_and_neutral_wording(line: str) -> None:
    assert not FOREIGN_COMMAND.search(line)


@pytest.mark.parametrize(
    "skill_file",
    _skill_markdown_files(),
    ids=lambda p: p.relative_to(SKILLS_DIR).as_posix(),
)
def test_no_third_party_git_workflow_command(skill_file: Path) -> None:
    flagged = [
        f"  L{number}: {line.strip()}"
        for number, line in enumerate(skill_file.read_text(encoding="utf-8").splitlines(), start=1)
        if FOREIGN_COMMAND.search(line)
    ]

    assert not flagged, (
        f"{skill_file.relative_to(SKILLS_DIR).as_posix()} names a third-party command. "
        "Describe the steps (branch, commit, PR) in tool-neutral wording instead:\n" + "\n".join(flagged)
    )


@pytest.mark.parametrize(("skill", "uncommitted_notice"), GLOBAL_WRITE_NOTICES)
def test_global_write_notice_names_the_steps(skill: str, uncommitted_notice: str) -> None:
    """A global rule write is lost on the next update unless the user is told how to ship it."""
    text = " ".join((SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8").split())

    assert uncommitted_notice in text
    assert "branch, commit, and open a PR from `{plugin_root}`" in text
