"""Static smoketest for the chapter-reviewer / chapter-reviewer-memoir split (Issue #176).

Asserts that:
- Both skill files exist with the right frontmatter (name, model, user-invocable).
- The fiction skill dispatches memoir books to chapter-reviewer-memoir.
- The memoir skill refuses fiction books and routes to chapter-reviewer.
- Memoir-only checklist terms (consent gate, people-log, memoir anti-AI points,
  dialog-reconstruction honesty) do not leak into the fiction skill.
- Fiction-only terms (Travel Matrix, canon-log, world-rule consistency) do not
  leak into the memoir skill.
- The plugin-root CLAUDE.md routing table mentions both skills.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_FICTION = PLUGIN_ROOT / "skills" / "chapter-reviewer" / "SKILL.md"
SKILL_MEMOIR = PLUGIN_ROOT / "skills" / "chapter-reviewer-memoir" / "SKILL.md"
CLAUDEMD = PLUGIN_ROOT / "CLAUDE.md"

# Terms that belong only in the memoir skill
MEMOIR_ONLY_TERMS = (
    "memoir-anti-ai-patterns",
    "people-log",
    "consent_status_warnings",
    "dialog reconstruction honesty",
    "Therapeutic reframe",
    "Tidy lesson ending",
    "real-world plausibility",
)

# Fiction-only terms and their allowed occurrence count in the memoir skill.
# Memoir may legitimately document exclusions ("no X"), so a small count is allowed.
FICTION_ONLY_TERMS: dict[str, int] = {
    "Travel Matrix": 2,   # Step 0 note + point 18 exclusion doc ("No Travel Matrix")
    "canon-log": 2,       # intro note + "use people-log, not canon-log" cross-reference
    "world-rule consistency": 1,  # point 20e skip note ("fiction-only")
}

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
    return text[m.end():] if m else text


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
        assert fm["name"] == "chapter-reviewer"
        assert fm["model"] == "claude-opus-4-7"
        assert fm["user-invocable"] == "true"

    def test_memoir_frontmatter_correct(self) -> None:
        fm = _read_frontmatter(SKILL_MEMOIR)
        assert fm["name"] == "chapter-reviewer-memoir"
        assert fm["model"] == "claude-opus-4-7"
        assert fm["user-invocable"] == "true"


# ---------------------------------------------------------------------------
# Routing — each skill dispatches the other category
# ---------------------------------------------------------------------------


class TestCrossRouting:
    def test_fiction_dispatches_memoir(self) -> None:
        body = _read_body(SKILL_FICTION)
        assert "/storyforge:chapter-reviewer-memoir" in body, (
            "Fiction skill must dispatch memoir books to chapter-reviewer-memoir"
        )
        assert "book_category" in body

    def test_memoir_routes_fiction(self) -> None:
        body = _read_body(SKILL_MEMOIR)
        assert "/storyforge:chapter-reviewer" in body, (
            "Memoir skill must route fiction books to chapter-reviewer"
        )
        assert "book_category" in body


# ---------------------------------------------------------------------------
# Catalog isolation
# ---------------------------------------------------------------------------


class TestCatalogIsolation:
    @pytest.mark.parametrize("term", MEMOIR_ONLY_TERMS)
    def test_fiction_skill_does_not_carry_memoir_checklist_terms(
        self, term: str
    ) -> None:
        body = _read_body(SKILL_FICTION)
        hits = body.count(term)
        assert hits <= 1, (
            f"Fiction skill mentions memoir-only term {term!r} {hits} times — "
            f"memoir checklist content is leaking. Allowed: routing-out clause only."
        )

    @pytest.mark.parametrize("term,max_allowed", FICTION_ONLY_TERMS.items())
    def test_memoir_skill_does_not_carry_fiction_checklist_terms(
        self, term: str, max_allowed: int
    ) -> None:
        body = _read_body(SKILL_MEMOIR)
        hits = body.count(term)
        assert hits <= max_allowed, (
            f"Memoir skill mentions fiction-only term {term!r} {hits} times "
            f"(allowed: ≤{max_allowed}) — fiction workflow content is leaking."
        )


# ---------------------------------------------------------------------------
# Plugin-root routing table is consistent
# ---------------------------------------------------------------------------


class TestRoutingTable:
    def test_claudemd_mentions_both_skills(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "/storyforge:chapter-reviewer" in text
        assert "/storyforge:chapter-reviewer-memoir" in text

    def test_routing_table_distinguishes_fiction_vs_memoir(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        fiction_row = re.search(
            r"^\|[^|]*fiction[^|]*\|\s*`?/storyforge:chapter-reviewer`?\s*\|",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        memoir_row = re.search(
            r"^\|[^|]*memoir[^|]*\|\s*`?/storyforge:chapter-reviewer-memoir`?\s*\|",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        assert fiction_row, "CLAUDE.md routing table missing fiction chapter-reviewer row"
        assert memoir_row, "CLAUDE.md routing table missing memoir chapter-reviewer-memoir row"
