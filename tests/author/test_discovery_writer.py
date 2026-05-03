"""Tests for ``tools.author.discovery_writer`` (Issue #151).

Two write paths:

- ``write_discovery`` — append an entry to ``profile.md`` under
  ``## Writing Discoveries`` → matching sub-section. Idempotent: if the entry
  already exists, append an additional origin tag instead of duplicating.
- ``write_banned_phrase_via_vocabulary`` — a thin wrapper around
  ``tools.rule_writer.write_author_rule`` so the harvest skill has a single
  call surface for all promotions.

Plus the cleanup half:

- ``remove_book_rule_after_promotion`` — removes a rule from a book CLAUDE.md
  once it's been promoted, optionally leaving a "promoted" note bullet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.author.discovery_writer import (
    AlreadyPresent,
    SectionMissing,
    write_discovery,
)


_PROFILE_WITH_DISCOVERIES = """\
---
name: "Ethan Cole"
slug: "ethan-cole"
primary_genres: ["dark-fantasy"]
narrative_voice: "third-limited"
tense: "past"
tone: ["brooding"]
---

# Ethan Cole

## Writing Style

Dark and lean.

## Writing Discoveries

*Insights that emerged across books.*

### Recurring Tics

_Frei._

### Style Principles

_Frei._

### Don'ts (beyond banned phrases)

_Frei._
"""


_PROFILE_WITHOUT_DISCOVERIES = """\
---
name: "Ethan Cole"
slug: "ethan-cole"
---

# Ethan Cole

## Writing Style

Dark.
"""


@pytest.fixture
def author_dir(tmp_path: Path) -> Path:
    d = tmp_path / "ethan-cole"
    d.mkdir()
    (d / "profile.md").write_text(_PROFILE_WITH_DISCOVERIES, encoding="utf-8")
    return d


# ---------------------------------------------------------------------------
# write_discovery — recurring_tics
# ---------------------------------------------------------------------------


class TestWriteDiscovery:
    def test_appends_recurring_tic_with_origin_tag(self, author_dir: Path):
        result = write_discovery(
            profile_path=author_dir / "profile.md",
            section="recurring_tics",
            text='**"math" as analytical metaphor** — cut on sight unless POV demands.',
            book_slug="firelight",
            year_month="2026-05",
        )
        assert result.written is True

        content = (author_dir / "profile.md").read_text(encoding="utf-8")
        assert '**"math" as analytical metaphor**' in content
        assert "_(emerged from firelight, 2026-05)_" in content
        # Placeholder must be removed when first real entry lands.
        recurring_section = _section_body(content, "Recurring Tics")
        assert "_Frei._" not in recurring_section

    def test_appends_to_style_principles(self, author_dir: Path):
        write_discovery(
            profile_path=author_dir / "profile.md",
            section="style_principles",
            text="Fast dialog without tags works up to ~8 turns.",
            book_slug="firelight",
            year_month="2026-05",
        )
        content = (author_dir / "profile.md").read_text(encoding="utf-8")
        principles = _section_body(content, "Style Principles")
        assert "Fast dialog" in principles
        # Recurring Tics section must NOT be touched.
        assert "_Frei._" in _section_body(content, "Recurring Tics")

    def test_appends_to_donts(self, author_dir: Path):
        write_discovery(
            profile_path=author_dir / "profile.md",
            section="donts",
            text="Never start a chapter with weather.",
            book_slug="firelight",
            year_month="2026-05",
        )
        content = (author_dir / "profile.md").read_text(encoding="utf-8")
        assert "weather" in _section_body(content, "Don'ts")

    def test_idempotent_when_entry_already_present_returns_already(self, author_dir: Path):
        write_discovery(
            profile_path=author_dir / "profile.md",
            section="recurring_tics",
            text='**"math" as analytical metaphor** — cut on sight.',
            book_slug="firelight",
            year_month="2026-05",
        )
        result = write_discovery(
            profile_path=author_dir / "profile.md",
            section="recurring_tics",
            text='**"math" as analytical metaphor** — cut on sight.',
            book_slug="firelight",
            year_month="2026-05",
        )
        assert isinstance(result, AlreadyPresent)
        # No duplicate — only one origin tag for the same book.
        content = (author_dir / "profile.md").read_text(encoding="utf-8")
        assert content.count("_(emerged from firelight, 2026-05)_") == 1

    def test_recurring_in_second_book_appends_extra_origin_tag(self, author_dir: Path):
        """When a discovery resurfaces in a new book, append a second origin tag."""
        write_discovery(
            profile_path=author_dir / "profile.md",
            section="recurring_tics",
            text='**"math" as analytical metaphor** — cut on sight.',
            book_slug="firelight",
            year_month="2026-05",
        )
        result = write_discovery(
            profile_path=author_dir / "profile.md",
            section="recurring_tics",
            text='**"math" as analytical metaphor** — cut on sight.',
            book_slug="emberkeep",
            year_month="2026-09",
        )
        # Second write to same text but new book → not "AlreadyPresent" because
        # the new origin tag IS new information.
        assert result.written is True
        content = (author_dir / "profile.md").read_text(encoding="utf-8")
        assert "_(emerged from firelight, 2026-05)_" in content
        assert "_(emerged from emberkeep, 2026-09)_" in content
        # Still only ONE bullet — both tags stacked on the same entry.
        recurring_section = _section_body(content, "Recurring Tics")
        bullet_count = sum(1 for line in recurring_section.splitlines() if line.strip().startswith("- "))
        assert bullet_count == 1

    def test_rejects_unknown_section(self, author_dir: Path):
        with pytest.raises(ValueError):
            write_discovery(
                profile_path=author_dir / "profile.md",
                section="unknown_bucket",
                text="x",
                book_slug="firelight",
                year_month="2026-05",
            )

    def test_raises_when_writing_discoveries_section_missing(self, tmp_path: Path):
        legacy = tmp_path / "old-author"
        legacy.mkdir()
        (legacy / "profile.md").write_text(_PROFILE_WITHOUT_DISCOVERIES, encoding="utf-8")

        with pytest.raises(SectionMissing):
            write_discovery(
                profile_path=legacy / "profile.md",
                section="recurring_tics",
                text="x",
                book_slug="firelight",
                year_month="2026-05",
            )

    def test_creates_subsection_if_missing(self, tmp_path: Path):
        """A profile with `## Writing Discoveries` but no `### Recurring Tics`
        sub-heading should auto-create the sub-heading + bullet."""
        d = tmp_path / "ethan-cole"
        d.mkdir()
        (d / "profile.md").write_text(
            "---\nname: x\n---\n\n# x\n\n## Writing Discoveries\n\n_Frei._\n",
            encoding="utf-8",
        )
        write_discovery(
            profile_path=d / "profile.md",
            section="recurring_tics",
            text="**foo** — bar.",
            book_slug="firelight",
            year_month="2026-05",
        )
        content = (d / "profile.md").read_text(encoding="utf-8")
        assert "### Recurring Tics" in content
        assert "**foo**" in content


# ---------------------------------------------------------------------------
# remove_book_rule_after_promotion
# ---------------------------------------------------------------------------


_BOOK_CLAUDEMD = """\
# Firelight — CLAUDE.md

