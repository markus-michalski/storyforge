"""Static smoketest for the plot-architect / plot-architect-memoir split (Issue #126).

Asserts that:
- Both skill files exist with the right frontmatter (name, model, user-invocable).
- The fiction skill refuses memoir books and routes to plot-architect-memoir.
- The memoir skill refuses fiction books and routes to plot-architect.
- The fiction catalog (3-Act, Hero's Journey, Snowflake, ...) does not leak
  into the memoir skill, and the memoir structure types
  (chronological / thematic / braided / vignette) do not leak into fiction.
- The plugin-root CLAUDE.md routing table mentions both skills.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_FICTION = PLUGIN_ROOT / "skills" / "plot-architect" / "SKILL.md"
SKILL_MEMOIR = PLUGIN_ROOT / "skills" / "plot-architect-memoir" / "SKILL.md"
CLAUDEMD = PLUGIN_ROOT / "CLAUDE.md"

FICTION_STRUCTURE_TERMS = (
    "3-Act",
    "Hero's Journey",
    "Save the Cat",
    "Snowflake",
    "Fichtean Curve",
    "Seven-Point Structure",
)

MEMOIR_STRUCTURE_TYPES = ("chronological", "thematic", "braided", "vignette")

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _read_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    assert m, f"{path} missing frontmatter"
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm


def _read_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    return text[m.end() :] if m else text


# ---------------------------------------------------------------------------
# Both files exist with the right frontmatter
# ---------------------------------------------------------------------------


class TestSkillFiles:
    def test_fiction_skill_exists(self) -> None:
        assert SKILL_FICTION.is_file()

    def test_memoir_skill_exists(self) -> None:
        assert SKILL_MEMOIR.is_file()

    def test_fiction_frontmatter_correct(self) -> None:
        fm = _read_frontmatter(SKILL_FICTION)
        assert fm["name"] == "plot-architect"
        assert fm["model"] == "claude-opus-4-7"
        assert fm["user-invocable"] == "true"

    def test_memoir_frontmatter_correct(self) -> None:
        fm = _read_frontmatter(SKILL_MEMOIR)
        assert fm["name"] == "plot-architect-memoir"
        assert fm["model"] == "claude-opus-4-7"
        assert fm["user-invocable"] == "true"


# ---------------------------------------------------------------------------
# Routing — each skill refuses the other category
# ---------------------------------------------------------------------------


class TestCrossRouting:
    def test_fiction_refuses_memoir_and_routes(self) -> None:
        body = _read_body(SKILL_FICTION)
        # Must mention the memoir skill by name.
        assert "/storyforge:plot-architect-memoir" in body, (
            "Fiction skill must route memoir books to plot-architect-memoir"
        )
        # Must explicitly check book_category.
        assert "book_category" in body
        assert "memoir" in body  # at least mentioned in the routing-out clause

    def test_memoir_refuses_fiction_and_routes(self) -> None:
        body = _read_body(SKILL_MEMOIR)
        assert "/storyforge:plot-architect" in body, "Memoir skill must route fiction books to plot-architect"
        assert "book_category" in body


# ---------------------------------------------------------------------------
# Catalog isolation — no fiction structures in memoir, no memoir types in fiction
# ---------------------------------------------------------------------------


class TestCatalogIsolation:
    @pytest.mark.parametrize("term", FICTION_STRUCTURE_TERMS)
    def test_memoir_skill_does_not_carry_fiction_catalog(self, term: str) -> None:
        body = _read_body(SKILL_MEMOIR)
        # The memoir skill may mention the catalog by name in the
        # routing-out clause ("(3-Act, Hero's Journey, Snowflake, ...) does
        # not apply"), but not as workflow steps. We allow at most one hit.
        hits = body.count(term)
        assert hits <= 1, (
            f"Memoir skill mentions fiction term {term!r} {hits} times — "
            f"workflow content is leaking. Allowed: only the routing-out clause."
        )

    @pytest.mark.parametrize("structure_type", MEMOIR_STRUCTURE_TYPES)
    def test_fiction_skill_does_not_carry_memoir_types(
        self,
        structure_type: str,
    ) -> None:
        body = _read_body(SKILL_FICTION)
        # The fiction skill is allowed to mention memoir terms only in the
        # routing-out clause. Most types are uncommon English words, so a
        # strict "≤1 occurrence" rule catches accidental workflow leakage.
        hits = body.lower().count(structure_type.lower())
        assert hits <= 1, (
            f"Fiction skill mentions memoir structure type {structure_type!r} "
            f"{hits} times — memoir workflow content is leaking. "
            f"Allowed: only the routing-out clause."
        )


# ---------------------------------------------------------------------------
# Plugin-root routing table is consistent
# ---------------------------------------------------------------------------


class TestRoutingTable:
    def test_claudemd_mentions_both_skills(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "/storyforge:plot-architect" in text
        assert "/storyforge:plot-architect-memoir" in text

    def test_routing_table_distinguishes_fiction_vs_memoir(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        # Both fiction-tagged and memoir-tagged plot rows must exist.
        # Match the row content rather than fixed wording so future edits to
        # the trigger phrases don't silently break this guard.
        fiction_row = re.search(
            r"^\|\s*\"Plot\"[^|]*fiction[^|]*\|\s*`?/storyforge:plot-architect`?\s*\|",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        memoir_row = re.search(
            r"^\|\s*\"Plot\"[^|]*memoir[^|]*\|\s*`?/storyforge:plot-architect-memoir`?\s*\|",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        assert fiction_row, "CLAUDE.md routing table missing fiction plot row"
        assert memoir_row, "CLAUDE.md routing table missing memoir plot row"
