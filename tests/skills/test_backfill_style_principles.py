"""Structural smoketest for backfill-style-principles/SKILL.md (Issue #381).

This skill had no dedicated structural coverage before #381 — the undefined
`{title}` template placeholder (Step 5.1 read the file via
`analysis-{title}.md`, but only `book_slug` is ever derived, in Step 4)
shipped unnoticed. Mirrors the lightweight frontmatter + structural-check
pattern used by tests/skills/test_chapter_writer_split.py for its sibling
skills, scoped to the one regression class that actually bit this file:
undefined `{title}` placeholders where `{book_slug}` is the real variable.
"""

from __future__ import annotations

import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_PATH = PLUGIN_ROOT / "skills" / "backfill-style-principles" / "SKILL.md"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _read_frontmatter() -> dict[str, str]:
    text = SKILL_PATH.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    assert m, f"{SKILL_PATH} missing frontmatter"
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm


def _read_body() -> str:
    text = SKILL_PATH.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    return text[m.end() :] if m else text


class TestSkillFile:
    def test_skill_exists(self) -> None:
        assert SKILL_PATH.is_file()

    def test_frontmatter_correct(self) -> None:
        fm = _read_frontmatter()
        assert fm["name"] == "backfill-style-principles"
        assert fm["model"] == "claude-opus-4-8"
        assert fm["user-invocable"] == "true"


class TestNoUndefinedTitlePlaceholder:
    """Regression guard for Issue #381.

    Step 4 derives `book_slug` from each analysis filename — that's the
    only per-file identifier this skill's flow ever defines. `{title}` is
    never bound to anything and must not reappear as a template token.
    """

    def test_body_has_no_title_placeholder(self) -> None:
        body = _read_body()
        assert "{title}" not in body, (
            "backfill-style-principles/SKILL.md references an undefined "
            "{title} placeholder — only {book_slug} is derived (Step 4). "
            "See Issue #381."
        )

    def test_body_uses_book_slug_for_per_file_reporting(self) -> None:
        # Step 4 defines book_slug; the per-file report lines (Step 5.x,
        # Step 6) must reference it, not a phantom {title} variable.
        body = _read_body()
        assert body.count("{book_slug}") >= 5, (
            "Expected {book_slug} to be the per-file identifier used "
            "throughout Steps 5.1/5.2/5.4/5.5 — count dropped below the "
            "known-good baseline, check for a reintroduced {title} bug."
        )
