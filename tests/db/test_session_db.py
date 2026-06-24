"""Tests for DB-backed session storage — Issue #280."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.db.connection import ensure_schema, open_db
from tools.db.sessions import get_session_from_db, update_session_in_db

USER_ID = "local"


@pytest.fixture
def conn(tmp_path: Path):
    db = open_db(tmp_path / "sessions.db")
    ensure_schema(db)
    yield db
    db.close()


class TestSessionDb:
    def test_get_session_returns_empty_dict_when_no_row_and_no_legacy(self, conn, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.shared.config.STATE_PATH", tmp_path / "nonexistent.json")
        result = get_session_from_db(conn, USER_ID)
        assert result == {}

    def test_get_session_returns_empty_dict_when_no_row(self, conn):
        result = get_session_from_db(conn, USER_ID)
        assert result == {}

    def test_update_then_get_roundtrip(self, conn):
        update_session_in_db(conn, USER_ID, last_book="firelight", last_chapter="30-the-hunt")
        result = get_session_from_db(conn, USER_ID)
        assert result["last_book"] == "firelight"
        assert result["last_chapter"] == "30-the-hunt"

    def test_partial_update_preserves_other_fields(self, conn):
        update_session_in_db(conn, USER_ID, last_book="firelight", active_author="ethan-cole")
        update_session_in_db(conn, USER_ID, last_chapter="31-the-reckoning")
        result = get_session_from_db(conn, USER_ID)
        assert result["last_book"] == "firelight"
        assert result["active_author"] == "ethan-cole"
        assert result["last_chapter"] == "31-the-reckoning"

    def test_update_overwrites_existing_value(self, conn):
        update_session_in_db(conn, USER_ID, last_book="firelight")
        update_session_in_db(conn, USER_ID, last_book="embers")
        result = get_session_from_db(conn, USER_ID)
        assert result["last_book"] == "embers"

    def test_empty_string_fields_are_not_stored(self, conn):
        update_session_in_db(conn, USER_ID, last_book="firelight", last_chapter="")
        result = get_session_from_db(conn, USER_ID)
        assert "last_chapter" not in result or result["last_chapter"] == ""
