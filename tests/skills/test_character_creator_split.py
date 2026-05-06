"""Static smoketest for the character-creator / character-creator-memoir split (Issue #177).

Asserts that:
- Both skill files exist with the right frontmatter (name, model, user-invocable).
- The fiction skill refuses memoir books and routes to character-creator-memoir.
- The memoir skill refuses fiction books and routes to character-creator.
- Fiction-only terms (Want vs. Need, Fatal Flaw, The Ghost, Lie they Believe,
  Truth they'll learn) appear at most once in the memoir skill (routing-out only).
- Memoir-only terms (consent_status, anonymization, real_name, person_category)
  appear at most once in the fiction skill.
- The plugin-root CLAUDE.md routing table mentions both skills.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_FICTION = PLUGIN_ROOT / "skills" / "character-creator" / "SKILL.md"
SKILL_MEMOIR = PLUGIN_ROOT / "skills" / "character-creator-memoir" / "SKILL.md"
CLAUDEMD = PLUGIN_ROOT / "CLAUDE.md"

# Terms that belong exclusively to the fiction 14-step workflow
FICTION_ONLY_TERMS = (
    "Want vs. Need",
    "Fatal Flaw",
    "The Ghost",
    "Lie they Believe",
    "Truth they'll learn",
)

# Terms that belong exclusively to the memoir real-people handler
MEMOIR_ONLY_TERMS = (
    "consent_status",
    "anonymization",
    "real_name",
    "person_category",
)

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
        assert fm["name"] == "character-creator"
        assert fm["model"] == "claude-opus-4-7"
        assert fm["user-invocable"] == "true"

    def test_memoir_frontmatter_correct(self) -> None:
        fm = _read_frontmatter(SKILL_MEMOIR)
        assert fm["name"] == "character-creator-memoir"
        assert fm["model"] == "claude-opus-4-7"
        assert fm["user-invocable"] == "true"


# ---------------------------------------------------------------------------
# Routing — each skill refuses the other category
# ---------------------------------------------------------------------------


class TestCrossRouting:
    def test_fiction_refuses_memoir_and_routes(self) -> None:
        body = _read_body(SKILL_FICTION)
        assert "/storyforge:character-creator-memoir" in body, (
            "Fiction skill must route memoir books to character-creator-memoir"
        )
        assert "book_category" in body
        assert "memoir" in body

    def test_memoir_refuses_fiction_and_routes(self) -> None:
        body = _read_body(SKILL_MEMOIR)
        assert "/storyforge:character-creator" in body, (
            "Memoir skill must route fiction books to character-creator"
        )
        assert "book_category" in body


# ---------------------------------------------------------------------------
# Catalog isolation — no fiction workflow in memoir, no memoir workflow in fiction
# ---------------------------------------------------------------------------


class TestCatalogIsolation:
    @pytest.mark.parametrize("term", FICTION_ONLY_TERMS)
    def test_memoir_skill_does_not_carry_fiction_workflow(self, term: str) -> None:
        body = _read_body(SKILL_MEMOIR)
        # Memoir skill may mention fiction terms only in the routing-out clause.
        hits = body.count(term)
        assert hits <= 1, (
            f"Memoir skill mentions fiction term {term!r} {hits} times — "
            f"fiction workflow content is leaking. Allowed: only the routing-out clause."
        )

    @pytest.mark.parametrize("term", MEMOIR_ONLY_TERMS)
    def test_fiction_skill_does_not_carry_memoir_workflow(self, term: str) -> None:
        body = _read_body(SKILL_FICTION)
        # Fiction skill may mention memoir-only terms only in the routing-out clause.
        hits = body.count(term)
        assert hits <= 1, (
            f"Fiction skill mentions memoir term {term!r} {hits} times — "
            f"memoir workflow content is leaking. Allowed: only the routing-out clause."
        )


# ---------------------------------------------------------------------------
# Plugin-root routing table is consistent
# ---------------------------------------------------------------------------


class TestRoutingTable:
    def test_claudemd_mentions_both_skills(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "/storyforge:character-creator" in text
        assert "/storyforge:character-creator-memoir" in text

    def test_routing_table_distinguishes_fiction_vs_memoir(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        fiction_row = re.search(
            r"^\|[^|]*fiction[^|]*\|\s*`?/storyforge:character-creator`?\s*\|",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        memoir_row = re.search(
            r"^\|[^|]*memoir[^|]*\|\s*`?/storyforge:character-creator-memoir`?\s*\|",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        assert fiction_row, "CLAUDE.md routing table missing fiction character row"
        assert memoir_row, "CLAUDE.md routing table missing memoir character row"
