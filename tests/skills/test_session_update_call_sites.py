"""Regression guard for Issue #378 — the `update_session()` call sites.

Issue #378: `last_chapter`/`last_phase` session fields were dead because no
skill in the pipeline ever wrote them. `chapter-writer`, `chapter-writer-memoir`,
and `rolling-planner` now call `update_session()` to persist them.

This is a static text check, not a runtime one — it can't prove the model
follows the instruction, but it guards against a future edit silently
deleting the call (e.g. during an unrelated Step-7 refactor) without any
test noticing. Cheap insurance for a bug class that went unnoticed for a
long time before #378 was filed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent

SKILLS_WITH_SESSION_UPDATE = (
    "chapter-writer",
    "chapter-writer-memoir",
    "rolling-planner",
)


def _read_body(name: str) -> str:
    path = PLUGIN_ROOT / "skills" / name / "SKILL.md"
    assert path.is_file(), f"{path} does not exist"
    return path.read_text(encoding="utf-8")


class TestSessionUpdateCallSites:
    @pytest.mark.parametrize("skill_name", SKILLS_WITH_SESSION_UPDATE)
    def test_skill_calls_update_session(self, skill_name: str) -> None:
        body = _read_body(skill_name)
        assert "update_session(" in body, (
            f"{skill_name}/SKILL.md no longer calls update_session() — "
            f"last_chapter/last_phase will go dead again (Issue #378)."
        )

    @pytest.mark.parametrize("skill_name", SKILLS_WITH_SESSION_UPDATE)
    def test_update_session_call_passes_last_book_and_last_chapter(self, skill_name: str) -> None:
        body = _read_body(skill_name)
        # Isolate the update_session(...) call itself, not just the surrounding prose.
        start = body.index("update_session(")
        end = body.index(")", start)
        call_args = body[start:end]
        assert "last_book=" in call_args, (
            f"{skill_name}/SKILL.md's update_session() call dropped last_book= — "
            f"session's last_chapter could then point at the wrong book."
        )
        assert "last_chapter=" in call_args, (
            f"{skill_name}/SKILL.md's update_session() call dropped last_chapter="
        )
