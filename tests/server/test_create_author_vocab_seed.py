"""Tests for create_author's default banned-word seeding — Issue #639.

create_author used to write ~20 default banned words only into the
author's vocabulary.md ("## Banned Words"). Since Issue #604, the hook
and the manuscript checker read author vocabulary from the
author_discoveries DB (tools/banlist_loader.load_author_vocab), not the
file — so those defaults were inert until scripts/migrate_vocabulary_to_db.py
was run by hand. These tests confirm the defaults land in the DB directly
at creation time, enforceable from the start.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.authors import create_author


@pytest.fixture
def authors_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Stand up a config pointing at tmp dirs, with no author yet.

    Also patches tools.db.connection.DB_DIR so authors.db lands in tmp_path.
    """
    content_root = tmp_path / "books"
    content_root.mkdir()
    authors_root = tmp_path / "authors"
    authors_root.mkdir()

    config = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(authors_root),
        },
    }
    monkeypatch.setattr(_app, "load_config", lambda: config)
    _app._cache.invalidate()

    import tools.db.connection as conn_mod

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(conn_mod, "DB_DIR", db_dir)

    return {"config": config, "authors_root": authors_root, "db_dir": db_dir}


def _open_authors_db(authors_setup: dict):
    from tools.db.connection import ensure_authors_schema, open_db

    db_path = authors_setup["db_dir"] / "authors.db"
    conn = open_db(db_path)
    ensure_authors_schema(conn)
    return conn


class TestCreateAuthorSeedsVocabInDb:
    def test_default_banned_words_land_in_author_discoveries(self, authors_setup):
        result = json.loads(create_author(name="Ethan Cole"))
        assert result["success"] is True

        conn = _open_authors_db(authors_setup)
        rows = conn.execute(
            "SELECT text FROM author_discoveries WHERE author_slug='ethan-cole' AND discovery_type='donts'"
        ).fetchall()
        conn.close()
        texts = {row["text"] for row in rows}
        from routers.authors import _DEFAULT_BANNED_WORDS

        assert texts == set(_DEFAULT_BANNED_WORDS)

    def test_seeded_entries_are_enforceable_via_load_author_vocab(self, authors_setup):
        """The actual gap #639 reported: writing the word to a file the hook
        no longer reads produces no finding. Ground this in the real
        enforcement path, not just a DB row existing.
        """
        create_author(name="Ethan Cole")

        from tools.banlist_loader import load_author_vocab

        patterns = load_author_vocab("ethan-cole", storyforge_home=authors_setup["db_dir"].parent)
        labels = {p.label for p in patterns}
        assert "delve" in labels

    def test_db_failure_does_not_strand_the_author(self, authors_setup, monkeypatch):
        """A DB error during seeding must not raise out of the tool: the
        author directory already exists, so a retry would only hit
        "already exists". The result carries a warning instead.
        """
        import sqlite3

        import routers.authors as authors_mod

        def boom(*args, **kwargs):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(authors_mod, "insert_discovery", boom)
        result = json.loads(create_author(name="Ethan Cole"))
        assert result["success"] is True
        assert "not fully seeded" in result["warning"]
        assert (Path(result["path"]) / "profile.md").is_file()

    def test_navigate_is_not_seeded(self, authors_setup):
        """Only metaphorical "navigate" is an AI tell, but the matcher also
        hits "navigation"/"navigator" — a flat ban can't tell them apart.
        """
        create_author(name="Ethan Cole")
        conn = _open_authors_db(authors_setup)
        rows = conn.execute(
            "SELECT text FROM author_discoveries WHERE author_slug='ethan-cole' AND text LIKE 'navigate%'"
        ).fetchall()
        conn.close()
        assert rows == []

    def test_vocabulary_md_no_longer_lists_a_stale_static_banned_words_section(self, authors_setup):
        """The file previously duplicated the DB-backed list as a static
        bullet list with no mechanism to stay in sync — a word removed
        from the DB later would still show here as if still banned.
        """
        result = json.loads(create_author(name="Ethan Cole"))
        vocab_path = Path(result["path"]) / "vocabulary.md"
        text = vocab_path.read_text(encoding="utf-8")
        assert "- delve" not in text
