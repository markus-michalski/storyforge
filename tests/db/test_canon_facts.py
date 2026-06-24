"""Tests for canon_facts CRUD — Issue #280."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.db.canon_facts import insert_fact, query_facts
from tools.db.connection import ensure_schema, open_db


@pytest.fixture
def conn(tmp_path: Path):
    db = open_db(tmp_path / "test.db")
    ensure_schema(db)
    yield db
    db.close()


class TestInsertFact:
    def test_inserts_basic_fact(self, conn):
        insert_fact(conn, book_num=1, chapter_num=5, subject="Lucien", fact="Has silver eyes")
        rows = [(r["subject"], r["fact"]) for r in conn.execute("SELECT subject, fact FROM canon_facts").fetchall()]
        assert ("Lucien", "Has silver eyes") in rows

    def test_unique_constraint_prevents_duplicate(self, conn):
        insert_fact(conn, book_num=1, chapter_num=5, subject="Lucien", fact="Has silver eyes")
        insert_fact(conn, book_num=1, chapter_num=5, subject="Lucien", fact="Has silver eyes")
        rows = conn.execute("SELECT COUNT(*) FROM canon_facts").fetchone()
        assert rows[0] == 1

    def test_revision_fact_stores_old_value(self, conn):
        insert_fact(conn, book_num=1, chapter_num=8, subject="Mine",
                    fact="Is abandoned", is_revision=True,
                    old_value="Is active", revision_impacts='["ch-07-descent"]')
        row = conn.execute(
            "SELECT is_revision, old_value, revision_impacts FROM canon_facts"
        ).fetchone()
        assert row[0] == 1
        assert row[1] == "Is active"
        assert row[2] == '["ch-07-descent"]'

    def test_inserts_facts_for_multiple_chapters(self, conn):
        insert_fact(conn, book_num=1, chapter_num=1, subject="World", fact="Has two moons")
        insert_fact(conn, book_num=1, chapter_num=3, subject="World", fact="Has no magic system")
        count = conn.execute("SELECT COUNT(*) FROM canon_facts").fetchone()[0]
        assert count == 2


class TestQueryFacts:
    def test_returns_facts_up_to_chapter(self, conn):
        insert_fact(conn, book_num=1, chapter_num=1, subject="A", fact="Fact 1")
        insert_fact(conn, book_num=1, chapter_num=5, subject="B", fact="Fact 5")
        insert_fact(conn, book_num=1, chapter_num=10, subject="C", fact="Fact 10")

        results = query_facts(conn, book_num=1, up_to_chapter=5)
        subjects = {r["subject"] for r in results}
        assert "A" in subjects
        assert "B" in subjects
        assert "C" not in subjects

    def test_includes_all_books_up_to_current(self, conn):
        insert_fact(conn, book_num=1, chapter_num=30, subject="B1", fact="Book 1 fact")
        insert_fact(conn, book_num=2, chapter_num=3, subject="B2", fact="Book 2 fact")

        results = query_facts(conn, book_num=2, up_to_chapter=3)
        subjects = {r["subject"] for r in results}
        assert "B1" in subjects
        assert "B2" in subjects

    def test_returns_empty_for_empty_db(self, conn):
        results = query_facts(conn, book_num=1, up_to_chapter=999)
        assert results == []

    def test_result_dicts_have_required_keys(self, conn):
        insert_fact(conn, book_num=1, chapter_num=1, subject="X", fact="Y")
        results = query_facts(conn, book_num=1, up_to_chapter=1)
        assert len(results) == 1
        r = results[0]
        assert {"subject", "fact", "book_num", "chapter_num", "domain"} <= r.keys()

    def test_ordered_by_book_then_chapter(self, conn):
        insert_fact(conn, book_num=1, chapter_num=5, subject="Late", fact="Late fact")
        insert_fact(conn, book_num=1, chapter_num=1, subject="Early", fact="Early fact")
        results = query_facts(conn, book_num=1, up_to_chapter=10)
        chapters = [r["chapter_num"] for r in results]
        assert chapters == sorted(chapters)
