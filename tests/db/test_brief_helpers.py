"""Tests for brief_helpers.py — C1/H1 regression guard (Issue #280)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.db.brief_helpers import load_canon_facts_for_brief
from tools.db.canon_facts import insert_fact
from tools.db.connection import open_canon_db
import tools.db.connection as _db_conn


@pytest.fixture
def db_dir(tmp_path: Path) -> Path:
    d = tmp_path / "db"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def patch_db_dir(db_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)


def _make_book(tmp_path: Path, slug: str, series: str = "", series_number: int = 1) -> Path:
    book_dir = tmp_path / slug
    book_dir.mkdir(parents=True)
    readme = (
        f"---\ntitle: {slug}\nslug: {slug}\n"
        f"series: \"{series}\"\nseries_number: {series_number}\n---\n\n# {slug}\n"
    )
    (book_dir / "README.md").write_text(readme, encoding="utf-8")
    return book_dir


class TestLoadCanonFactsForBrief:
    def test_returns_empty_when_db_empty_and_no_markdown(self, tmp_path: Path):
        book_dir = _make_book(tmp_path, "standalone")
        result = load_canon_facts_for_brief(book_dir)
        assert result == []

    def test_auto_derives_book_num_for_series_book_2(self, tmp_path: Path, db_dir: Path):
        """C1 regression: book #2 must use book_num=2, not the old default of 1."""
        book_dir = _make_book(tmp_path, "embers", series="blood-and-binary", series_number=2)

        conn = open_canon_db("blood-and-binary")
        insert_fact(conn, book_num=2, chapter_num=3, subject="Lucien", fact="Lost his arm")
        conn.close()

        facts = load_canon_facts_for_brief(book_dir)
        subjects = {f["subject"] for f in facts}
        assert "Lucien" in subjects, "Book #2 facts must be visible when book_num=2"

    def test_book1_facts_visible_when_writing_book2(self, tmp_path: Path, db_dir: Path):
        """cross-book: book 1 facts must appear in book 2 context."""
        book_dir = _make_book(tmp_path, "embers", series="blood-and-binary", series_number=2)

        conn = open_canon_db("blood-and-binary")
        insert_fact(conn, book_num=1, chapter_num=30, subject="WorldFact", fact="There are two moons")
        insert_fact(conn, book_num=2, chapter_num=1, subject="NewFact", fact="City fell")
        conn.close()

        facts = load_canon_facts_for_brief(book_dir)
        subjects = {f["subject"] for f in facts}
        assert "WorldFact" in subjects
        assert "NewFact" in subjects

    def test_falls_back_to_markdown_when_db_empty(self, tmp_path: Path):
        book_dir = _make_book(tmp_path, "standalone")
        (book_dir / "plot").mkdir()
        canon_log = (
            "# Canon Log\n\n## Established Facts\n\n"
            "| Fact | Established In | Status | Notes |\n"
            "|------|---------------|--------|-------|\n"
            "| Has silver eyes | Ch 01 | ACTIVE | |\n"
        )
        (book_dir / "plot" / "canon-log.md").write_text(canon_log, encoding="utf-8")

        facts = load_canon_facts_for_brief(book_dir)
        assert len(facts) >= 1
        assert any("silver" in f.get("fact", "") or "silver" in f.get("subject", "") for f in facts)
