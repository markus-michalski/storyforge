"""Tests for listing and editing rules in the book_rules DB.

Phase 4 (#282): rules/callbacks/workflows moved from CLAUDE.md marker blocks
to SQLite. list_rules() / update_rule() now operate on the book_rules table;
CLAUDE.md is prose-only and is never modified by these operations.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.claudemd.manager import append_callback, append_rule, init_claudemd, resolve_claudemd_path
from tools.claudemd.rules_editor import (
    AmbiguousMatchError,
    DisagreeingResolutionError,
    _list_rules_by_type,
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


@pytest.fixture(autouse=True)
def isolate_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect DB_DIR to tmp_path so tests don't touch ~/.storyforge/db/."""
    import tools.db.connection as _conn
    monkeypatch.setattr(_conn, "DB_DIR", tmp_path / "db")


def _seed_rules(book_config: dict, rules: list[str]) -> None:
    """Initialize CLAUDE.md and seed rules into the book_rules DB."""
    init_claudemd(book_config, PLUGIN_ROOT, "my-book")
    for rule_text in rules:
        append_rule(book_config, "my-book", rule_text)


# ---------------------------------------------------------------------------
# list_rules
# ---------------------------------------------------------------------------


class TestListRules:
    def test_empty_returns_no_rules(self, book_config):
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
                "**R1** — avoid `clocked` as a verb",       # literal
                r"**R2** — avoid `\bsuddenly\b` patterns",  # regex (\b)
                "**R3** — narrative discipline only",        # neither
            ],
        )
        rules = list_rules(book_config, "my-book")
        assert rules[0].has_literals is True
        assert rules[0].has_regex is False
        assert rules[1].has_regex is True
        assert rules[2].has_literals is False
        assert rules[2].has_regex is False

    def test_degrades_gracefully_if_claudemd_missing(self, book_config):
        # No init_claudemd — CLAUDE.md does not exist, but the book itself
        # does. Rules live in the book_rules DB independent of the file
        # (Phase 4 migration), so this must not raise — Issue #573.
        assert list_rules(book_config, "my-book") == []

    def test_survives_claudemd_deleted_after_rules_seeded(self, book_config):
        # The DB content must actually survive the file going away — not
        # just "no raise" (which a hardcoded [] return would also satisfy).
        _seed_rules(book_config, ["**Rule 1** — avoid passive voice"])
        resolve_claudemd_path(book_config, "my-book").unlink()

        rules = list_rules(book_config, "my-book")
        assert len(rules) == 1
        assert rules[0].title == "Rule 1"

    def test_raises_if_book_itself_missing(self, book_config):
        # No book directory at all — genuinely invalid input, unlike the
        # missing-CLAUDE.md-only case above.
        with pytest.raises(FileNotFoundError):
            list_rules(book_config, "does-not-exist")


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
# update_rule / list_rules — reaching callback entries (Issue #605)
# ---------------------------------------------------------------------------


