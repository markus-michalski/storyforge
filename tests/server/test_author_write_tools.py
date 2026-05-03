"""Tests for ``write_author_discovery`` + ``write_author_banned_phrase`` MCP
tools (Issue #151 follow-up).

The harvest skill needs MCP tools (not raw Python calls) to write into the
author profile so that:

- The state cache gets invalidated after each write.
- The skill walks ONE call surface for both promotion paths.
- The chapter-writer/reviewer ``get_author()`` consumers see fresh data
  immediately, without a Claude-Code session restart.
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


@pytest.fixture
def author_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Stand up a config that points at a temp authors_root and a fresh
    profile + vocabulary for ``ethan-cole``."""
    content_root = tmp_path / "books"
    content_root.mkdir()
    authors_root = tmp_path / "authors"
    authors_root.mkdir()
    author_dir = authors_root / "ethan-cole"
    author_dir.mkdir()

    (author_dir / "profile.md").write_text(
        '---\nname: "Ethan Cole"\nslug: "ethan-cole"\n---\n\n'
        "# Ethan Cole\n\n"
        "## Writing Discoveries\n\n"
        "### Recurring Tics\n\n_Frei._\n\n"
        "### Style Principles\n\n_Frei._\n\n"
        "### Don'ts (beyond banned phrases)\n\n_Frei._\n",
        encoding="utf-8",
    )
    (author_dir / "vocabulary.md").write_text(
        "# Ethan Cole — Vocabulary\n\n## Banned Words\n\n### Absolutely Forbidden\n\n- delve\n",
        encoding="utf-8",
    )

    config = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(authors_root),
        },
    }
    monkeypatch.setattr(_app, "load_config", lambda: config)
    return {"config": config, "author_dir": author_dir}


# ---------------------------------------------------------------------------
# write_author_discovery
# ---------------------------------------------------------------------------


class TestWriteAuthorDiscovery:
    def test_appends_recurring_tic_with_origin(self, author_setup):
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
        content = (author_setup["author_dir"] / "profile.md").read_text(encoding="utf-8")
        assert '**"thing"**' in content
        assert "_(emerged from firelight, 2026-05)_" in content

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

    def test_year_month_defaults_to_today_when_omitted(self, author_setup):
        result = json.loads(
            write_author_discovery(
                author_slug="ethan-cole",
                section="recurring_tics",
                text='**"foo"** — concretize.',
                book_slug="firelight",
            )
        )
        assert result["written"] is True
        # Some year-month tag must be in the file now.
        content = (author_setup["author_dir"] / "profile.md").read_text(encoding="utf-8")
        import re

        assert re.search(r"_\(emerged from firelight, \d{4}-\d{2}\)_", content)


# ---------------------------------------------------------------------------
# write_author_banned_phrase
# ---------------------------------------------------------------------------


class TestWriteAuthorBannedPhrase:
    def test_appends_phrase_to_vocabulary(self, author_setup):
        result = json.loads(
            write_author_banned_phrase(
                author_slug="ethan-cole",
                phrase="thing",
                reason="vague-noun fallback",
            )
        )
        assert result["written"] is True
        content = (author_setup["author_dir"] / "vocabulary.md").read_text(encoding="utf-8")
        assert "thing" in content

    def test_idempotent_already_present(self, author_setup):
        # `delve` is in the fixture vocabulary already.
        result = json.loads(
            write_author_banned_phrase(
                author_slug="ethan-cole",
                phrase="delve",
                reason="generic AI tell",
            )
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
# Cache invalidation — both tools must invalidate so subsequent get_author()
# reflects the write.
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
