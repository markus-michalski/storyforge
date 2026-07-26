"""Regression guard: no SKILL.md may instruct a direct Edit of CLAUDE.md's ## Rules section.

Phase 4 (Issue #282) migrated book rules from CLAUDE.md text into the book_rules
SQLite DB. CLAUDE.md's `## Rules (from DB)` section is now a read-only rendered
view — editing that text directly does nothing. All rule writes must go through
`append_book_rule()` / `update_book_rule()` MCP tools.

Issue #448 audited all 55 skills and found zero violations.
This test is a regression guard that will fire on any future skill that reverts
to the pre-Phase-4 hand-edit pattern.

What this catches
-----------------
A line that simultaneously:
  - references "CLAUDE.md" AND
  - contains an explicit write/add/edit instruction keyword AND
  - references the Rules section ("## Rules", "Rules section", "Rules block")

...and is NOT excluded by one of the safe-context patterns below.

Known-legitimate exclusions applied per line:
  - `get_book_claudemd` / `init_book_claudemd` / `sync_book_claudemd`  (MCP reads/writes)
  - `append_book_rule` / `update_book_rule`                            (correct write path)
  - "not by editing" / "do not edit" / "editor refuses" / "read-only"  (explicit negations)
  - pov / tense / writing_mode / book_facts — Book Facts editing is explicitly allowed
    per storyforge CLAUDE.md "Removed (Issue #236)": "edit the book's CLAUDE.md
    directly to update Book Facts"

Coverage limit
--------------
Line-level text search, not semantic analysis. Catches the most obvious violation
shape ("Edit CLAUDE.md's ## Rules section to add a rule") but will miss violations
spread across two lines or phrased very differently. Pair with manual review when
introducing new rule-persistence flows.

NOT excluded: `genre` — while "genre" appears in many skills, a line that also
contains CLAUDE.md + ## Rules + an edit verb is not a normal genre reference.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"

# Patterns that indicate a write instruction targeting CLAUDE.md's Rules section.
VIOLATION_WRITE_KEYWORDS = re.compile(
    r"\b(edit|write|add|insert|append|touch|update|modify)\b",
    re.IGNORECASE,
)

VIOLATION_RULES_KEYWORDS = re.compile(
    r"##\s*Rules|Rules\s+section|Rules\s+block",
    re.IGNORECASE,
)

VIOLATION_CLAUDEMD_KEYWORDS = re.compile(
    r"CLAUDE\.md",
    re.IGNORECASE,
)

# Safe contexts that override the violation signal.
NEGATION_RE = re.compile(
    r"not\s+by\s+editing|do\s+not\s+edit|never\s+edit|do\s+not\s+touch"
    r"|refuses\s+to\s+touch|editor\s+refuses"
    r"|read-only|rendered\s+view",
    re.IGNORECASE,
)

CORRECT_MCP_TOOLS_RE = re.compile(
    r"append_book_rule|update_book_rule|get_book_claudemd"
    r"|init_book_claudemd|sync_book_claudemd|list_book_rules",
)

# Book Facts keywords — pov/tense/writing_mode editing is explicitly allowed.
# Deliberately excludes `genre` (too broad: a line with genre + CLAUDE.md + ## Rules
# + an edit verb is not a normal genre reference and should be flagged).
BOOK_FACTS_RE = re.compile(
    r"\b(pov|tense|writing_mode|book_title|book_facts)\b",
    re.IGNORECASE,
)


def _check_skill(skill_dir: Path) -> list[tuple[int, str]]:
    """Return list of (line_number, line_text) for suspected violations."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return []

    violations: list[tuple[int, str]] = []
    for i, line in enumerate(skill_md.read_text(encoding="utf-8").splitlines(), start=1):
        if (
            VIOLATION_CLAUDEMD_KEYWORDS.search(line)
            and VIOLATION_RULES_KEYWORDS.search(line)
            and VIOLATION_WRITE_KEYWORDS.search(line)
            and not NEGATION_RE.search(line)
            and not CORRECT_MCP_TOOLS_RE.search(line)
            and not BOOK_FACTS_RE.search(line)
        ):
            violations.append((i, line.strip()))

    return violations


def _all_skill_dirs() -> list[Path]:
    return sorted(p for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())


class TestSkillRulesEditLint:
    @pytest.mark.parametrize("skill_dir", _all_skill_dirs(), ids=lambda p: p.name)
    def test_no_direct_claudemd_rules_edit_instruction(self, skill_dir: Path) -> None:
        """No SKILL.md may instruct a direct Edit of CLAUDE.md's ## Rules section.

        Post-Phase-4 (Issue #282), CLAUDE.md's ## Rules is a read-only rendered
        view of the book_rules DB. Any skill that tells Claude to edit that text
        directly would silently do nothing — the render is regenerated from the DB.
        """
        violations = _check_skill(skill_dir)
        assert not violations, (
            f"{skill_dir.name}/SKILL.md appears to instruct a direct Edit of "
            f"CLAUDE.md's ## Rules section (Issue #282/448 regression). "
            f"Use `append_book_rule(book_slug, text)` or `update_book_rule(...)` "
            f"instead. Flagged lines:\n"
            + "\n".join(f"  L{ln}: {text}" for ln, text in violations)
            + "\n\nIf this line is a legitimate negation or Book Facts edit, "
            "add the appropriate exclusion keyword to NEGATION_RE or BOOK_FACTS_RE."
        )
