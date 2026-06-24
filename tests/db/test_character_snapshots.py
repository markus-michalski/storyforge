"""Tests for character_snapshots CRUD — Issue #281."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.db.character_snapshots import (
    get_all_latest_snapshots,
    get_latest_snapshot,
    get_latest_snapshot_for_book,
    upsert_snapshot,
)
from tools.db.connection import ensure_schema, open_db


@pytest.fixture
def conn(tmp_path: Path):
    db = open_db(tmp_path / "series.db")
    ensure_schema(db)
    yield db
    db.close()


class TestUpsertSnapshot:
    def test_inserts_basic_snapshot(self, conn):
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=5,
                        inventory=["sword", "shield"])
        row = conn.execute("SELECT inventory FROM character_snapshots WHERE char_slug='kael'").fetchone()
        assert row is not None
        import json
        assert json.loads(row["inventory"]) == ["sword", "shield"]

    def test_replaces_snapshot_for_same_key(self, conn):
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=5,
                        inventory=["old-item"])
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=5,
                        inventory=["new-item"])
        count = conn.execute("SELECT COUNT(*) FROM character_snapshots").fetchone()[0]
        assert count == 1
        import json
        row = conn.execute("SELECT inventory FROM character_snapshots").fetchone()
        assert json.loads(row["inventory"]) == ["new-item"]

    def test_stores_all_fields(self, conn):
        upsert_snapshot(
            conn,
            char_slug="kael",
            book_num=1,
            chapter_num=10,
            injuries=["bruised ribs"],
            clothing=["tactical jacket"],
            inventory=["compass"],
            altered_states=["sleep-deprived"],
            environmental_limiters="no phone signal",
        )
        import json
        row = conn.execute("SELECT * FROM character_snapshots").fetchone()
        assert json.loads(row["injuries"]) == ["bruised ribs"]
        assert json.loads(row["clothing"]) == ["tactical jacket"]
        assert json.loads(row["inventory"]) == ["compass"]
        assert json.loads(row["altered_states"]) == ["sleep-deprived"]
        assert row["environmental_limiters"] == "no phone signal"

    def test_empty_lists_stored_correctly(self, conn):
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=1,
                        inventory=[], injuries=[])
        import json
        row = conn.execute("SELECT inventory, injuries FROM character_snapshots").fetchone()
        assert json.loads(row["inventory"]) == []
        assert json.loads(row["injuries"]) == []

    def test_partial_update_merges_with_existing(self, conn):
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=5,
                        inventory=["compass"], clothing=["jacket"])
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=6,
                        injuries=["bruised ribs"])
        import json
        row = conn.execute(
            "SELECT * FROM character_snapshots WHERE chapter_num=6"
        ).fetchone()
        assert json.loads(row["inventory"]) == ["compass"]
        assert json.loads(row["clothing"]) == ["jacket"]
        assert json.loads(row["injuries"]) == ["bruised ribs"]

    def test_multiple_characters_stored_independently(self, conn):
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=3, inventory=["sword"])
        upsert_snapshot(conn, char_slug="lyra", book_num=1, chapter_num=3, inventory=["bow"])
        count = conn.execute("SELECT COUNT(*) FROM character_snapshots").fetchone()[0]
        assert count == 2


class TestGetLatestSnapshot:
    def test_returns_none_for_unknown_character(self, conn):
        assert get_latest_snapshot(conn, "nobody") is None

    def test_returns_latest_chapter(self, conn):
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=5, inventory=["old"])
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=10, inventory=["new"])
        snap = get_latest_snapshot(conn, "kael")
        assert snap is not None
        assert snap["inventory"] == ["new"]

    def test_latest_across_books(self, conn):
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=30, inventory=["b1-item"])
        upsert_snapshot(conn, char_slug="kael", book_num=2, chapter_num=1, inventory=["b2-item"])
        snap = get_latest_snapshot(conn, "kael")
        assert snap["inventory"] == ["b2-item"]
        assert snap["book_num"] == 2

    def test_list_fields_decoded_as_python_lists(self, conn):
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=1,
                        injuries=["cut hand"], clothing=["coat"])
        snap = get_latest_snapshot(conn, "kael")
        assert isinstance(snap["injuries"], list)
        assert isinstance(snap["clothing"], list)
        assert snap["injuries"] == ["cut hand"]


class TestGetLatestSnapshotForBook:
    def test_returns_latest_within_book(self, conn):
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=5, inventory=["ch5"])
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=10, inventory=["ch10"])
        upsert_snapshot(conn, char_slug="kael", book_num=2, chapter_num=1, inventory=["b2"])
        snap = get_latest_snapshot_for_book(conn, "kael", book_num=1)
        assert snap["inventory"] == ["ch10"]
        assert snap["chapter_num"] == 10

    def test_returns_none_if_no_snapshots_for_book(self, conn):
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=1, inventory=["x"])
        assert get_latest_snapshot_for_book(conn, "kael", book_num=2) is None


class TestGetAllLatestSnapshots:
    def test_returns_one_per_character(self, conn):
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=5, inventory=["sword"])
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=10, inventory=["dagger"])
        upsert_snapshot(conn, char_slug="lyra", book_num=1, chapter_num=3, inventory=["bow"])

        snaps = get_all_latest_snapshots(conn)
        assert len(snaps) == 2
        by_slug = {s["char_slug"]: s for s in snaps}
        assert by_slug["kael"]["inventory"] == ["dagger"]
        assert by_slug["lyra"]["inventory"] == ["bow"]

    def test_returns_empty_list_when_no_snapshots(self, conn):
        assert get_all_latest_snapshots(conn) == []

    def test_picks_highest_book_and_chapter(self, conn):
        upsert_snapshot(conn, char_slug="kael", book_num=1, chapter_num=30, inventory=["b1"])
        upsert_snapshot(conn, char_slug="kael", book_num=2, chapter_num=1, inventory=["b2"])
        snaps = get_all_latest_snapshots(conn)
        assert snaps[0]["inventory"] == ["b2"]
