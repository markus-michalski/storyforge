"""Tests for cover_images CRUD — Issue #551."""

from __future__ import annotations

import sqlite3
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
        upsert_cover_image(conn, book_slug="firelight", filename="cover.png", is_final=False)
        rows = conn.execute("SELECT filename, is_final FROM cover_images").fetchall()
        assert (rows[0]["filename"], rows[0]["is_final"]) == ("cover.png", 0)

    def test_inserts_final(self, conn):
        upsert_cover_image(conn, book_slug="firelight", filename="cover-final.png", is_final=True)
        row = conn.execute("SELECT is_final FROM cover_images").fetchone()
        assert row["is_final"] == 1

    def test_marking_new_final_clears_previous_final(self, conn):
        upsert_cover_image(conn, book_slug="firelight", filename="cover-a.png", is_final=True)
        upsert_cover_image(conn, book_slug="firelight", filename="cover-b.png", is_final=True)
        rows = conn.execute("SELECT filename, is_final FROM cover_images ORDER BY filename").fetchall()
        by_name = {r["filename"]: r["is_final"] for r in rows}
        assert by_name == {"cover-a.png": 0, "cover-b.png": 1}

    def test_marking_final_does_not_affect_other_books(self, conn):
        upsert_cover_image(conn, book_slug="firelight", filename="cover-a.png", is_final=True)
        upsert_cover_image(conn, book_slug="other-book", filename="cover-b.png", is_final=True)
        rows = {
            r["book_slug"]: r["is_final"] for r in conn.execute("SELECT book_slug, is_final FROM cover_images")
        }
        assert rows == {"firelight": 1, "other-book": 1}

    def test_reimport_same_filename_updates_flag(self, conn):
        upsert_cover_image(conn, book_slug="firelight", filename="cover.png", is_final=False)
        upsert_cover_image(conn, book_slug="firelight", filename="cover.png", is_final=True)
        rows = conn.execute("SELECT COUNT(*) as cnt FROM cover_images").fetchone()
        assert rows["cnt"] == 1
        row = conn.execute("SELECT is_final FROM cover_images WHERE filename='cover.png'").fetchone()
        assert row["is_final"] == 1

    def test_two_under_specified_series_books_do_not_collide(self, conn):
        """#558: get_book_num() defaults to 1 for a book whose README is
        missing/unparseable series_number. Two such books in the same
        series-scoped DB previously shared cover_images rows keyed on
        book_num=1 alone — keying on book_slug instead means they never
        collide even though both would report book_num=1."""
        upsert_cover_image(conn, book_slug="book-one", filename="cover.png", is_final=True)
        upsert_cover_image(conn, book_slug="book-two", filename="cover.png", is_final=True)

        assert get_final_cover_image(conn, book_slug="book-one") == "cover.png"
        assert get_final_cover_image(conn, book_slug="book-two") == "cover.png"
        rows = conn.execute("SELECT COUNT(*) as cnt FROM cover_images").fetchone()
        assert rows["cnt"] == 2


class TestGetFinalCoverImage:
    def test_returns_final_filename(self, conn):
        upsert_cover_image(conn, book_slug="firelight", filename="draft.png", is_final=False)
        upsert_cover_image(conn, book_slug="firelight", filename="final.png", is_final=True)
        assert get_final_cover_image(conn, book_slug="firelight") == "final.png"

    def test_returns_none_when_no_final_marked(self, conn):
        upsert_cover_image(conn, book_slug="firelight", filename="draft.png", is_final=False)
        assert get_final_cover_image(conn, book_slug="firelight") is None

    def test_returns_none_for_unknown_book(self, conn):
        assert get_final_cover_image(conn, book_slug="nonexistent") is None

    def test_scoped_to_book_slug(self, conn):
        upsert_cover_image(conn, book_slug="book-one", filename="book1-final.png", is_final=True)
        upsert_cover_image(conn, book_slug="book-two", filename="book2-final.png", is_final=True)
        assert get_final_cover_image(conn, book_slug="book-one") == "book1-final.png"
        assert get_final_cover_image(conn, book_slug="book-two") == "book2-final.png"

    def test_marking_one_under_specified_books_final_does_not_affect_the_other(self, conn):
        """#558 companion to the upsert-side collision test: re-importing a
        final cover for one book_num=1 book must not clear the other
        under-specified book's final flag."""
        upsert_cover_image(conn, book_slug="book-one", filename="cover.png", is_final=True)
        upsert_cover_image(conn, book_slug="book-two", filename="cover.png", is_final=True)

        upsert_cover_image(conn, book_slug="book-one", filename="new-cover.png", is_final=True)

        assert get_final_cover_image(conn, book_slug="book-one") == "new-cover.png"
        assert get_final_cover_image(conn, book_slug="book-two") == "cover.png"