## Rules

<!-- RULES:START -->
- **Math metaphor** — Avoid `math` for analytical thinking.
- **Pattern** — Avoid `[Character] moved to [location]`.
<!-- RULES:END -->
"""


class TestRemoveBookRuleAfterPromotion:
    """Cleanup half: when the user accepts a promotion, the original rule
    should optionally disappear from the book CLAUDE.md."""

    def test_removes_matched_rule(self, tmp_path: Path):
        from tools.author.discovery_writer import remove_book_rule_after_promotion

        book_dir = tmp_path / "firelight"
        book_dir.mkdir()
        (book_dir / "CLAUDE.md").write_text(_BOOK_CLAUDEMD, encoding="utf-8")

        result = remove_book_rule_after_promotion(
            claudemd_path=book_dir / "CLAUDE.md",
            rule_index=0,
        )
        assert result.removed is True

        content = (book_dir / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Math metaphor" not in content
        # Other rule must remain intact.
        assert "Pattern" in content

    def test_keeps_rule_with_promoted_note(self, tmp_path: Path):
        from tools.author.discovery_writer import remove_book_rule_after_promotion

        book_dir = tmp_path / "firelight"
        book_dir.mkdir()
        (book_dir / "CLAUDE.md").write_text(_BOOK_CLAUDEMD, encoding="utf-8")

        result = remove_book_rule_after_promotion(
            claudemd_path=book_dir / "CLAUDE.md",
            rule_index=0,
            mode="annotate",
        )
        assert result.removed is False
        assert result.annotated is True

        content = (book_dir / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Math metaphor" in content
        assert "promoted to author profile" in content.lower()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _section_body(content: str, heading: str) -> str:
    """Return the body text under `### {heading}` up to the next heading."""
    import re
    pat = re.compile(
        rf"^###\s+{re.escape(heading)}.*?$(.*?)(?=^###?\s|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    m = pat.search(content)
    return m.group(1) if m else ""
