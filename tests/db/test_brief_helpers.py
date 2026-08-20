"""Tests for brief_helpers.py — C1/H1 regression guard (Issue #280)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.db.brief_helpers import (
    load_callbacks_for_brief,
    load_canon_facts_for_brief,
    load_changed_facts_for_brief,
    load_rules_for_brief,
)
from tools.db.book_rules import insert_rule
from tools.db.canon_facts import insert_fact
from tools.db.connection import open_canon_db
import tools.db.connection as _db_conn
from tools.state.brief_common import cap_canon_facts


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

    def test_includes_id_for_cap_canon_facts_tiebreak(self, tmp_path: Path, db_dir: Path):
        """Issue #506: brief_common.cap_canon_facts needs id (not
        created_at — see brief_helpers._db_row_to_legacy_fact's docstring
        for why: created_at has only second resolution and collides on
        same-tool-call batch inserts) to break ties between CHANGED facts
        sharing a chapter. id was queried from the DB but dropped in the
        row->legacy-fact mapping before this fix."""
        book_dir = _make_book(tmp_path, "standalone")

        conn = open_canon_db("standalone")
        insert_fact(conn, book_num=1, chapter_num=5, subject="s", fact="f")
        conn.close()

        facts = load_canon_facts_for_brief(book_dir)
        assert len(facts) == 1
        assert facts[0]["id"], "id must be present and non-zero"

    def test_same_second_batch_revisions_resolve_by_id_not_lost_to_truncation(
        self, tmp_path: Path, db_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """True end-to-end reproduction of the original #506/HIGH-1 bug: 4
        real CHANGED facts inserted for the same chapter via back-to-back
        insert_fact() calls (naturally same-second — CURRENT_TIMESTAMP has
        no sub-second resolution, so a fast test run collides exactly like
        the real same-tool-call-batch scenario) must still resolve
        correctly through the full query_facts() -> _db_row_to_legacy_fact()
        -> cap_canon_facts() pipeline via the id tiebreak, not silently fall
        back to insertion order winning by luck."""
        import tools.state.brief_common as brief_common_module

        book_dir = _make_book(tmp_path, "standalone")
        monkeypatch.setattr(brief_common_module, "CANON_FACTS_CHAR_BUDGET", 1)

        conn = open_canon_db("standalone")
        for label in ("oldest", "second", "third", "newest"):
            insert_fact(
                conn,
                book_num=1,
                chapter_num=31,
                subject="s",
                fact=f"revision-{label}",
                is_revision=True,
                old_value="prior value",
            )
        conn.close()

        facts = load_canon_facts_for_brief(book_dir)
        assert len(facts) == 4

        # Budget for exactly one entry — forces the tiebreak to matter.
        one_entry_size = len(str(facts[0])) + 1
        kept, truncated, total = cap_canon_facts(facts, char_budget=one_entry_size)
        assert truncated is True
        assert total == 4
        assert len(kept) == 1
        assert kept[0]["fact"] == "revision-newest", (
            "the most-recently-inserted same-chapter revision must survive, "
            "not whichever one happened to be inserted first"
        )

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

    def test_returns_empty_when_db_empty_no_md_fallback(self, tmp_path: Path):
        """After Issue #291: MD fallback is removed — DB-empty means empty result.

        If markdown content exists but the DB is empty, callers must migrate
        first (run migrate_canon_log_to_db.py) before facts appear here.
        Use build_canon_brief() for the chapter-writer path, which still reads
        the MD archive alongside the DB.
        """
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
        assert facts == [], "No MD fallback — empty DB must return empty list"

    def test_timeline_domain_facts_are_not_filtered(self, tmp_path: Path, db_dir: Path):
        """Issue #500: domain="timeline" is a documented first-class canon
        domain (reference/craft/chapter-writing-shared.md), not noise —
        load_canon_facts_for_brief must never filter by domain. Size bounding
        for the review brief happens downstream in brief_common.cap_canon_facts,
        which truncates transparently instead of assuming a domain is safe to drop."""
        book_dir = _make_book(tmp_path, "standalone")

        conn = open_canon_db("standalone")
        insert_fact(conn, book_num=1, chapter_num=1, subject="Theo",
                    fact="Theo is 26", domain="")
        insert_fact(conn, book_num=1, chapter_num=2, subject="general",
                    fact="Storm hits midday Saturday", domain="timeline")
        conn.close()

        facts = load_canon_facts_for_brief(book_dir)
        assert len(facts) == 2


class TestLoadChangedFactsForBrief:
    def test_returns_empty_when_db_empty(self, tmp_path: Path):
        book_dir = _make_book(tmp_path, "standalone")
        result = load_changed_facts_for_brief(book_dir)
        assert result == []

    def test_returns_only_revision_rows(self, tmp_path: Path, db_dir: Path):
        book_dir = _make_book(tmp_path, "standalone")

        conn = open_canon_db("standalone")
        insert_fact(conn, book_num=1, chapter_num=1, subject="Theo",
                    fact="Theo is 26", domain="")
        insert_fact(conn, book_num=1, chapter_num=14, subject="Lena",
                    fact="Lena eats normal food", domain="",
                    is_revision=True, old_value="Lena doesn't eat",
                    revision_impacts='["15-aftermath", "17-the-school"]')
        conn.close()

        result = load_changed_facts_for_brief(book_dir)
        assert len(result) == 1
        assert result[0]["old"] == "Lena doesn't eat"
        assert result[0]["new"] == "Lena eats normal food"
        assert result[0]["chapter"] == "14"
        assert result[0]["revision_impact"] == ["15-aftermath", "17-the-school"]

    def test_handles_missing_revision_impacts_gracefully(self, tmp_path: Path, db_dir: Path):
        book_dir = _make_book(tmp_path, "standalone")

        conn = open_canon_db("standalone")
        insert_fact(conn, book_num=1, chapter_num=4, subject="World",
                    fact="Vampires walk in daylight", domain="",
                    is_revision=True, old_value="Vampires burn in daylight")
        conn.close()

        result = load_changed_facts_for_brief(book_dir)
        assert len(result) == 1
        assert result[0]["revision_impact"] == []

    def test_auto_derives_book_num_for_series_book_2(self, tmp_path: Path, db_dir: Path):
        book_dir = _make_book(tmp_path, "embers", series="blood-and-binary", series_number=2)

        conn = open_canon_db("blood-and-binary")
        insert_fact(conn, book_num=2, chapter_num=3, subject="Lucien",
                    fact="Has one arm", domain="",
                    is_revision=True, old_value="Has two arms")
        conn.close()

        result = load_changed_facts_for_brief(book_dir)
        assert len(result) == 1

    def test_excludes_revisions_from_other_books_in_series(self, tmp_path: Path, db_dir: Path):
        """revision_impact holds chapter *slugs*, which are only unique within
        a single book. Including book 1's revisions while reviewing book 2
        risks a false stale-reference match against an unrelated same-named
        chapter (e.g. both books having a "05-aftermath")."""
        book_dir = _make_book(tmp_path, "embers", series="blood-and-binary", series_number=2)

        conn = open_canon_db("blood-and-binary")
        insert_fact(conn, book_num=1, chapter_num=5, subject="WorldFact",
                    fact="There are two moons", domain="",
                    is_revision=True, old_value="There is one moon",
                    revision_impacts='["05-aftermath"]')
        insert_fact(conn, book_num=2, chapter_num=2, subject="Lucien",
                    fact="Has one arm", domain="",
                    is_revision=True, old_value="Has two arms",
                    revision_impacts='["03-recovery"]')
        conn.close()

        result = load_changed_facts_for_brief(book_dir)
        assert len(result) == 1
        assert result[0]["new"] == "Has one arm"

    def test_non_list_revision_impacts_json_is_ignored(self, tmp_path: Path, db_dir: Path):
        """A revision_impacts column holding valid-but-non-list JSON (e.g. a
        bare string from a hand-migrated row) must not violate the documented
        list[str] contract — check 19 does 'is this slug in the list'."""
        book_dir = _make_book(tmp_path, "standalone")

        conn = open_canon_db("standalone")
        insert_fact(conn, book_num=1, chapter_num=4, subject="World",
                    fact="Vampires walk in daylight", domain="",
                    is_revision=True, old_value="Vampires burn in daylight",
                    revision_impacts='"05-aftermath"')
        conn.close()

        result = load_changed_facts_for_brief(book_dir)
        assert len(result) == 1
        assert result[0]["revision_impact"] == []


class TestUnlinkedSeriesBookDegradesGracefully:
    """Issue #579: series set but series_number=0 (never linked via
    add_book_to_series()) — get_book_num() now raises
    BookNotLinkedToSeriesError. All four brief_helpers functions promise
    "empty list if the DB is unreachable" in their own docstrings; this
    must hold for this cause too, not just sqlite/OSError causes. Each
    function's get_book_num() call was previously OUTSIDE its own try
    block, so widening that block's except tuple alone would not have
    caught it — the call itself had to move inside."""

    def test_load_canon_facts_for_brief(self, tmp_path: Path, db_dir: Path):
        book_dir = _make_book(tmp_path, "unlinked", series="my-series", series_number=0)
        conn = open_canon_db("unlinked")
        insert_fact(conn, book_num=1, chapter_num=1, subject="X", fact="should not surface")
        conn.close()

        assert load_canon_facts_for_brief(book_dir) == []

    def test_load_changed_facts_for_brief(self, tmp_path: Path, db_dir: Path):
        book_dir = _make_book(tmp_path, "unlinked", series="my-series", series_number=0)
        conn = open_canon_db("unlinked")
        insert_fact(
            conn, book_num=1, chapter_num=1, subject="X", fact="new value",
            is_revision=True, old_value="old value",
        )
        conn.close()

        assert load_changed_facts_for_brief(book_dir) == []

    def test_load_rules_for_brief(self, tmp_path: Path, db_dir: Path):
        book_dir = _make_book(tmp_path, "unlinked", series="my-series", series_number=0)
        conn = open_canon_db("unlinked")
        insert_rule(conn, book_num=1, rule_type="rule", text="Avoid `synergy`.")
        conn.close()

        assert load_rules_for_brief(book_dir) == []

    def test_load_callbacks_for_brief(self, tmp_path: Path, db_dir: Path):
        book_dir = _make_book(tmp_path, "unlinked", series="my-series", series_number=0)
        conn = open_canon_db("unlinked")
        insert_rule(conn, book_num=1, rule_type="callback", text="the locket returns")
        conn.close()

        assert load_callbacks_for_brief(book_dir) == []
