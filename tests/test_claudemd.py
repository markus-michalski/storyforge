"""Tests for per-book CLAUDE.md management."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.claudemd.manager import (
    append_callback,
    append_rule,
    append_workflow,
    get_claudemd,
    init_claudemd,
    resolve_claudemd_path,
    update_book_facts,
)
from tools.claudemd.parser import (
    extract_prefixed_lines,
    parse_prefixed_entry,
)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def book_config(tmp_path: Path) -> dict:
    """Config with tmp_path as content_root and a pre-created book directory."""
    content_root = tmp_path / "books"
    book_dir = content_root / "projects" / "my-book"
    book_dir.mkdir(parents=True)
    # Book README so find_projects would recognize it.
    (book_dir / "README.md").write_text("# My Book\n", encoding="utf-8")
    return {"paths": {"content_root": str(content_root)}}


class TestParser:
    def test_regel_prefix_german(self):
        assert parse_prefixed_entry("Regel: sparsam mit Adverbien") == (
            "rule",
            "sparsam mit Adverbien",
        )

    def test_rule_prefix_english(self):
        assert parse_prefixed_entry("Rule: avoid passive voice") == (
            "rule",
            "avoid passive voice",
        )

    def test_workflow_prefix(self):
        assert parse_prefixed_entry("Workflow: scene-by-scene, not whole chapter") == (
            "workflow",
            "scene-by-scene, not whole chapter",
        )

    def test_callback_prefix(self):
        assert parse_prefixed_entry("Callback: Gary the cat") == (
            "callback",
            "Gary the cat",
        )

    def test_case_insensitive(self):
        assert parse_prefixed_entry("CALLBACK: thing") == ("callback", "thing")
        assert parse_prefixed_entry("callback: thing") == ("callback", "thing")

    def test_leading_whitespace(self):
        assert parse_prefixed_entry("   Regel: X") == ("rule", "X")

    def test_no_prefix_returns_none(self):
        assert parse_prefixed_entry("Just a normal sentence.") is None

    def test_empty_body_returns_none(self):
        assert parse_prefixed_entry("Regel:") is None
        assert parse_prefixed_entry("Regel:    ") is None

    def test_similar_but_not_prefix(self):
        assert parse_prefixed_entry("The rule here is important") is None

    def test_extract_from_multiline(self):
        text = (
            "Normal line.\n"
            "Regel: stay tight\n"
            "Another normal line.\n"
            "Callback: Gary\n"
            "Workflow: scene-by-scene\n"
        )
        result = extract_prefixed_lines(text)
        assert result == [
            ("rule", "stay tight"),
            ("callback", "Gary"),
            ("workflow", "scene-by-scene"),
        ]

    def test_extract_empty(self):
        assert extract_prefixed_lines("") == []
        assert extract_prefixed_lines("no prefixes here\nnothing") == []


class TestResolvePath:
    def test_resolve_claudemd_path(self, book_config):
        path = resolve_claudemd_path(book_config, "my-book")
        assert path.name == "CLAUDE.md"
        assert path.parent.name == "my-book"


class TestInitClaudemd:
    def test_creates_file(self, book_config):
        path = init_claudemd(
            book_config,
            PLUGIN_ROOT,
            "my-book",
            facts={"book_title": "My Book", "pov": "first", "genre": "fantasy"},
        )
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "# My Book" in content
        assert "**POV:** first" in content
        assert "**Genre:** fantasy" in content

    def test_contains_section_markers(self, book_config):
        path = init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        content = path.read_text(encoding="utf-8")
        assert "<!-- RULES:START -->" in content
        assert "<!-- RULES:END -->" in content
        assert "<!-- CALLBACKS:START -->" in content
        assert "<!-- WORKFLOW:START -->" in content

    def test_missing_facts_render_as_dash(self, book_config):
        path = init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        content = path.read_text(encoding="utf-8")
        # book_title was not provided
        assert "# —" in content

    def test_refuses_overwrite_by_default(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        with pytest.raises(FileExistsError):
            init_claudemd(book_config, PLUGIN_ROOT, "my-book")

    def test_overwrite_flag(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book", facts={"pov": "first"})
        init_claudemd(
            book_config,
            PLUGIN_ROOT,
            "my-book",
            facts={"pov": "third"},
            overwrite=True,
        )
        content = get_claudemd(book_config, "my-book")
        assert "**POV:** third" in content
        assert "**POV:** first" not in content


class TestGetClaudemd:
    def test_reads_content(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        content = get_claudemd(book_config, "my-book")
        assert "<!-- RULES:END -->" in content

    def test_raises_if_missing(self, book_config):
        with pytest.raises(FileNotFoundError):
            get_claudemd(book_config, "nonexistent")


class TestAppendRule:
    def test_appends_rule(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(book_config, "my-book", "avoid passive voice")
        content = get_claudemd(book_config, "my-book")
        assert "avoid passive voice" in content

    def test_rule_before_end_marker(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(book_config, "my-book", "new rule")
        content = get_claudemd(book_config, "my-book")
        rule_pos = content.index("new rule")
        end_pos = content.index("<!-- RULES:END -->")
        assert rule_pos < end_pos

    def test_rule_not_in_callbacks_section(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(book_config, "my-book", "unique-rule-marker")
        content = get_claudemd(book_config, "my-book")
        callbacks_start = content.index("<!-- CALLBACKS:START -->")
        callbacks_end = content.index("<!-- CALLBACKS:END -->")
        callbacks_section = content[callbacks_start:callbacks_end]
        assert "unique-rule-marker" not in callbacks_section

    def test_multiple_rules(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(book_config, "my-book", "first rule")
        append_rule(book_config, "my-book", "second rule")
        content = get_claudemd(book_config, "my-book")
        assert "first rule" in content
        assert "second rule" in content

    def test_idempotent(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(book_config, "my-book", "same rule")
        append_rule(book_config, "my-book", "same rule")
        content = get_claudemd(book_config, "my-book")
        assert content.count("same rule") == 1

    def test_empty_rejected(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        with pytest.raises(ValueError):
            append_rule(book_config, "my-book", "   ")

    def test_fails_if_not_initialized(self, book_config):
        with pytest.raises(FileNotFoundError):
            append_rule(book_config, "my-book", "something")


class TestAppendRuleNormalization:
    """Verify that rules persisted via ``append_rule`` get their primary
    ban-cued double-quoted phrase converted to backtick form, so the
    PostToolUse hook (which only blocks on backtick patterns) can pick
    them up automatically.
    """

    def test_avoid_quoted_phrase_becomes_backticks(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(book_config, "my-book", 'Avoid "clocked" as a verb')
        content = get_claudemd(book_config, "my-book")
        assert "Avoid `clocked` as a verb" in content
        assert 'Avoid "clocked"' not in content

    def test_do_not_use_quoted_phrase(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(
            book_config, "my-book", 'Do not use "began to" as a verb opener'
        )
        content = get_claudemd(book_config, "my-book")
        assert "Do not use `began to`" in content

    def test_dont_use_smart_apostrophe(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(book_config, "my-book", 'Don’t use "really" too often')
        content = get_claudemd(book_config, "my-book")
        assert "`really`" in content

    def test_limit_with_qualifier(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(
            book_config,
            "my-book",
            'Limit the "specific kind of X that Y" construction',
        )
        content = get_claudemd(book_config, "my-book")
        assert "Limit the `specific kind of X that Y` construction" in content

    def test_only_first_quoted_phrase_converted(self, book_config):
        """Replacement examples that come *after* the banned phrase stay
        in double quotes — they're advice, not patterns to block."""
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(
            book_config,
            "my-book",
            'Avoid "clocked" — replace with "noticed" or "registered"',
        )
        content = get_claudemd(book_config, "my-book")
        assert "Avoid `clocked`" in content
        # The replacement examples remain quoted (they're not block patterns).
        assert '"noticed"' in content
        assert '"registered"' in content

    def test_no_ban_cue_leaves_quotes_intact(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(
            book_config, "my-book", 'Use "felt like" sparingly in dialog'
        )
        content = get_claudemd(book_config, "my-book")
        assert '"felt like"' in content
        assert "`felt like`" not in content

    def test_already_backticked_unchanged(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(book_config, "my-book", "Avoid `clocked` as a verb")
        content = get_claudemd(book_config, "my-book")
        assert "Avoid `clocked` as a verb" in content
        assert "``clocked``" not in content  # no double-wrapping

    def test_workflow_not_normalized(self, book_config):
        """Normalization only applies to rules, not workflows."""
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_workflow(
            book_config, "my-book", 'Avoid "branching" in commit names'
        )
        content = get_claudemd(book_config, "my-book")
        assert '"branching"' in content
        assert "`branching`" not in content

    def test_callback_not_normalized(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_callback(
            book_config, "my-book", 'Avoid "Gary" as a name in next book'
        )
        content = get_claudemd(book_config, "my-book")
        assert '"Gary"' in content


class TestAppendWorkflow:
    def test_appends_to_workflow_section(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_workflow(book_config, "my-book", "scene-by-scene")
        content = get_claudemd(book_config, "my-book")
        wf_start = content.index("<!-- WORKFLOW:START -->")
        wf_end = content.index("<!-- WORKFLOW:END -->")
        assert "scene-by-scene" in content[wf_start:wf_end]


class TestAppendCallback:
    def test_appends_to_callbacks_section(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_callback(book_config, "my-book", "Gary the cat")
        content = get_claudemd(book_config, "my-book")
        cb_start = content.index("<!-- CALLBACKS:START -->")
        cb_end = content.index("<!-- CALLBACKS:END -->")
        assert "Gary the cat" in content[cb_start:cb_end]

    def test_callback_not_in_rules_section(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_callback(book_config, "my-book", "Gary-unique")
        content = get_claudemd(book_config, "my-book")
        rules_start = content.index("<!-- RULES:START -->")
        rules_end = content.index("<!-- RULES:END -->")
        assert "Gary-unique" not in content[rules_start:rules_end]


class TestUpdateBookFacts:
    def test_updates_writing_mode(self, book_config):
        init_claudemd(
            book_config,
            PLUGIN_ROOT,
            "my-book",
            facts={"writing_mode": "chapter"},
        )
        update_book_facts(
            book_config, "my-book", {"writing_mode": "scene-by-scene"}
        )
        content = get_claudemd(book_config, "my-book")
        assert "**Writing Mode:** scene-by-scene" in content
        # Header bullet should not retain old value.
        assert content.count("**Writing Mode:** chapter") == 0

    def test_updates_multiple_fields(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        update_book_facts(
            book_config,
            "my-book",
            {"pov": "first", "tense": "present"},
        )
        content = get_claudemd(book_config, "my-book")
        assert "**POV:** first" in content
        assert "**Tense:** present" in content

    def test_unknown_key_ignored(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        # Ephemeral keys no longer live in CLAUDE.md — silently ignored.
        update_book_facts(book_config, "my-book", {"current_chapter": "01"})

    def test_raises_if_missing(self, book_config):
        with pytest.raises(FileNotFoundError):
            update_book_facts(book_config, "nonexistent", {"pov": "first"})
