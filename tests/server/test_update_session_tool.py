"""Tests for the update_session/get_session MCP tools — session clear semantics.

Companion to tests/db/test_session_db.py, which covers the underlying
update_session_in_db()/get_session_from_db() helpers directly. These tests
exercise the actual MCP-decorated functions in routers/state.py — the public
signature that changed (str = "" -> str | None = None) and the only surface
skills ever call.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.db.connection as conn_mod
from routers.state import get_session, update_session


@pytest.fixture
def isolated_session_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the global sessions DB at a fresh tmp_path for this test."""
    monkeypatch.setattr(conn_mod, "DB_DIR", tmp_path)


class TestUpdateSessionTool:
    def test_clears_active_author_end_to_end(self, isolated_session_db):
        update_session(active_author="ethan-cole")
        assert json.loads(get_session())["active_author"] == "ethan-cole"

        result = json.loads(update_session(active_author=""))
        assert result["success"] is True
        assert result["session"].get("active_author", "") == ""
        assert json.loads(get_session()).get("active_author", "") == ""

    def test_omitted_field_preserves_existing_value(self, isolated_session_db):
        update_session(last_book="firelight", active_author="ethan-cole")
        update_session(last_chapter="31-the-reckoning")

        session = json.loads(get_session())
        assert session["last_book"] == "firelight"
        assert session["active_author"] == "ethan-cole"
        assert session["last_chapter"] == "31-the-reckoning"

    def test_clearing_field_that_was_never_set_is_a_no_op_not_an_error(self, isolated_session_db):
        result = json.loads(update_session(active_author=""))
        assert result["success"] is True
        assert json.loads(get_session()).get("active_author", "") == ""
