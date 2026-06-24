"""Tests for write_author_discovery + write_author_banned_phrase MCP tools — Issue #281.

Phase 3 rewrite: discoveries and banned phrases now write to author_discoveries
in SQLite (authors.db) instead of profile.md / vocabulary.md. profile.md still
exists for author-existence validation; vocabulary.md is no longer written to.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.authors import (
    write_author_banned_phrase,
    write_author_discovery,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def author_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Stand up a config pointing at tmp dirs, with a minimal ethan-cole profile.

    Also patches tools.db.connection.DB_DIR so authors.db lands in tmp_path.
    """
    content_root = tmp_path / "books"
    content_root.mkdir()
    authors_root = tmp_path / "authors"
    authors_root.mkdir()
    author_dir = authors_root / "ethan-cole"
    author_dir.mkdir()

    # profile.md still required for author-existence check
    (author_dir / "profile.md").write_text(
        '---\nname: "Ethan Cole"\nslug: "ethan-cole"\n---\n\n# Ethan Cole\n',
        encoding="utf-8",
    )

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

    return {"config": config, "author_dir": author_dir, "db_dir": db_dir}


def _open_authors_db(author_setup: dict):
    """Open the test authors DB directly for assertion."""
    from tools.db.connection import ensure_authors_schema, open_db
    db_path = author_setup["db_dir"] / "authors.db"
    conn = open_db(db_path)
    ensure_authors_schema(conn)
    return conn


# ---------------------------------------------------------------------------
# write_author_discovery
# ---------------------------------------------------------------------------


class TestWriteAuthorDiscovery:
    def test_inserts_recurring_tic_into_db(self, author_setup):
        result = json.loads(
            write_author_discovery(
                author_slug="ethan-cole",
                section="recurring_tics",
                text='**"thing"** — concretize on sight.',
                book_slug="firelight",
                year_month="2026-05",
            )
        )
        assert result["written"] is True

        conn = _open_authors_db(author_setup)
        rows = conn.execute(
            "SELECT * FROM author_discoveries WHERE author_slug='ethan-cole'"
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0]["discovery_type"] == "recurring_tics"
        assert '**"thing"**' in rows[0]["text"]
        assert rows[0]["book_slug"] == "firelight"
        assert rows[0]["date_added"] == "2026-05"

    def test_idempotent_returns_already_present(self, author_setup):
        write_author_discovery(
            author_slug="ethan-cole",
            section="recurring_tics",
            text='**"thing"** — concretize.',
            book_slug="firelight",
            year_month="2026-05",
        )
        result = json.loads(
            write_author_discovery(
                author_slug="ethan-cole",
                section="recurring_tics",
                text='**"thing"** — concretize.',
                book_slug="firelight",
                year_month="2026-05",
            )
        )
        assert result["written"] is False
        assert result.get("already_present") is True

        conn = _open_authors_db(author_setup)
        count = conn.execute("SELECT COUNT(*) FROM author_discoveries").fetchone()[0]
        conn.close()
        assert count == 1

    def test_invalid_section_returns_error(self, author_setup):
        result = json.loads(
            write_author_discovery(
                author_slug="ethan-cole",
                section="bogus",
                text="x",
                book_slug="firelight",
                year_month="2026-05",
            )
        )
        assert "error" in result

    def test_unknown_author_returns_error(self, author_setup):
        result = json.loads(
            write_author_discovery(
                author_slug="ghost-author",
                section="recurring_tics",
                text="x",
                book_slug="firelight",
                year_month="2026-05",
            )
        )
        assert "error" in result

    def test_year_month_stored_as_date_added(self, author_setup):
        write_author_discovery(
            author_slug="ethan-cole",
            section="recurring_tics",
            text='**"foo"** — concretize.',
            book_slug="firelight",
            year_month="2026-03",
        )
        conn = _open_authors_db(author_setup)
        row = conn.execute("SELECT date_added FROM author_discoveries").fetchone()
        conn.close()
        assert row["date_added"] == "2026-03"

    def test_year_month_defaults_to_current_when_omitted(self, author_setup):
        import re
        write_author_discovery(
            author_slug="ethan-cole",
            section="recurring_tics",
            text='**"bar"** — concrete.',
            book_slug="firelight",
        )
        conn = _open_authors_db(author_setup)
        row = conn.execute("SELECT date_added FROM author_discoveries").fetchone()
        conn.close()
        assert re.match(r"\d{4}-\d{2}", row["date_added"])

    def test_genres_stored_as_source_genres(self, author_setup):
        write_author_discovery(
            author_slug="ethan-cole",
            section="style_principles",
            text="Use concrete detail.",
            book_slug="firelight",
            year_month="2026-05",
            genres="shifter-romance,omega-verse",
        )
        conn = _open_authors_db(author_setup)
        row = conn.execute("SELECT source_genres FROM author_discoveries").fetchone()
        conn.close()
        assert "shifter-romance" in row["source_genres"]

    def test_example_stored_in_db(self, author_setup):
        write_author_discovery(
            author_slug="ethan-cole",
            section="style_principles",
            text="Ground emotion in sensation.",
            book_slug="firelight",
            year_month="2026-05",
            example="His knuckles were white on the rail.",
        )
        conn = _open_authors_db(author_setup)
        row = conn.execute("SELECT example FROM author_discoveries").fetchone()
        conn.close()
        assert "knuckles" in row["example"]


