"""Skill size guard — catches skills that exceed the budget defined in CLAUDE.md.

CLAUDE.md rule: "Skill size: skills over 25 k chars or 400 LOC require a
split-or-trim plan."

This test warns at 28K (a buffer above the 25K rule) so we catch drift before
it becomes a bloat problem. Known offenders are marked xfail so CI stays green
while their trim plan is in progress.

See: Issue #235 (chapter-writer trim plan)
"""

from __future__ import annotations

from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
WARN_BYTES = 28_000
FRONTMATTER_SEP = "---"

# Skills currently over budget with an active trim plan.
# Remove the entry once the skill is trimmed under WARN_BYTES.
KNOWN_OVERSIZED: dict[str, str] = {
    "chapter-writer": "Issue #235 — trim plan in progress",
}


def _body_bytes(skill_file: Path) -> int:
    text = skill_file.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else text
    return len(body.encode("utf-8"))


def _all_skills() -> list[tuple[str, Path]]:
    return sorted(
        (p.parent.name, p)
        for p in SKILLS_DIR.rglob("SKILL.md")
        if p.is_file()
    )


@pytest.mark.parametrize("skill_name,skill_file", _all_skills())
def test_skill_size_budget(skill_name: str, skill_file: Path) -> None:
    """Skill body must stay under the 28K warning threshold."""
    size = _body_bytes(skill_file)
    if size <= WARN_BYTES:
        return

    message = (
        f"Skill '{skill_name}' body is {size:,} bytes "
        f"({size - WARN_BYTES:+,} over the 28K budget). "
        f"CLAUDE.md rule: skills over 25K require a split-or-trim plan."
    )
    if skill_name in KNOWN_OVERSIZED:
        reason = KNOWN_OVERSIZED[skill_name]
        pytest.xfail(f"{message} Known: {reason}")
    else:
        pytest.fail(message)
