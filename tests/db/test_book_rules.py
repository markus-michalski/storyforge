"""Tests for book_rules DB module — Issue #282."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.db.book_rules import delete_rule, get_rule, insert_rule, list_rules, update_rule_text
from tools.db.connection import ensure_schema, open_db


@pytest.fixture
def conn(tmp_path: Path):
    db = open_db(tmp_path / "test.db")
    ensure_schema(db)
    yield db
    db.close()


class TestInsertRule:
    def test_insert_returns_rule_id(self, conn):
        result = insert_rule(conn, book_num=1, rule_type="rule", text="Avoid `clocked`")
        assert result["inserted"] is True
        assert result["rule_id"] > 0

    def test_insert_idempotent(self, conn):
        first = insert_rule(conn, book_num=1, rule_type="rule", text="Avoid `clocked`")
        second = insert_rule(conn, book_num=1, rule_type="rule", text="Avoid `clocked`")
        assert first["rule_id"] == second["rule_id"]
        assert second["inserted"] is False

    def test_same_text_different_book_num_both_inserted(self, conn):
        r1 = insert_rule(conn, book_num=1, rule_type="rule", text="Same text")
        r2 = insert_rule(conn, book_num=2, rule_type="rule", text="Same text")
        assert r1["rule_id"] != r2["rule_id"]
        assert r1["inserted"] is True
        assert r2["inserted"] is True

    def test_same_text_different_rule_type_both_inserted(self, conn):
        r1 = insert_rule(conn, book_num=1, rule_type="rule", text="Do this")
        r2 = insert_rule(conn, book_num=1, rule_type="callback", text="Do this")
        assert r1["rule_id"] != r2["rule_id"]

    def test_series_wide_entry_book_num_none(self, conn):
        result = insert_rule(conn, book_num=None, rule_type="rule", text="Series-wide rule")
        assert result["inserted"] is True

    def test_series_wide_idempotent(self, conn):
        first = insert_rule(conn, book_num=None, rule_type="rule", text="Series-wide rule")
        second = insert_rule(conn, book_num=None, rule_type="rule", text="Series-wide rule")
        assert first["rule_id"] == second["rule_id"]
        assert second["inserted"] is False


class TestListRules:
    def test_list_empty_returns_empty(self, conn):
        assert list_rules(conn, book_num=1, rule_type="rule") == []

    def test_list_returns_inserted_row(self, conn):
        insert_rule(conn, book_num=1, rule_type="rule", text="Rule A")
        rows = list_rules(conn, book_num=1, rule_type="rule")
        assert len(rows) == 1
        assert rows[0]["text"] == "Rule A"

    def test_list_filters_by_rule_type(self, conn):
        insert_rule(conn, book_num=1, rule_type="rule", text="A rule")
        insert_rule(conn, book_num=1, rule_type="callback", text="A callback")
        rules = list_rules(conn, book_num=1, rule_type="rule")
        callbacks = list_rules(conn, book_num=1, rule_type="callback")
        assert len(rules) == 1
        assert len(callbacks) == 1

    def test_list_filters_by_book_num(self, conn):
        insert_rule(conn, book_num=1, rule_type="rule", text="B1 rule")
        insert_rule(conn, book_num=2, rule_type="rule", text="B2 rule")
        b1 = list_rules(conn, book_num=1, rule_type="rule")
        b2 = list_rules(conn, book_num=2, rule_type="rule")
        assert b1[0]["text"] == "B1 rule"
        assert b2[0]["text"] == "B2 rule"

    def test_list_ordered_by_insertion(self, conn):
        for text in ["First", "Second", "Third"]:
            insert_rule(conn, book_num=1, rule_type="rule", text=text)
        rows = list_rules(conn, book_num=1, rule_type="rule")
        assert [r["text"] for r in rows] == ["First", "Second", "Third"]

    def test_list_row_has_required_fields(self, conn):
        insert_rule(conn, book_num=1, rule_type="rule", text="Test rule")
        row = list_rules(conn, book_num=1, rule_type="rule")[0]
        assert {"id", "book_num", "rule_type", "text", "added_at"} <= set(row.keys())

    def test_list_no_filters_returns_all(self, conn):
        insert_rule(conn, book_num=1, rule_type="rule", text="R1")
        insert_rule(conn, book_num=2, rule_type="callback", text="C2")
        assert len(list_rules(conn)) == 2


class TestGetRule:
    def test_get_existing(self, conn):
        result = insert_rule(conn, book_num=1, rule_type="rule", text="Get me")
        row = get_rule(conn, result["rule_id"])
        assert row is not None
        assert row["text"] == "Get me"

    def test_get_missing_returns_none(self, conn):
        assert get_rule(conn, 9999) is None


class TestUpdateRuleText:
    def test_update_changes_text(self, conn):
        result = insert_rule(conn, book_num=1, rule_type="rule", text="Old text")
        changed = update_rule_text(conn, result["rule_id"], "New text")
        assert changed is True
        row = get_rule(conn, result["rule_id"])
        assert row["text"] == "New text"

    def test_update_strips_whitespace(self, conn):
        result = insert_rule(conn, book_num=1, rule_type="rule", text="Old text")
        update_rule_text(conn, result["rule_id"], "  Padded  ")
        row = get_rule(conn, result["rule_id"])
        assert row["text"] == "Padded"

    def test_update_missing_id_returns_false(self, conn):
        assert update_rule_text(conn, 9999, "Whatever") is False


class TestDeleteRule:
    def test_delete_removes_row(self, conn):
        result = insert_rule(conn, book_num=1, rule_type="rule", text="Delete me")
        deleted = delete_rule(conn, result["rule_id"])
        assert deleted is True
        assert get_rule(conn, result["rule_id"]) is None

    def test_delete_missing_id_returns_false(self, conn):
        assert delete_rule(conn, 9999) is False

    def test_delete_only_removes_target(self, conn):
        r1 = insert_rule(conn, book_num=1, rule_type="rule", text="Keep me")
        r2 = insert_rule(conn, book_num=1, rule_type="rule", text="Delete me")
        delete_rule(conn, r2["rule_id"])
        assert get_rule(conn, r1["rule_id"]) is not None
        assert get_rule(conn, r2["rule_id"]) is None


class TestSchemaBookRulesTable:
    def test_book_rules_table_exists(self, conn):
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "book_rules" in tables

    def test_book_rules_has_required_columns(self, conn):
        cols = {r[1] for r in conn.execute("PRAGMA table_info(book_rules)")}
        assert {"id", "book_num", "rule_type", "text", "added_at"} <= cols

    def test_book_rules_index_exists(self, conn):
        indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert "idx_br" in indexes