# ---------------------------------------------------------------------------
# write_author_discovery validate=True (Issue #218)
# ---------------------------------------------------------------------------


class TestWriteAuthorDiscoveryValidate:
    def test_validate_true_attaches_warnings_and_patterns(self, author_setup):
        result = json.loads(
            write_author_discovery(
                author_slug="ethan-cole",
                section="donts",
                text='**Never use rooms** — *The room received it.*',
                book_slug="firelight",
                year_month="2026-05",
            )
        )
        assert result["written"] is True
        assert "warnings" in result
        assert "extracted_patterns" in result
        labels = [p["label"] for p in result["extracted_patterns"]]
        assert "The room received it." in labels

    def test_validate_true_surfaces_lint_warning(self, author_setup):
        result = json.loads(
            write_author_discovery(
                author_slug="ethan-cole",
                section="donts",
                text='**Never use weather openings** — clichéd.',
                book_slug="firelight",
                year_month="2026-05",
            )
        )
        assert result["written"] is True
        codes = [w["code"] for w in result["warnings"]]
        assert "scanner_extracts_nothing" in codes

    def test_validate_false_omits_warnings_and_patterns(self, author_setup):
        result = json.loads(
            write_author_discovery(
                author_slug="ethan-cole",
                section="donts",
                text='**Never use rooms** — *The room received it.*',
                book_slug="firelight",
                year_month="2026-05",
                validate=False,
            )
        )
        assert result["written"] is True
        assert "warnings" not in result
        assert "extracted_patterns" not in result

    def test_validate_true_works_for_already_present(self, author_setup):
        text = '**Never use rooms** — *The room received it.*'
        write_author_discovery(
            author_slug="ethan-cole",
            section="donts",
            text=text,
            book_slug="firelight",
            year_month="2026-05",
        )
        result = json.loads(
            write_author_discovery(
                author_slug="ethan-cole",
                section="donts",
                text=text,
                book_slug="firelight",
                year_month="2026-05",
            )
        )
        assert result["already_present"] is True
        assert "warnings" in result
        assert "extracted_patterns" in result

    def test_validate_true_recurring_tics_german_title_warns(self, author_setup):
        result = json.loads(
            write_author_discovery(
                author_slug="ethan-cole",
                section="recurring_tics",
                text=(
                    "**Abstrakte Körperteil-Anthropomorphisierung** — "
                    "Körperteil als Subjekt + vages Prädikat. Konkretisieren."
                ),
                book_slug="firelight",
                year_month="2026-05",
            )
        )
        codes = [w["code"] for w in result["warnings"]]
        assert "bold_title_unscannable" in codes

    def test_validate_true_style_principles_no_scanner_warnings(self, author_setup):
        result = json.loads(
            write_author_discovery(
                author_slug="ethan-cole",
                section="style_principles",
                text='**No purple prose** — avoid lush descriptions.',
                book_slug="firelight",
                year_month="2026-05",
            )
        )
        codes = [w["code"] for w in result["warnings"]]
        assert "scanner_extracts_nothing" not in codes
        assert result["extracted_patterns"] == []


# ---------------------------------------------------------------------------
# write_author_banned_phrase — now goes to author_discoveries (type='donts')
# ---------------------------------------------------------------------------


class TestWriteAuthorBannedPhrase:
    def test_inserts_banned_phrase_into_db(self, author_setup):
        result = json.loads(
            write_author_banned_phrase(
                author_slug="ethan-cole",
                phrase="thing",
                reason="vague-noun fallback",
            )
        )
        assert result["written"] is True

        conn = _open_authors_db(author_setup)
        rows = conn.execute(
            "SELECT * FROM author_discoveries WHERE discovery_type='donts'"
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        assert "thing" in rows[0]["text"]

    def test_idempotent_already_present(self, author_setup):
        write_author_banned_phrase(author_slug="ethan-cole", phrase="delve", reason="AI tell")
        result = json.loads(
            write_author_banned_phrase(author_slug="ethan-cole", phrase="delve", reason="AI tell")
        )
        assert result["written"] is False

    def test_unknown_author_returns_error(self, author_setup):
        result = json.loads(
            write_author_banned_phrase(
                author_slug="ghost-author",
                phrase="thing",
                reason="x",
            )
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# Cache invalidation — both tools must invalidate
# ---------------------------------------------------------------------------


class TestCacheInvalidation:
    def test_discovery_write_invalidates_cache(self, author_setup, monkeypatch):
        from routers._app import _cache

        invalidate_called = {"count": 0}
        original = _cache.invalidate

        def spy() -> None:
            invalidate_called["count"] += 1
            original()

        monkeypatch.setattr(_cache, "invalidate", spy)
        write_author_discovery(
            author_slug="ethan-cole",
            section="recurring_tics",
            text='**"thing"** — concretize.',
            book_slug="firelight",
            year_month="2026-05",
        )
        assert invalidate_called["count"] >= 1

    def test_banned_phrase_write_invalidates_cache(self, author_setup, monkeypatch):
        from routers._app import _cache

        invalidate_called = {"count": 0}
        original = _cache.invalidate

        def spy() -> None:
            invalidate_called["count"] += 1
            original()

        monkeypatch.setattr(_cache, "invalidate", spy)
        write_author_banned_phrase(
            author_slug="ethan-cole",
            phrase="thing",
            reason="vague-noun fallback",
        )
        assert invalidate_called["count"] >= 1