class TestListCoverImages:
    def test_lists_all_for_book(self, conn):
        upsert_cover_image(conn, book_slug="firelight", filename="a.png", is_final=False)
        upsert_cover_image(conn, book_slug="firelight", filename="b.png", is_final=True)
        result = list_cover_images(conn, book_slug="firelight")
        filenames = {r["filename"] for r in result}
        assert filenames == {"a.png", "b.png"}

    def test_returns_empty_list_for_book_with_none(self, conn):
        assert list_cover_images(conn, book_slug="firelight") == []

    def test_result_dicts_have_required_keys(self, conn):
        upsert_cover_image(conn, book_slug="firelight", filename="a.png", is_final=False)
        result = list_cover_images(conn, book_slug="firelight")
        assert {"filename", "is_final", "imported_at"} <= result[0].keys()

    def test_same_second_batch_orders_by_id_desc_not_insertion_order(self, conn):
        """#556 M-2: SQLite's CURRENT_TIMESTAMP has 1-second resolution, so
        a batch of imports landing within the same second degrades
        imported_at-only ordering to insertion order — the opposite of
        newest-first. Force all rows to an identical timestamp so this
        test is deterministic regardless of how fast it actually runs, and
        assert id DESC (monotonically increasing) breaks the tie correctly."""
        upsert_cover_image(conn, book_slug="firelight", filename="a.png", is_final=False)
        upsert_cover_image(conn, book_slug="firelight", filename="b.png", is_final=False)
        upsert_cover_image(conn, book_slug="firelight", filename="c.png", is_final=False)
        conn.execute("UPDATE cover_images SET imported_at = '2026-01-01 00:00:00' WHERE book_slug = 'firelight'")
        conn.commit()

        result = list_cover_images(conn, book_slug="firelight")

        assert [r["filename"] for r in result] == ["c.png", "b.png", "a.png"]

    def test_scoped_to_book_slug_not_book_num(self, conn):
        upsert_cover_image(conn, book_slug="book-one", filename="a.png", is_final=False)
        upsert_cover_image(conn, book_slug="book-two", filename="b.png", is_final=False)

        assert [r["filename"] for r in list_cover_images(conn, book_slug="book-one")] == ["a.png"]
        assert [r["filename"] for r in list_cover_images(conn, book_slug="book-two")] == ["b.png"]


class TestOneCoverFinalPerBookSchemaInvariant:
    """#556 L-1: the one-final-per-book invariant is now enforced at the
    schema level (a partial unique index), not just by upsert_cover_image()'s
    application-level clear-then-insert. Scoped to book_slug (#558), not
    book_num."""

    def test_direct_sql_insert_of_second_final_row_is_rejected(self, conn):
        upsert_cover_image(conn, book_slug="firelight", filename="a.png", is_final=True)

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO cover_images (book_slug, filename, is_final) VALUES (?, ?, ?)",
                ("firelight", "b.png", 1),
            )

    def test_second_final_row_is_permitted_for_a_different_book(self, conn):
        upsert_cover_image(conn, book_slug="book-one", filename="a.png", is_final=True)
        # Must not raise — the index is scoped to book_slug, not global.
        upsert_cover_image(conn, book_slug="book-two", filename="b.png", is_final=True)

    def test_get_final_cover_image_picks_most_recent_if_invariant_ever_broken(self, conn):
        """Defense in depth (#556 L-1): if the schema-level index were ever
        absent (e.g. a pre-migration DB) and two rows ended up marked
        final, get_final_cover_image() must return the most recently
        imported one rather than an arbitrary row from an unordered
        LIMIT 1."""
        conn.execute("DROP INDEX idx_ci_one_final")
        conn.execute(
            "INSERT INTO cover_images (book_slug, filename, is_final, imported_at) VALUES (?, ?, ?, ?)",
            ("firelight", "older.png", 1, "2020-01-01 00:00:00"),
        )
        conn.execute(
            "INSERT INTO cover_images (book_slug, filename, is_final, imported_at) VALUES (?, ?, ?, ?)",
            ("firelight", "newer.png", 1, "2025-01-01 00:00:00"),
        )
        conn.commit()

        assert get_final_cover_image(conn, book_slug="firelight") == "newer.png"


class _FlakyConn:
    """Wraps a real sqlite3.Connection; the Nth execute() call raises,
    everything else (including the with-statement transaction protocol)
    passes through to the real connection unchanged."""

    def __init__(self, real: sqlite3.Connection, fail_on_call: int):
        self._real = real
        self._fail_on_call = fail_on_call
        self._calls = 0

    def execute(self, sql, params=()):
        self._calls += 1
        if self._calls == self._fail_on_call:
            raise sqlite3.IntegrityError("simulated failure")
        return self._real.execute(sql, params)

    def __enter__(self):
        self._real.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._real.__exit__(exc_type, exc, tb)


class TestUpsertCoverImageAtomicity:
    """#556 L-3: the UPDATE (clear other final flags) + INSERT pair must be
    one atomic transaction — a failure partway through must not leave the
    book with the old final flag cleared but no new one set."""

    def test_insert_failure_after_clearing_final_rolls_back_the_clear(self, conn):
        upsert_cover_image(conn, book_slug="firelight", filename="existing-final.png", is_final=True)

        flaky = _FlakyConn(conn, fail_on_call=2)  # the INSERT, after the UPDATE already ran
        with pytest.raises(sqlite3.IntegrityError):
            upsert_cover_image(flaky, book_slug="firelight", filename="new-final.png", is_final=True)

        assert get_final_cover_image(conn, book_slug="firelight") == "existing-final.png"
