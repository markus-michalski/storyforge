"""Tests for ``tools.author.discovery_writer``.

Covers ``remove_book_rule_after_promotion`` — the cleanup path after a rule
has been promoted from a book CLAUDE.md to the author profile.

Note: The old ``write_discovery`` Markdown write path was removed in Phase 5
(#283). Writing Discoveries now go through the ``write_author_discovery`` MCP
tool which persists to the author_discoveries SQLite table (Issue #281).
"""

from __future__ import annotations

from pathlib import Path

from tools.author.discovery_writer import remove_book_rule_after_promotion


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
