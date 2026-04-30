"""Tests for editing existing rules in a book's CLAUDE.md.

Issue #145 — `update_book_rule`, `list_book_rules`. The editor operates only
inside the ``<!-- RULES:START --> ... <!-- RULES:END -->`` block; static rules
above the marker are surfaced via list_rules but cannot be edited.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.claudemd.manager import init_claudemd
from tools.claudemd.rules_editor import (
    AmbiguousMatchError,
    DisagreeingResolutionError,
    MarkersNotFoundError,
    list_rules,
    update_rule,
)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def book_config(tmp_path: Path) -> dict:
    content_root = tmp_path / "books"
    book_dir = content_root / "projects" / "my-book"
    book_dir.mkdir(parents=True)
    (book_dir / "README.md").write_text("# My Book\n", encoding="utf-8")
    return {"paths": {"content_root": str(content_root)}}


def _seed_rules(book_config: dict, rules: list[str]) -> Path:
    """Initialize CLAUDE.md and seed the RULES block with raw bullets."""
    from tools.claudemd.manager import resolve_claudemd_path

    init_claudemd(book_config, PLUGIN_ROOT, "my-book")
    path = resolve_claudemd_path(book_config, "my-book")
    content = path.read_text(encoding="utf-8")

    bullets = "\n".join(f"- {r}" for r in rules)
    new_content = content.replace(
        "<!-- RULES:START -->\n<!-- RULES:END -->",
        f"<!-- RULES:START -->\n{bullets}\n<!-- RULES:END -->",
    )
    path.write_text(new_content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# list_rules
# ---------------------------------------------------------------------------


class TestListRules:
    def test_empty_block(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        assert list_rules(book_config, "my-book") == []

    def test_single_rule(self, book_config):
        _seed_rules(book_config, ["**Rule 1** — avoid passive voice"])
        rules = list_rules(book_config, "my-book")
        assert len(rules) == 1
        assert rules[0].index == 0
        assert rules[0].title == "Rule 1"
        assert "avoid passive voice" in rules[0].raw_text

    def test_multiple_rules(self, book_config):
        _seed_rules(
            book_config,
            [
                "**Rule 1** — avoid `clocked`",
                "**Rule 2** — limit adverbs",
                "**Rule 3** — never use `began to`",
            ],
        )
        rules = list_rules(book_config, "my-book")
        assert len(rules) == 3
        assert [r.index for r in rules] == [0, 1, 2]
        assert [r.title for r in rules] == ["Rule 1", "Rule 2", "Rule 3"]

    def test_rule_without_bold_title(self, book_config):
        _seed_rules(book_config, ["avoid passive voice in dialog"])
        rules = list_rules(book_config, "my-book")
        assert len(rules) == 1
        # Falls back to truncated body as title.
        assert "avoid passive voice" in rules[0].title

    def test_has_regex_and_has_literals_flags(self, book_config):
        _seed_rules(
            book_config,
            [
                "**R1** — avoid `clocked` as a verb",  # literal
                r"**R2** — avoid `\bsuddenly\b` patterns",  # regex (\b)
                "**R3** — narrative discipline only",  # neither
            ],
        )
        rules = list_rules(book_config, "my-book")
        assert rules[0].has_literals is True
        assert rules[0].has_regex is False
        assert rules[1].has_regex is True
        assert rules[2].has_literals is False
        assert rules[2].has_regex is False

    def test_raises_if_markers_missing(self, book_config, tmp_path):
        from tools.claudemd.manager import resolve_claudemd_path

        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        path = resolve_claudemd_path(book_config, "my-book")
        # Strip the markers entirely.
        content = path.read_text(encoding="utf-8")
        content = content.replace("<!-- RULES:START -->\n", "")
        content = content.replace("<!-- RULES:END -->", "")
        path.write_text(content, encoding="utf-8")

        with pytest.raises(MarkersNotFoundError):
            list_rules(book_config, "my-book")


# ---------------------------------------------------------------------------
# update_rule — by index
# ---------------------------------------------------------------------------


class TestUpdateByIndex:
    def test_replaces_rule_at_index(self, book_config):
        _seed_rules(
            book_config,
            ["**R1** — first", "**R2** — second", "**R3** — third"],
        )
        result = update_rule(
            book_config, "my-book",
            rule_index=1, new_text="**R2** — replacement",
        )
        assert result["found"] is True
        assert result["changed"] is True
        assert result["rule_index"] == 1
        assert "**R2** — second" == result["old_text"]
        rules = list_rules(book_config, "my-book")
        assert rules[1].raw_text == "**R2** — replacement"
        # Other rules untouched.
        assert rules[0].raw_text == "**R1** — first"
        assert rules[2].raw_text == "**R3** — third"

    def test_index_out_of_range(self, book_config):
        _seed_rules(book_config, ["**R1** — only"])
        result = update_rule(
            book_config, "my-book",
            rule_index=5, new_text="should fail",
        )
        assert result["found"] is False

    def test_negative_index_rejected(self, book_config):
        _seed_rules(book_config, ["**R1** — only"])
        with pytest.raises(ValueError):
            update_rule(
                book_config, "my-book",
                rule_index=-1, new_text="x",
            )


# ---------------------------------------------------------------------------
# update_rule — by match
# ---------------------------------------------------------------------------


class TestUpdateByMatch:
    def test_match_against_bold_title(self, book_config):
        _seed_rules(
            book_config,
            ["**Adverbs** — limit them", "**Cliches** — kill on sight"],
        )
        result = update_rule(
            book_config, "my-book",
            rule_match="Adverbs", new_text="**Adverbs** — limit to 1 per scene",
        )
        assert result["found"] is True
        assert result["rule_index"] == 0
        rules = list_rules(book_config, "my-book")
        assert "1 per scene" in rules[0].raw_text

    def test_match_substring_case_insensitive(self, book_config):
        _seed_rules(book_config, ["**Adverbs** — limit them"])
        result = update_rule(
            book_config, "my-book",
            rule_match="adverbs", new_text="**Adverbs** — none",
        )
        assert result["found"] is True

    def test_match_falls_back_to_body(self, book_config):
        _seed_rules(book_config, ["no bold title here, watch for clocked usage"])
        result = update_rule(
            book_config, "my-book",
            rule_match="clocked", new_text="rewritten",
        )
        assert result["found"] is True

    def test_ambiguous_match_raises(self, book_config):
        _seed_rules(
            book_config,
            ["**Adverbs Hard** — strict", "**Adverbs Soft** — flexible"],
        )
        with pytest.raises(AmbiguousMatchError) as exc:
            update_rule(
                book_config, "my-book",
                rule_match="Adverbs", new_text="x",
            )
        assert "Adverbs Hard" in str(exc.value)
        assert "Adverbs Soft" in str(exc.value)

    def test_no_match_returns_found_false(self, book_config):
        _seed_rules(book_config, ["**R1** — first"])
        result = update_rule(
            book_config, "my-book",
            rule_match="nonexistent", new_text="x",
        )
        assert result["found"] is False


# ---------------------------------------------------------------------------
# update_rule — by both (agree / disagree)
# ---------------------------------------------------------------------------


class TestUpdateByBoth:
    def test_both_agree_succeeds(self, book_config):
        _seed_rules(
            book_config,
            ["**R1** — first", "**R2** — second", "**R3** — third"],
        )
        result = update_rule(
            book_config, "my-book",
            rule_index=1, rule_match="R2",
            new_text="**R2** — replaced",
        )
        assert result["found"] is True
        assert result["rule_index"] == 1

    def test_both_disagree_raises(self, book_config):
        _seed_rules(
            book_config,
            ["**R1** — first", "**R2** — second"],
        )
        with pytest.raises(DisagreeingResolutionError):
            update_rule(
                book_config, "my-book",
                rule_index=0, rule_match="R2", new_text="x",
            )

    def test_neither_provided_raises(self, book_config):
        _seed_rules(book_config, ["**R1** — first"])
        with pytest.raises(ValueError):
            update_rule(book_config, "my-book", new_text="x")


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDeleteRule:
    def test_delete_by_index(self, book_config):
        _seed_rules(
            book_config,
            ["**R1** — first", "**R2** — second", "**R3** — third"],
        )
        result = update_rule(book_config, "my-book", rule_index=1, delete=True)
        assert result["found"] is True
        assert result["changed"] is True
        assert result["new_text"] == ""
        rules = list_rules(book_config, "my-book")
        assert len(rules) == 2
        assert rules[0].title == "R1"
        assert rules[1].title == "R3"

    def test_delete_by_match(self, book_config):
        _seed_rules(
            book_config,
            ["**Keep** — always", "**Drop** — never"],
        )
        update_rule(book_config, "my-book", rule_match="Drop", delete=True)
        rules = list_rules(book_config, "my-book")
        assert len(rules) == 1
        assert rules[0].title == "Keep"

    def test_delete_with_new_text_rejected(self, book_config):
        _seed_rules(book_config, ["**R1** — first"])
        with pytest.raises(ValueError):
            update_rule(
                book_config, "my-book",
                rule_index=0, delete=True, new_text="x",
            )

    def test_delete_nonexistent_returns_found_false(self, book_config):
        _seed_rules(book_config, ["**R1** — first"])
        result = update_rule(
            book_config, "my-book",
            rule_match="ghost", delete=True,
        )
        assert result["found"] is False


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_same_text_twice_no_op(self, book_config):
        _seed_rules(book_config, ["**R1** — original"])
        update_rule(
            book_config, "my-book",
            rule_index=0, new_text="**R1** — updated",
        )
        result2 = update_rule(
            book_config, "my-book",
            rule_index=0, new_text="**R1** — updated",
        )
        assert result2["found"] is True
        assert result2["changed"] is False

    def test_empty_new_text_rejected(self, book_config):
        _seed_rules(book_config, ["**R1** — first"])
        with pytest.raises(ValueError):
            update_rule(
                book_config, "my-book",
                rule_index=0, new_text="   ",
            )


# ---------------------------------------------------------------------------
# Marker preservation
# ---------------------------------------------------------------------------


class TestMarkerPreservation:
    def test_markers_unchanged_after_update(self, book_config):
        path = _seed_rules(book_config, ["**R1** — first", "**R2** — second"])
        update_rule(
            book_config, "my-book",
            rule_index=0, new_text="**R1** — replaced",
        )
        content = path.read_text(encoding="utf-8")
        assert content.count("<!-- RULES:START -->") == 1
        assert content.count("<!-- RULES:END -->") == 1
        # Other markers also intact.
        assert "<!-- WORKFLOW:START -->" in content
        assert "<!-- CALLBACKS:END -->" in content

    def test_markers_unchanged_after_delete(self, book_config):
        path = _seed_rules(book_config, ["**R1** — first"])
        update_rule(book_config, "my-book", rule_index=0, delete=True)
        content = path.read_text(encoding="utf-8")
        assert "<!-- RULES:START -->" in content
        assert "<!-- RULES:END -->" in content


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_no_markers_raises_on_update(self, book_config):
        from tools.claudemd.manager import resolve_claudemd_path

        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        path = resolve_claudemd_path(book_config, "my-book")
        content = path.read_text(encoding="utf-8")
        content = content.replace("<!-- RULES:START -->\n", "")
        content = content.replace("<!-- RULES:END -->", "")
        path.write_text(content, encoding="utf-8")

        with pytest.raises(MarkersNotFoundError):
            update_rule(
                book_config, "my-book",
                rule_index=0, new_text="x",
            )

    def test_static_rules_above_marker_invisible_to_editor(self, book_config):
        """Rules outside the RULES:START/END block are not user-managed."""
        from tools.claudemd.manager import resolve_claudemd_path

        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        path = resolve_claudemd_path(book_config, "my-book")
        content = path.read_text(encoding="utf-8")
        # Insert a static bullet ABOVE the markers.
        content = content.replace(
            "<!-- RULES:START -->",
            "- **Static** — unmanaged static rule\n<!-- RULES:START -->",
        )
        path.write_text(content, encoding="utf-8")

        rules = list_rules(book_config, "my-book")
        # Editor only sees managed (in-marker) rules.
        assert all("Static" not in r.title for r in rules)

    def test_multiline_rule_body_preserved(self, book_config):
        """A bullet that wraps across multiple lines is treated as one rule."""
        from tools.claudemd.manager import resolve_claudemd_path

        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        path = resolve_claudemd_path(book_config, "my-book")
        content = path.read_text(encoding="utf-8")
        # Manually inject a multi-line bullet block.
        block = (
            "<!-- RULES:START -->\n"
            "- **R1** — first line of rule\n"
            "  continuation on second line\n"
            "  and third line\n"
            "- **R2** — second rule\n"
            "<!-- RULES:END -->"
        )
        content = content.replace(
            "<!-- RULES:START -->\n<!-- RULES:END -->", block
        )
        path.write_text(content, encoding="utf-8")

        rules = list_rules(book_config, "my-book")
        assert len(rules) == 2
        assert "continuation on second line" in rules[0].raw_text
        assert "and third line" in rules[0].raw_text

    def test_book_not_found(self, book_config):
        with pytest.raises(FileNotFoundError):
            update_rule(
                book_config, "nonexistent",
                rule_index=0, new_text="x",
            )
