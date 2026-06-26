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
