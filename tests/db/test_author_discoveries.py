"""Tests for author_discoveries CRUD — Issue #281."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.db.author_discoveries import (
    VALID_TYPES,
    discoveries_as_writing_discoveries,
    discovery_exists,
    get_discoveries,
    insert_discovery,
    remove_author_discoveries,
    update_source_genres,
)
from tools.db.connection import ensure_authors_schema, open_db


@pytest.fixture
def conn(tmp_path: Path):
    db = open_db(tmp_path / "authors.db")
    ensure_authors_schema(db)
    yield db
    db.close()


class TestValidTypes:
    def test_valid_types_contains_expected(self):
        assert "recurring_tics" in VALID_TYPES
        assert "style_principles" in VALID_TYPES
        assert "donts" in VALID_TYPES


class TestInsertDiscovery:
    def test_inserts_basic_discovery(self, conn):
        inserted = insert_discovery(
            conn,
            author_slug="ethan-cole",
            discovery_type="recurring_tics",
            text='**"thing"** — concretize on sight.',
            book_slug="firelight",
            date_added="2026-05",
        )
        assert inserted is True
        rows = conn.execute("SELECT * FROM author_discoveries").fetchall()
        assert len(rows) == 1
        assert rows[0]["author_slug"] == "ethan-cole"
        assert rows[0]["discovery_type"] == "recurring_tics"

    def test_unique_constraint_returns_false_on_duplicate(self, conn):
        insert_discovery(
            conn, author_slug="ethan-cole", discovery_type="recurring_tics",
            text="**Bold** — note.", book_slug="firelight",
        )
        again = insert_discovery(
            conn, author_slug="ethan-cole", discovery_type="recurring_tics",
            text="**Bold** — note.", book_slug="firelight",
        )
        assert again is False
        count = conn.execute("SELECT COUNT(*) FROM author_discoveries").fetchone()[0]
        assert count == 1

    def test_different_types_same_text_allowed(self, conn):
        insert_discovery(conn, author_slug="a", discovery_type="donts", text="x")
        insert_discovery(conn, author_slug="a", discovery_type="recurring_tics", text="x")
        count = conn.execute("SELECT COUNT(*) FROM author_discoveries").fetchone()[0]
        assert count == 2

    def test_stores_source_genres_and_universal(self, conn):
        insert_discovery(
            conn,
            author_slug="ethan-cole",
            discovery_type="style_principles",
            text="Avoid purple prose.",
            source_genres="shifter-romance,omega-verse",
            universal=True,
        )
        row = conn.execute("SELECT source_genres, universal FROM author_discoveries").fetchone()
        assert row["source_genres"] == "shifter-romance,omega-verse"
        assert row["universal"] == 1

    def test_stores_example(self, conn):
        insert_discovery(
            conn, author_slug="a", discovery_type="style_principles",
            text="Use concrete detail.", example="He smelled burnt oil, not fear.",
        )
        row = conn.execute("SELECT example FROM author_discoveries").fetchone()
        assert row["example"] == "He smelled burnt oil, not fear."


class TestGetDiscoveries:
    def test_returns_all_for_author(self, conn):
        insert_discovery(conn, author_slug="a", discovery_type="recurring_tics", text="tic1")
        insert_discovery(conn, author_slug="a", discovery_type="donts", text="dont1")
        insert_discovery(conn, author_slug="b", discovery_type="recurring_tics", text="other")
        rows = get_discoveries(conn, "a")
        assert len(rows) == 2
        slugs = {r["author_slug"] for r in rows}
        assert slugs == {"a"}

    def test_filters_by_type(self, conn):
        insert_discovery(conn, author_slug="a", discovery_type="recurring_tics", text="tic1")
        insert_discovery(conn, author_slug="a", discovery_type="donts", text="dont1")
        rows = get_discoveries(conn, "a", "recurring_tics")
        assert len(rows) == 1
        assert rows[0]["discovery_type"] == "recurring_tics"

    def test_returns_empty_for_unknown_author(self, conn):
        rows = get_discoveries(conn, "nobody")
        assert rows == []

    def test_ordered_by_id_within_type(self, conn):
        insert_discovery(conn, author_slug="a", discovery_type="donts", text="first")
        insert_discovery(conn, author_slug="a", discovery_type="donts", text="second")
        rows = get_discoveries(conn, "a", "donts")
        assert rows[0]["text"] == "first"
        assert rows[1]["text"] == "second"


class TestDiscoveryExists:
    def test_returns_true_if_exists(self, conn):
        insert_discovery(conn, author_slug="a", discovery_type="donts", text="x")
        assert discovery_exists(conn, "a", "donts", "x") is True

    def test_returns_false_if_not_exists(self, conn):
        assert discovery_exists(conn, "a", "donts", "x") is False

    def test_case_sensitive_match(self, conn):
        insert_discovery(conn, author_slug="a", discovery_type="donts", text="Thing")
        assert discovery_exists(conn, "a", "donts", "thing") is False


class TestUpdateSourceGenres:
    def test_updates_all_discoveries_for_book(self, conn):
        insert_discovery(conn, author_slug="a", discovery_type="donts", text="x", book_slug="book1")
        insert_discovery(conn, author_slug="a", discovery_type="donts", text="y", book_slug="book1")
        insert_discovery(conn, author_slug="a", discovery_type="donts", text="z", book_slug="book2")

        count = update_source_genres(conn, author_slug="a", book_slug="book1", source_genres="shifter-romance")
        assert count == 2

        rows = conn.execute(
            "SELECT source_genres FROM author_discoveries WHERE book_slug='book1'"
        ).fetchall()
        for r in rows:
            assert r["source_genres"] == "shifter-romance"

    def test_returns_zero_for_unknown_book(self, conn):
        count = update_source_genres(conn, author_slug="a", book_slug="missing", source_genres="x")
        assert count == 0


class TestDiscoveriesAsWritingDiscoveries:
    def test_groups_by_type(self, conn):
        insert_discovery(conn, author_slug="a", discovery_type="recurring_tics", text="tic1", book_slug="b1", date_added="2026-01")
        insert_discovery(conn, author_slug="a", discovery_type="style_principles", text="principle1")
        insert_discovery(conn, author_slug="a", discovery_type="donts", text="dont1")
        rows = get_discoveries(conn, "a")
        result = discoveries_as_writing_discoveries(rows)
        assert len(result["recurring_tics"]) == 1
        assert len(result["style_principles"]) == 1
        assert len(result["donts"]) == 1

    def test_origins_populated_from_book_slug_and_date(self, conn):
        insert_discovery(conn, author_slug="a", discovery_type="recurring_tics",
                         text="tic1", book_slug="firelight", date_added="2026-05")
        rows = get_discoveries(conn, "a")
        result = discoveries_as_writing_discoveries(rows)
        origins = result["recurring_tics"][0]["origins"]
        assert origins == [{"book": "firelight", "date": "2026-05"}]

    def test_no_origins_when_no_book_slug(self, conn):
        insert_discovery(conn, author_slug="a", discovery_type="donts", text="x")
        rows = get_discoveries(conn, "a")
        result = discoveries_as_writing_discoveries(rows)
        assert result["donts"][0]["origins"] == []

    def test_genres_key_present_when_source_genres_set(self, conn):
        insert_discovery(conn, author_slug="a", discovery_type="style_principles",
                         text="p", source_genres="romance,thriller")
        rows = get_discoveries(conn, "a")
        result = discoveries_as_writing_discoveries(rows)
        assert result["style_principles"][0]["genres"] == ["romance", "thriller"]

    def test_example_key_present_when_set(self, conn):
        insert_discovery(conn, author_slug="a", discovery_type="style_principles",
                         text="p", example="He burned it.")
        rows = get_discoveries(conn, "a")
        result = discoveries_as_writing_discoveries(rows)
        assert result["style_principles"][0]["example"] == "He burned it."

    def test_unknown_type_rows_are_skipped(self, conn):
        conn.execute(
            "INSERT INTO author_discoveries (author_slug, discovery_type, text) VALUES (?, ?, ?)",
            ("a", "unknown_type", "x"),
        )
        conn.commit()
        rows = get_discoveries(conn, "a")
        result = discoveries_as_writing_discoveries(rows)
        assert all(len(v) == 0 for v in result.values())


class TestRemoveAuthorDiscoveries:
    def test_removes_all_rows_for_author(self, conn):
        insert_discovery(conn, author_slug="a", discovery_type="donts", text="x")
        insert_discovery(conn, author_slug="a", discovery_type="style_principles", text="y")
        removed = remove_author_discoveries(conn, "a")
        assert removed == 2
        assert get_discoveries(conn, "a") == []

    def test_leaves_other_authors_untouched(self, conn):
        insert_discovery(conn, author_slug="a", discovery_type="donts", text="x")
        insert_discovery(conn, author_slug="b", discovery_type="donts", text="x")
        removed = remove_author_discoveries(conn, "a")
        assert removed == 1
        assert len(get_discoveries(conn, "b")) == 1

    def test_returns_zero_when_no_rows(self, conn):
        assert remove_author_discoveries(conn, "ghost") == 0
