"""Tests for the MCP tool sweep (Issue #175, cleaned up in Issue #236).

Verifies that CLAUDE.md documents the user-callable utility tools.
Deprecated tools (get_chapter, get_character, get_series,
update_book_claudemd_facts) were removed in Issue #236.
"""

from __future__ import annotations

from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
CLAUDEMD = PLUGIN_ROOT / "CLAUDE.md"


class TestUserCallableUtilitiesDocumented:
    def test_claudemd_has_user_callable_section(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "User-Callable MCP Tools" in text or "user-callable" in text.lower(), (
            "CLAUDE.md must document user-callable MCP tools"
        )

    def test_list_craft_references_documented(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "list_craft_references" in text

    def test_validate_timeline_consistency_documented(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "validate_timeline_consistency" in text

    def test_get_review_handle_config_documented(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "get_review_handle_config" in text

    def test_rebuild_state_documented(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "rebuild_state" in text

    def test_get_current_story_anchor_documented(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "get_current_story_anchor" in text

    def test_get_recent_chapter_timelines_documented(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "get_recent_chapter_timelines" in text

    def test_count_words_documented(self) -> None:
        text = CLAUDEMD.read_text(encoding="utf-8")
        assert "count_words" in text
