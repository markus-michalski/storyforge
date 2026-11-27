"""Regression guard: no SKILL.md may depend on a third-party git workflow command.

Which command ships a change (branch, commit, PR) is the user's own tooling.
A skill that names one specific plugin's command sends users without that
plugin to a command that does not exist.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"

FOREIGN_COMMAND_PREFIX = "git-pr-workflows:"


def _all_skill_files() -> list[Path]:
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


@pytest.mark.parametrize("skill_md", _all_skill_files(), ids=lambda p: p.parent.name)
def test_no_third_party_git_workflow_command(skill_md: Path) -> None:
    flagged = [
        f"  L{number}: {line.strip()}"
        for number, line in enumerate(skill_md.read_text(encoding="utf-8").splitlines(), start=1)
        if FOREIGN_COMMAND_PREFIX in line
    ]

    assert not flagged, (
        f"{skill_md.parent.name}/SKILL.md names a third-party git workflow command. "
        "Describe the steps (branch, commit, PR) in tool-neutral wording instead:\n" + "\n".join(flagged)
    )
