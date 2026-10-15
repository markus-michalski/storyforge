"""End-to-end privacy check for the voice-feedback chain on memoir books.

Epic #663 / Issue #670: no names, no comment text and no before/after text from a
memoir book may reach the database file, a tool response or the author profile.
The chain under test: log_review_feedback -> list_pending_feedback ->
set_feedback_classification -> get_voice_candidates -> write_author_discovery ->
mark_feedback_harvested.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import routers._app as _app
from routers.authors import write_author_discovery
from routers.feedback import (
    discard_feedback,
    get_voice_candidates,
    list_pending_feedback,
    log_review_feedback,
    mark_feedback_harvested,
    set_feedback_classification,
)
from tools.db.connection import get_authors_db_path

SECRETS = [
    "Anna Mueller",
    "Berger",
    "Hamburg-Altona",
    "sie hat nie wieder angerufen",
    "Mueller kam am Dienstag",
]

BOOKS = {
    "my-life": {
        "author": "ethan-cole",
        "book_category": "memoir",
        "genres": ["memoir"],
        "chapters_data": {"01-home": {"number": 1}, "02-station": {"number": 2},
                          "03-kitchen": {"number": 3}},
        "people": {
            "anna": {"slug": "anna", "name": "Anna Berger", "real_name": "Anna Mueller"},
        },
    },
    "other-life": {
        "author": "ethan-cole",
        "book_category": "memoir",
        "genres": [],
        "chapters_data": {"01-x": {"number": 1}},
        "people": {"bob": {"slug": "bob", "name": "Robert Hale", "real_name": ""}},
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
    return tmp_path


def _log(book: str, chapter: str, n: int) -> dict:
    return json.loads(log_review_feedback(
        book_slug=book,
        chapter_slug=chapter,
        source_skill="reviewer",
        decision="reworked",
        comment_text=f"Anna Mueller würde das nie sagen ({n}); sie hat nie wieder angerufen.",
        before_text=f"Mueller kam am Dienstag nach Hamburg-Altona ({n}).",
        after_text="Sie kam am Dienstag.",
        proposal_text="Anna Berger kam an.",
        dimension="hedging",
        direction="less",
        normalized_rule="Cut qualifiers before a statement.",
    ))


def _db_bytes() -> bytes:
    path = get_authors_db_path()
    # Fold the WAL into the main file so the check sees everything that was written.
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    data = path.read_bytes()
    wal = Path(f"{path}-wal")
    if wal.exists():
        data += wal.read_bytes()
    return data


def _assert_clean(label: str, payload: str | bytes) -> None:
    haystack = payload.decode("utf-8", "ignore") if isinstance(payload, bytes) else payload
    for secret in SECRETS:
        assert secret.lower() not in haystack.lower(), f"{label} leaked {secret!r}"


class TestMemoirChain:
    def test_full_chain_never_exposes_raw_text_or_names(self, env):
        results = [
            _log("my-life", "01-home", 1),
            _log("my-life", "02-station", 2),
            _log("my-life", "03-kitchen", 3),
        ]
        for r in results:
            _assert_clean("log_review_feedback response", json.dumps(r))
            assert r["logged"] is True

        listed = list_pending_feedback("my-life", "03-kitchen")
        _assert_clean("list_pending_feedback", listed)
        entries = json.loads(listed)["entries"]
        assert len(entries) == 3
        for e in entries:
            assert e["comment_text"] == e["before_text"] == e["after_text"] == e["proposal_text"] == ""

        candidates = get_voice_candidates("ethan-cole", "my-life")
        _assert_clean("get_voice_candidates", candidates)
        candidate = json.loads(candidates)["candidates"][0]
        assert candidate["dimension"] == "hedging"
        assert candidate["book_category"] == "memoir"

        written = write_author_discovery(
            "ethan-cole", "style_principles",
            f"**Less hedging** — {candidate['normalized_rule']}",
            "my-life", genres="memoir", universal=False,
        )
        _assert_clean("write_author_discovery", written)
        assert json.loads(written)["written"] is True

        closed = mark_feedback_harvested("my-life", candidate["evidence_ids"])
        assert json.loads(closed)["changed"] == 3

        _assert_clean("authors.db file", _db_bytes())

    def test_rejected_calls_do_not_persist_anything(self, env):
        before = _db_bytes()
        refused = [
            # no classification: raw text would have to be stored
            log_review_feedback(
                "my-life", "01-home", "reviewer", "accepted",
                comment_text="Anna Mueller würde das nie sagen.",
                before_text="Mueller kam am Dienstag.", after_text="Sie kam.",
            ),
            # rule carries a name
            log_review_feedback(
                "my-life", "01-home", "reviewer", "accepted",
                comment_text="x", dimension="hedging", direction="less",
                normalized_rule="Anna Mueller hedges too much.",
            ),
        ]
        for response in refused:
            assert "error" in json.loads(response)
            _assert_clean("refused response", response)
        assert json.loads(list_pending_feedback("my-life"))["count"] == 0
        after = _db_bytes()
        _assert_clean("authors.db after refused calls", after)
        assert b"Mueller" not in after and before is not None

    def test_names_are_blocked_on_every_write_path(self, env):
        assert "error" in json.loads(log_review_feedback(
            "my-life", "01-home", "reviewer", "accepted", comment_text="c",
            dimension="hedging", direction="less", normalized_rule="Berger hedges.",
        ))
        _log("my-life", "01-home", 1)
        rid = json.loads(list_pending_feedback("my-life"))["entries"][0]["id"]
        assert "error" in json.loads(set_feedback_classification(
            "my-life", rid, "hedging", "less", "Less like Anna.",
        ))
        assert "error" in json.loads(write_author_discovery(
            "ethan-cole", "style_principles", "**Anna** — hedges less.", "my-life",
            genres="memoir",
        ))

    def test_other_authors_memoir_people_do_not_block_unrelated_rules(self, env):
        result = _log("other-life", "01-x", 1)
        assert result["logged"] is True

    def test_discarded_entries_stay_free_of_raw_text(self, env):
        _log("my-life", "01-home", 1)
        rid = json.loads(list_pending_feedback("my-life"))["entries"][0]["id"]
        assert json.loads(discard_feedback("my-life", [rid]))["changed"] == 1
        _assert_clean("authors.db after discard", _db_bytes())


def test_memoir_candidates_are_style_principles_tagged_memoir(env):
    for i, chapter in enumerate(["01-home", "02-station", "03-kitchen"], start=1):
        _log("my-life", chapter, i)
    candidate = json.loads(get_voice_candidates("ethan-cole", "my-life"))["candidates"][0]
    assert candidate["target_section"] == "style_principles"
    assert candidate["scope"]["universal"] is True  # engine scope; the skill writes genres="memoir"
