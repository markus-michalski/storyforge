"""Smoke test: structural drift detection for fiction/memoir skill pairs (Issue #238).

Parses the H2 section headers of each fiction+memoir pair, computes a
sequence-similarity ratio via difflib.SequenceMatcher, and emits a warning
(never a failure) when the pair diverges by more than 20%.

This catches accidental omissions after workflow changes while allowing
intentional memoir-specific sections (e.g. consent gates, memoir structures).
"""

from __future__ import annotations

import difflib
import re
import warnings
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"

SKILL_PAIRS = [
    ("chapter-writer", "chapter-writer-memoir"),
    ("chapter-reviewer", "chapter-reviewer-memoir"),
    ("plot-architect", "plot-architect-memoir"),
    ("character-creator", "character-creator-memoir"),
]

DRIFT_THRESHOLD = 0.20

FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
STEP_NUM_RE = re.compile(r"\b[Mm]?\d+[a-zA-Z]?\b")
DESCRIPTION_RE = re.compile(r"(\s+[—–]\s*.+|\s+[-]\s+.+)$")
PARENTHETICAL_RE = re.compile(r"\s*\([^)]*\)")
H2_RE = re.compile(r"^##\s+\S")


def _strip_frontmatter(text: str) -> str:
    m = FRONTMATTER_RE.match(text)
    return text[m.end() :] if m else text


def _normalize(header: str) -> str:
    """Reduce a header to its structural label for cross-pair comparison."""
    text = re.sub(r"^#{1,6}\s*", "", header)
    text = DESCRIPTION_RE.sub("", text)
    text = PARENTHETICAL_RE.sub("", text)
    text = STEP_NUM_RE.sub("N", text)
    return text.lower().strip()


def _extract_h2_headers(skill_name: str) -> list[str]:
    """Return all H2 (##) headers from a skill's SKILL.md, frontmatter stripped."""
    path = SKILLS_DIR / skill_name / "SKILL.md"
    if not path.is_file():
        pytest.skip(f"Skill file not found: {path}")
    body = _strip_frontmatter(path.read_text(encoding="utf-8"))
    return [line for line in body.splitlines() if H2_RE.match(line)]


def _similarity(a: list[str], b: list[str]) -> float:
    norm_a = [_normalize(h) for h in a]
    norm_b = [_normalize(h) for h in b]
    return difflib.SequenceMatcher(None, norm_a, norm_b).ratio()


class TestSkillPairFiles:
    """Both files in each pair must exist."""

    @pytest.mark.parametrize("skill", [s for pair in SKILL_PAIRS for s in pair])
    def test_skill_file_exists(self, skill: str) -> None:
        assert (SKILLS_DIR / skill / "SKILL.md").is_file(), \
            f"Skill missing: {skill}/SKILL.md"


class TestSkillPairDrift:
    """Structural parity: warns (never fails) when H2 sections diverge by >20%.

    Intentional memoir-specific sections are allowed. This test exists to
    catch accidental omissions when a workflow phase is added to the fiction
    variant but not propagated to the memoir variant (or vice versa).
    """

    @pytest.mark.parametrize("fiction,memoir", SKILL_PAIRS)
    def test_h2_structural_parity(self, fiction: str, memoir: str) -> None:
        fiction_headers = _extract_h2_headers(fiction)
        memoir_headers = _extract_h2_headers(memoir)

        ratio = _similarity(fiction_headers, memoir_headers)
        min_ratio = 1.0 - DRIFT_THRESHOLD

        if ratio < min_ratio:
            fiction_set = {_normalize(h) for h in fiction_headers}
            memoir_set = {_normalize(h) for h in memoir_headers}
            only_fiction = sorted(fiction_set - memoir_set)
            only_memoir = sorted(memoir_set - fiction_set)
            warnings.warn(
                f"Skill pair '{fiction}' / '{memoir}' H2 similarity {ratio:.0%} "
                f"< threshold {min_ratio:.0%}. "
                f"Only in fiction: {only_fiction}. "
                f"Only in memoir: {only_memoir}.",
                UserWarning,
                stacklevel=2,
            )
