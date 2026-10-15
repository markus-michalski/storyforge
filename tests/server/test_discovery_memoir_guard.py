"""write_author_discovery must not carry memoir names or prose into the author profile.

Epic #663 / #668 review: an author discovery is read across all of the
author's books, so text that originates from a memoir book is checked against
the people of that book, and memoir discoveries carry no prose example.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.authors import write_author_discovery
from tools.shared.person_names import person_name_hit

BOOKS = {
    "my-life": {
        "author": "ethan-cole",
        "book_category": "memoir",
        "genres": ["memoir"],
        "people": {
            "anna": {"slug": "anna", "name": "Anna Berger", "real_name": "Anna Mueller"},
            "mom": {"slug": "mom", "name": "Mom", "real_name": ""},
        },
    },
    "firelight": {
        "author": "ethan-cole",
        "book_category": "fiction",
        "genres": ["dark-fantasy"],
        "people": {},
    },
}


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import tools.db.connection as conn_mod

    authors_root = tmp_path / "authors"
    (authors_root / "ethan-cole").mkdir(parents=True)
    (authors_root / "ethan-cole" / "profile.md").write_text(
        '---\nname: "Ethan Cole"\nslug: "ethan-cole"\n---\n\n# Ethan Cole\n', encoding="utf-8"
    )
    config = {"paths": {"content_root": str(tmp_path / "books"), "authors_root": str(authors_root)}}
    monkeypatch.setattr(_app, "load_config", lambda: config)
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(conn_mod, "DB_DIR", db_dir)
    monkeypatch.setattr(_app._cache, "get", lambda: {"books": BOOKS, "authors": {}})
    monkeypatch.setattr(_app._cache, "invalidate", lambda: None)


def _write(book_slug: str, text: str, **kw) -> dict:
    return json.loads(write_author_discovery(
        "ethan-cole", "style_principles", text, book_slug, **kw,
    ))


class TestMemoirGuard:
    def test_name_in_text_is_rejected(self, env):
        result = _write("my-life", "**Plainer speech** — Anna Mueller should sound plainer.")
        assert "error" in result and "anna" in result["error"].lower()

    def test_example_is_rejected_for_memoir(self, env):
        result = _write("my-life", "**Plainer speech** — Prefer plainer speech.",
                        example="She left without a word.")
        assert "error" in result and "example" in result["error"].lower()

    def test_clean_memoir_discovery_is_written(self, env):
        result = _write("my-life", "**Plainer speech** — Prefer plainer speech.", genres="memoir")
        assert result.get("written") is True

    def test_fiction_discovery_with_example_is_untouched(self, env):
        result = _write("firelight", "**Short sentences** — Prefer short sentences.",
                        example="He ran. She followed.", genres="dark-fantasy")
        assert result.get("written") is True

    def test_unknown_book_is_not_blocked(self, env):
        result = _write("ghost-book", "**Plainer speech** — Prefer plainer speech.")
        assert result.get("written") is True


class TestPersonNameHit:
    PEOPLE = BOOKS["my-life"]["people"]

    @pytest.mark.parametrize("text", [
        "Annas voice", "Bergers habit", "Anna_Berger", "Ánna", "Anna’s rhythm", "MUELLER",
    ])
    def test_hits(self, text):
        assert person_name_hit(text, self.PEOPLE)

    @pytest.mark.parametrize("text", [
        "Plainer wording", "Mom-style warmth", "annals of detail", "",
    ])
    def test_misses(self, text):
        assert person_name_hit(text, self.PEOPLE) is None

    def test_no_people_never_hits(self):
        assert person_name_hit("Anna", {}) is None
