"""Tests for cover_images CRUD — Issue #551."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.db.connection import ensure_schema, open_db
from tools.db.cover_images import get_final_cover_image, list_cover_images, upsert_cover_image


@pytest.fixture
def conn(tmp_path: Path):
    db = open_db(tmp_path / "test.db")
    ensure_schema(db)
    yield db
    db.close()


class TestUpsertCoverImage:
    def test_inserts_draft(self, conn):
        upsert_cover_image(conn, book_num=1, filename="cover.png", is_final=False)
        rows = conn.execute("SELECT filename, is_final FROM cover_images").fetchall()
        assert (rows[0]["filename"], rows[0]["is_final"]) == ("cover.png", 0)

    def test_inserts_final(self, conn):
        upsert_cover_image(conn, book_num=1, filename="cover-final.png", is_final=True)
        row = conn.execute("SELECT is_final FROM cover_images").fetchone()
        assert row["is_final"] == 1

    def test_marking_new_final_clears_previous_final(self, conn):
        upsert_cover_image(conn, book_num=1, filename="cover-a.png", is_final=True)
        upsert_cover_image(conn, book_num=1, filename="cover-b.png", is_final=True)
        rows = conn.execute("SELECT filename, is_final FROM cover_images ORDER BY filename").fetchall()
        by_name = {r["filename"]: r["is_final"] for r in rows}
        assert by_name == {"cover-a.png": 0, "cover-b.png": 1}

    def test_marking_final_does_not_affect_other_books(self, conn):
        upsert_cover_image(conn, book_num=1, filename="cover-a.png", is_final=True)
        upsert_cover_image(conn, book_num=2, filename="cover-b.png", is_final=True)
        rows = {r["book_num"]: r["is_final"] for r in conn.execute("SELECT book_num, is_final FROM cover_images")}
        assert rows == {1: 1, 2: 1}

    def test_reimport_same_filename_updates_flag(self, conn):
        upsert_cover_image(conn, book_num=1, filename="cover.png", is_final=False)
        upsert_cover_image(conn, book_num=1, filename="cover.png", is_final=True)
        rows = conn.execute("SELECT COUNT(*) as cnt FROM cover_images").fetchone()
        assert rows["cnt"] == 1
        row = conn.execute("SELECT is_final FROM cover_images WHERE filename='cover.png'").fetchone()
        assert row["is_final"] == 1


class TestGetFinalCoverImage:
    def test_returns_final_filename(self, conn):
        upsert_cover_image(conn, book_num=1, filename="draft.png", is_final=False)
        upsert_cover_image(conn, book_num=1, filename="final.png", is_final=True)
        assert get_final_cover_image(conn, book_num=1) == "final.png"

    def test_returns_none_when_no_final_marked(self, conn):
        upsert_cover_image(conn, book_num=1, filename="draft.png", is_final=False)
        assert get_final_cover_image(conn, book_num=1) is None

    def test_returns_none_for_unknown_book(self, conn):
        assert get_final_cover_image(conn, book_num=99) is None

    def test_scoped_to_book_num(self, conn):
        upsert_cover_image(conn, book_num=1, filename="book1-final.png", is_final=True)
        upsert_cover_image(conn, book_num=2, filename="book2-final.png", is_final=True)
        assert get_final_cover_image(conn, book_num=1) == "book1-final.png"
        assert get_final_cover_image(conn, book_num=2) == "book2-final.png"


class TestListCoverImages:
    def test_lists_all_for_book(self, conn):
        upsert_cover_image(conn, book_num=1, filename="a.png", is_final=False)
        upsert_cover_image(conn, book_num=1, filename="b.png", is_final=True)
        result = list_cover_images(conn, book_num=1)
        filenames = {r["filename"] for r in result}
        assert filenames == {"a.png", "b.png"}

    def test_returns_empty_list_for_book_with_none(self, conn):
        assert list_cover_images(conn, book_num=1) == []

    def test_result_dicts_have_required_keys(self, conn):
        upsert_cover_image(conn, book_num=1, filename="a.png", is_final=False)
        result = list_cover_images(conn, book_num=1)
        assert {"filename", "is_final", "imported_at"} <= result[0].keys()
