"""Pytest configuration for StoryForge tests."""

import sqlite3
import sys
from pathlib import Path

import pytest

# Add tools and hooks to Python path for imports
plugin_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(plugin_root / "tools"))
sys.path.insert(0, str(plugin_root))

# The MCP server directory has a hyphen in its name, which is not a valid Python
# module identifier. Add it directly to sys.path so tests can import it as "server".
sys.path.insert(0, str(plugin_root / "servers" / "storyforge-server"))

# When running with the system pytest (not the venv's pytest), mcp and other
# dependencies may be missing. Inject the plugin venv's site-packages so that
# `pytest -q` from the project root works regardless of which Python is active.
_venv_site = Path.home() / ".storyforge" / "venv" / "lib" / "python3.12" / "site-packages"
if _venv_site.is_dir() and str(_venv_site) not in sys.path:
    sys.path.insert(0, str(_venv_site))


@pytest.fixture(autouse=True)
def _isolate_db_dir(tmp_path, monkeypatch):
    """Redirect ``tools.db.connection.DB_DIR`` to a per-test tmp dir by default.

    Safety net for Issue #407: a test reaching a DB-backed loader without its
    own explicit ``DB_DIR`` redirect used to silently create/write to the
    real ``~/.storyforge/db/`` on the developer's machine. Tests that need a
    specific ``DB_DIR`` still override it explicitly (their own fixture runs
    after this one and wins).
    """
    import tools.db.connection as _db_conn

    monkeypatch.setattr(_db_conn, "DB_DIR", tmp_path / "db")


@pytest.fixture
def seed_author_discoveries():
    """Factory fixture: seed ``author_discoveries`` DB entries for a test.

    Returns a callable ``(storyforge_home, slug, discovery_type, texts)`` that
    creates the authors.db at ``storyforge_home/db/`` with the full production
    schema and inserts one row per text entry.

    Usage::

        def test_something(self, tmp_path, patch_storyforge_home, seed_author_discoveries):
            seed_author_discoveries(patch_storyforge_home, "ethan-cole", "donts",
                                    ["**Never use rooms** — *The room received it.*"])
    """

    def _seed(
        storyforge_home: Path,
        slug: str,
        discovery_type: str,
        texts: list,
    ) -> None:
        db_dir = storyforge_home / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(db_dir / "authors.db")) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS author_discoveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author_slug TEXT NOT NULL,
                    discovery_type TEXT NOT NULL,
                    text TEXT NOT NULL,
                    book_slug TEXT DEFAULT '',
                    source_genres TEXT DEFAULT '',
                    universal BOOLEAN DEFAULT FALSE,
                    example TEXT DEFAULT '',
                    date_added TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(author_slug, discovery_type, text)
                )
                """
            )
            for text in texts:
                conn.execute(
                    "INSERT OR IGNORE INTO author_discoveries "
                    "(author_slug, discovery_type, text) VALUES (?, ?, ?)",
                    (slug, discovery_type, text),
                )

    return _seed
