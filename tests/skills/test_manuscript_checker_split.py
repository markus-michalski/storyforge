"""Static smoketest for the manuscript-checker / manuscript-checker-memoir split (Issue #138).

Asserts that:
- Both skill files exist with the right frontmatter (name, model, user-invocable).
- The fiction skill refuses memoir books and routes to manuscript-checker-memoir.
- The memoir skill refuses fiction books and routes to manuscript-checker.
- The memoir-only finding categories (anonymization_leak, tidy_lesson_ending,
  reflective_platitude, timeline_ambiguity, real_people_consistency) do not
  leak into the fiction skill, and the fiction-only plot_hole category does
  not leak into the memoir skill.
- The plugin-root CLAUDE.md routing table mentions both skills.

Does not cover the underlying scanner module (tools/analysis/manuscript/) —
that's shared, category-aware, and unchanged by this split; only the two
SKILL.md prompts are in scope here (see #138's "Out of scope" note).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_FICTION = PLUGIN_ROOT / "skills" / "manuscript-checker" / "SKILL.md"
SKILL_MEMOIR = PLUGIN_ROOT / "skills" / "manuscript-checker-memoir" / "SKILL.md"
CLAUDEMD = PLUGIN_ROOT / "CLAUDE.md"

MEMOIR_ONLY_CATEGORIES = (
    "anonymization_leak",
    "tidy_lesson_ending",
    "reflective_platitude",
    "timeline_ambiguity",
    "real_people_consistency",
)

# plot_hole is NOT fiction-only: tools/analysis/plot_logic.py's
# detect_causality_inversion() runs unconditionally for both categories —
# only its chekhov_gun sibling is fiction-gated. Both split files must
# therefore document plot_hole (verified against tools/analysis/manuscript/
# __init__.py, which calls _scan_plot_holes() unconditionally, before the
# book_category branch).
FICTION_ONLY_CATEGORIES: tuple[str, ...] = ()

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
        assert fm["name"] == "manuscript-checker"
        assert fm["model"] == "claude-opus-5"
        assert fm["user-invocable"] == "true"

    def test_memoir_frontmatter_correct(self) -> None:
        fm = _read_frontmatter(SKILL_MEMOIR)
        assert fm["name"] == "manuscript-checker-memoir"
        assert fm["model"] == "claude-opus-5"
        assert fm["user-invocable"] == "true"


# ---------------------------------------------------------------------------
# Routing — each skill refuses the other category
# ---------------------------------------------------------------------------


class TestCrossRouting:
    def test_fiction_refuses_memoir_and_routes(self) -> None:
        body = _read_body(SKILL_FICTION)
        assert "/storyforge:manuscript-checker-memoir" in body, (
            "Fiction skill must route memoir books to manuscript-checker-memoir"
        )
        assert "book_category" in body
        assert "memoir" in body  # at least mentioned in the routing-out clause

    def test_memoir_refuses_fiction_and_routes(self) -> None:
        body = _read_body(SKILL_MEMOIR)
        # Must mention the fiction skill by name, as a distinct token (not
        # merely as a substring of its own "manuscript-checker-memoir" name).
        assert re.search(r"/storyforge:manuscript-checker(?!-memoir)", body), (
            "Memoir skill must route fiction books to manuscript-checker"
        )
        assert "book_category" in body


# ---------------------------------------------------------------------------
# Shared categories — plot_hole applies to both (causality_inversion is not
# memoir-gated; only its chekhov_gun sibling is)
# ---------------------------------------------------------------------------


class TestSharedCategories:
    def test_fiction_skill_documents_plot_hole(self) -> None:
        assert "plot_hole" in _read_body(SKILL_FICTION)

    def test_memoir_skill_documents_plot_hole(self) -> None:
        assert "plot_hole" in _read_body(SKILL_MEMOIR)


# ---------------------------------------------------------------------------
# Catalog isolation — no memoir categories in fiction
# ---------------------------------------------------------------------------


class TestCatalogIsolation:
    @pytest.mark.parametrize("category", MEMOIR_ONLY_CATEGORIES)
    def test_fiction_skill_does_not_carry_memoir_categories(self, category: str) -> None:
        body = _read_body(SKILL_FICTION)
        assert category not in body, (
            f"Fiction skill mentions memoir-only category {category!r} — memoir workflow content is leaking."
        )

    @pytest.mark.parametrize("category", FICTION_ONLY_CATEGORIES)
    def test_memoir_skill_does_not_carry_fiction_categories(self, category: str) -> None:
        body = _read_body(SKILL_MEMOIR)
        assert category not in body, (
            f"Memoir skill mentions fiction-only category {category!r} — fiction workflow content is leaking."
        )


# ---------------------------------------------------------------------------
# Plugin-root routing table is consistent
# ---------------------------------------------------------------------------


class TestRoutingTable:
    def test_claudemd_mentions_both_skills(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "/storyforge:manuscript-checker" in text
        assert "/storyforge:manuscript-checker-memoir" in text

    def test_routing_table_distinguishes_fiction_vs_memoir(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        fiction_row = re.search(
            r"^\|\s*\"Manuscript check\"[^|]*fiction[^|]*\|\s*`?/storyforge:manuscript-checker`?\s*\|",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        memoir_row = re.search(
            r"^\|\s*\"Manuscript check[^|]*memoir[^|]*\|\s*`?/storyforge:manuscript-checker-memoir`?\s*\|",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        assert fiction_row, "CLAUDE.md routing table missing fiction manuscript-check row"
        assert memoir_row, "CLAUDE.md routing table missing memoir manuscript-check row"