class TestReachesCallbacks:
    def test_list_rules_does_not_include_callbacks(self, book_config):
        """Baseline: list_rules() stays rule-only — callbacks must not leak
        into the plain rules listing/index space."""
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(book_config, "my-book", "**R1** — first")
        append_callback(book_config, "my-book", "Ch 5 fixer note — bet timeline is canon-broken")

        rules = list_rules(book_config, "my-book")
        assert len(rules) == 1
        assert rules[0].title == "R1"

    def test_default_ignores_callbacks_even_on_no_rule_match(self, book_config):
        """Regression guard: without include_callbacks=True, a rule_match
        that only exists in callback prose must stay a safe found:False
        no-op — the exact behavior promote-rule and rules-audit already
        depend on (SKILL.md instructs update_book_rule(rule_match=phrase,
        delete=True) as a documented, known-safe fallback when a phrase
        isn't a rule). Making the callback search implicit would turn
        those callers' no-ops into silent, undocumented deletions of
        unrelated callback prose that happens to contain the phrase as a
        substring (Issue #605 review)."""
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_callback(book_config, "my-book", "Ch 5 fixer note — bet timeline is canon-broken")

        result = update_rule(
            book_config, "my-book",
            rule_match="bet timeline is canon-broken", delete=True,
        )
        assert result["found"] is False
        assert result["rule_type"] is None

        # Untouched.
        assert len(_list_rules_by_type(book_config, "my-book", "callback")) == 1

    def test_update_by_match_deletes_callback(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(book_config, "my-book", "**R1** — first")
        append_callback(
            book_config, "my-book",
            "Ch 5 fixer note — bet timeline is canon-broken, and the chapter misses its own best beat.",
        )

        result = update_rule(
            book_config, "my-book",
            rule_match="bet timeline is canon-broken", delete=True,
            include_callbacks=True,
        )
        assert result["found"] is True
        assert result["changed"] is True
        assert result["rule_type"] == "callback"
        # Not a usable rule-list index — must not be replayable as rule_index.
        assert result["rule_index"] == -1

        # The callback row is actually gone from the DB, not just absent
        # from list_rules() (which never contained it in the first place).
        assert _list_rules_by_type(book_config, "my-book", "callback") == []
        # The unrelated rule survives untouched.
        rules = list_rules(book_config, "my-book")
        assert len(rules) == 1
        assert rules[0].title == "R1"

    def test_update_by_match_replaces_callback_text_preserving_newlines(self, book_config):
        # callback_validator parses multi-line callback bodies structurally
        # (Issue #605 review) — a whitespace-collapsing normalize would
        # corrupt that, unlike single-line rule bodies.
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_callback(
            book_config, "my-book",
            "Ch 5 fixer note — stale, already resolved\nkeep for context",
        )

        result = update_rule(
            book_config, "my-book",
            rule_match="stale, already resolved",
            new_text="Ch 5 fixer note — resolved on-page in Ch 07\nkeep for context",
            include_callbacks=True,
        )
        assert result["found"] is True
        assert result["changed"] is True
        assert result["rule_type"] == "callback"

        stored = _list_rules_by_type(book_config, "my-book", "callback")
        assert len(stored) == 1
        assert stored[0].raw_text == "Ch 5 fixer note — resolved on-page in Ch 07\nkeep for context"

    def test_update_by_match_skips_lint_for_callback_text(self, book_config):
        # This exact text carries a ban cue ("Never") with no backtick/quoted
        # pattern — under the *rule* lint contract that triggers a
        # scanner_extracts_nothing warning (tools/claudemd/rules_lint.py).
        # Proves the callback path actually suppresses the lint rather than
        # the text just happening to lint clean either way.
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        lint_triggering_text = "Never use vague filler words in this note."
        append_callback(book_config, "my-book", "placeholder")

        result = update_rule(
            book_config, "my-book",
            rule_match="placeholder",
            new_text=lint_triggering_text,
            include_callbacks=True,
        )
        assert result["found"] is True
        assert result["rule_type"] == "callback"
        assert result["warnings"] == []
        assert result["extracted_patterns"] == []

        from tools.claudemd.rules_lint import lint_rule_text
        assert lint_rule_text(lint_triggering_text)["warnings"], (
            "fixture text must actually trigger a rule-contract lint warning "
            "for this test to prove anything"
        )

    def test_no_match_in_rules_or_callbacks_returns_found_false(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(book_config, "my-book", "**R1** — first")
        append_callback(book_config, "my-book", "some callback note")

        result = update_rule(
            book_config, "my-book",
            rule_match="nonexistent-phrase", delete=True,
            include_callbacks=True,
        )
        assert result["found"] is False

    def test_ambiguous_callback_match_error_mentions_callbacks(self, book_config):
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_callback(book_config, "my-book", "Ch 3 callback — shared phrase one")
        append_callback(book_config, "my-book", "Ch 7 callback — shared phrase two")

        with pytest.raises(AmbiguousMatchError) as exc:
            update_rule(
                book_config, "my-book",
                rule_match="shared phrase", delete=True,
                include_callbacks=True,
            )
        assert "callbacks:" in str(exc.value)

    def test_rule_index_present_never_falls_back_to_callbacks(self, book_config):
        """A rule_index that happens to resolve within the rule list wins
        outright — pre-existing _resolve_target_index semantics (a lone
        by_index match needs no by_match agreement). The callback fallback
        must not additionally kick in here: rule_index being set at all
        keeps resolution inside the rule list, so a rule_match that only
        matches a callback is correctly ignored rather than accidentally
        reaching into the callback list (Issue #605 review)."""
        init_claudemd(book_config, PLUGIN_ROOT, "my-book")
        append_rule(book_config, "my-book", "**R1** — keep me")
        append_callback(book_config, "my-book", "Ch 3 callback — CB-A")

        result = update_rule(
            book_config, "my-book",
            rule_index=0, rule_match="CB-A", delete=True,
            include_callbacks=True,
        )
        assert result["found"] is True
        assert result["rule_type"] == "rule"
        assert result["old_text"] == "**R1** — keep me"

        # The callback the rule_match text names is untouched.
        callbacks = _list_rules_by_type(book_config, "my-book", "callback")
        assert len(callbacks) == 1
        assert "CB-A" in callbacks[0].raw_text

    def test_list_rules_by_type_raises_if_book_missing(self, book_config):
        with pytest.raises(FileNotFoundError):
            _list_rules_by_type(book_config, "does-not-exist", "callback")


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
# File not modified (Phase 4: rules live in DB, CLAUDE.md is prose-only)
# ---------------------------------------------------------------------------


class TestFileNotModified:
    def test_claudemd_unchanged_after_rule_update(self, book_config):
        _seed_rules(book_config, ["**R1** — first", "**R2** — second"])
        path = resolve_claudemd_path(book_config, "my-book")
        content_before = path.read_text(encoding="utf-8")

        update_rule(book_config, "my-book", rule_index=0, new_text="**R1** — replaced")

        assert path.read_text(encoding="utf-8") == content_before

    def test_claudemd_unchanged_after_delete(self, book_config):
        _seed_rules(book_config, ["**R1** — first"])
        path = resolve_claudemd_path(book_config, "my-book")
        content_before = path.read_text(encoding="utf-8")

        update_rule(book_config, "my-book", rule_index=0, delete=True)

        assert path.read_text(encoding="utf-8") == content_before


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_update_degrades_gracefully_if_claudemd_missing(self, book_config):
        """Issue #580: no init_claudemd — CLAUDE.md does not exist, but the
        book itself does. list_rules() (Issue #573) already returns []
        gracefully for this state instead of raising; update_rule() must
        not raise ahead of that call either — there are no rules to find,
        so this is a plain found: False, not an error."""
        result = update_rule(
            book_config, "my-book",
            rule_index=0, new_text="x",
        )
        assert result["found"] is False
        assert result["changed"] is False

    def test_update_succeeds_without_claudemd_when_rules_exist(self, book_config):
        """The capability this fix actually adds: editing a real rule while
        CLAUDE.md is absent — not just the trivially-safe empty-DB case
        above. Seeds a row directly via insert_rule(), bypassing
        _append_entry()'s CLAUDE.md-exists guard, the same way an
        unlinked-series-book collision (pre-#579) or a duplicate
        series_number (still open, see rules_editor.update_rule's
        docstring) could leave a book with DB rows but no CLAUDE.md."""
        from tools.claudemd.manager import _open_book_db
        from tools.db.book_rules import insert_rule

        conn, book_num = _open_book_db(book_config, "my-book")
        try:
            insert_rule(conn, book_num=book_num, rule_type="rule", text="**R** — avoid `x`")
        finally:
            conn.close()

        result = update_rule(
            book_config, "my-book",
            rule_index=0, new_text="**R** — avoid `y`",
        )

        assert result["found"] is True
        assert result["changed"] is True
        rules = list_rules(book_config, "my-book")
        assert rules[0].raw_text == "**R** — avoid `y`"

    def test_multiline_rule_body_preserved(self, book_config):
        """A rule with embedded newlines is stored and retrieved intact."""
        multiline = "**R1** — first line of rule\n  continuation on second line\n  and third line"
        _seed_rules(book_config, [multiline, "**R2** — second rule"])
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
