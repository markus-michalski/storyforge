"""Tests for SQLite schema — Issue #280.

Verifies that ensure_schema() creates the canonical tables and indexes,
and that repeated calls are idempotent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.db.connection import ensure_schema, open_db


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


class TestEnsureSchema:
    def test_creates_db_file(self, db_path: Path):
        conn = open_db(db_path)
        ensure_schema(conn)
        conn.close()
        assert db_path.exists()

    def test_canon_facts_table_exists(self, db_path: Path):
        conn = open_db(db_path)
        ensure_schema(conn)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert "canon_facts" in tables

    def test_sessions_table_exists(self, db_path: Path):
        conn = open_db(db_path)
        ensure_schema(conn)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert "sessions" in tables

    def test_canon_facts_has_required_columns(self, db_path: Path):
        conn = open_db(db_path)
        ensure_schema(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(canon_facts)")}
        conn.close()
        assert {"id", "book_num", "chapter_num", "subject", "fact", "is_revision",
                "old_value", "revision_impacts", "created_at"} <= cols

    def test_sessions_has_required_columns(self, db_path: Path):
        conn = open_db(db_path)
        ensure_schema(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
        conn.close()
        assert {"user_id", "current_book_slug", "current_chapter",
                "next_beat", "notes", "last_updated"} <= cols

    def test_idempotent_schema_creation(self, db_path: Path):
        conn = open_db(db_path)
        ensure_schema(conn)
        ensure_schema(conn)  # must not raise
        conn.close()

    def test_indexes_created(self, db_path: Path):
        conn = open_db(db_path)
        ensure_schema(conn)
        indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        conn.close()
        assert "idx_cf" in indexes
        assert "idx_cf_subject" in indexes


# ---------------------------------------------------------------------------
# get_canon_db_path — slug validation (Issue #323)
# ---------------------------------------------------------------------------


class TestGetCanonDbPathSlugValidation:
    """Issue #323 — get_canon_db_path() must reject traversal slugs."""

    def test_valid_slug_returns_path(self):
        from tools.db.connection import get_canon_db_path

        path = get_canon_db_path("my-series")
        assert path.name == "my-series.db"

    def test_rejects_dotdot_traversal(self):
        import pytest

        from tools.db.connection import get_canon_db_path

        with pytest.raises(ValueError, match="Invalid"):
            get_canon_db_path("../../.bashrc")

    def test_rejects_slash_in_slug(self):
        import pytest

        from tools.db.connection import get_canon_db_path

        with pytest.raises(ValueError, match="Invalid"):
            get_canon_db_path("good/evil")

    def test_rejects_backslash_in_slug(self):
        import pytest

        from tools.db.connection import get_canon_db_path

        with pytest.raises(ValueError, match="Invalid"):
            get_canon_db_path("good\\evil")

    def test_rejects_null_byte(self):
        import pytest

        from tools.db.connection import get_canon_db_path

        with pytest.raises(ValueError, match="Invalid"):
            get_canon_db_path("slug\x00evil")

    def test_empty_slug_passes_through(self):
        # _validate_slug treats empty as a no-op sentinel used by callers
        from tools.db.connection import get_canon_db_path

        path = get_canon_db_path("")
        assert path.name == ".db"


# ---------------------------------------------------------------------------
# STORYFORGE_DB_DIR validation (Issue #329)
# ---------------------------------------------------------------------------


class TestStoryforgeDbDirValidation:
    """Issue #329 — STORYFORGE_DB_DIR must be sanitized against traversal."""

    def test_valid_tmp_path_accepted(self, tmp_path: Path):
        import importlib
        import sys

        env = {**__import__("os").environ, "STORYFORGE_DB_DIR": str(tmp_path)}
        result = __import__("subprocess").run(
            [sys.executable, "-c",
             "from tools.db.connection import DB_DIR; print(DB_DIR)"],
            capture_output=True, text=True,
            cwd="/home/markus/projekte/storyforge",
            env=env,
        )
        assert result.returncode == 0, result.stderr
        assert str(tmp_path) in result.stdout

    def test_dotdot_traversal_rejected(self, tmp_path: Path):
        import sys
        env = {**__import__("os").environ, "STORYFORGE_DB_DIR": "/tmp/../etc/evil"}
        result = __import__("subprocess").run(
            [sys.executable, "-c", "from tools.db.connection import DB_DIR"],
            capture_output=True, text=True,
            cwd="/home/markus/projekte/storyforge",
            env=env,
        )
        assert result.returncode != 0
        assert "invalid path components" in result.stderr
