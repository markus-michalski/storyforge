"""Tests for scripts/migrate_canon_log_to_db.py — Issue #297.

Verifies that the migration script correctly handles Format B
(## Chapter NN / ### Subject: topic / bullets / **CHANGED**) for both
fiction (canon-log.md) and memoir (people-log.md).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.migrate_canon_log_to_db as migrate_canon_log_to_db
import tools.db.connection as _db_conn
from tools.db.canon_facts import insert_fact, query_facts
from tools.db.connection import get_book_num, get_db_slug_for_book, open_canon_db
from tools.state.loaders.canon_log_extractor import extract_all_facts


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _book_at(root: Path, *, category: str = "fiction") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "chapters").mkdir(exist_ok=True)
    (root / "plot").mkdir(exist_ok=True)
    (root / "characters").mkdir(exist_ok=True)
    (root / "README.md").write_text(
        f"---\ntitle: {root.name}\nslug: {root.name}\nbook_category: {category}\n---\n",
        encoding="utf-8",
    )
    return root


def _book(tmp_path: Path, slug: str = "my-book", *, category: str = "fiction") -> Path:
    return _book_at(tmp_path / slug, category=category)


def _write_log(book_root: Path, content: str, *, memoir: bool = False) -> None:
    name = "people-log.md" if memoir else "canon-log.md"
    (book_root / "plot" / name).write_text(content, encoding="utf-8")


@pytest.fixture()
def _patch_db(tmp_path, monkeypatch):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)


def _query_all(book_root: Path) -> list[dict]:
    book_num = get_book_num(book_root)
    db_slug = get_db_slug_for_book(book_root)
    conn = open_canon_db(db_slug)
    try:
        return query_facts(conn, book_num=book_num, up_to_chapter=9999)
    finally:
        conn.close()


def _run_migrate(book_root: Path) -> int:
    """Import facts from the book's log into the DB. Returns total row count."""
    book_category = "memoir" if "memoir" in (book_root / "README.md").read_text() else "fiction"
    result = extract_all_facts(book_root, book_category)
    if result["extraction_method"] == "none":
        return 0

    book_num = get_book_num(book_root)
    db_slug = get_db_slug_for_book(book_root)
    conn = open_canon_db(db_slug)
    inserted = 0
    try:
        for f in result["current_facts"]:
            insert_fact(
                conn,
                book_num=book_num,
                chapter_num=f["chapter_num"],
                subject=f["subject"],
                fact=f["fact"],
                domain=f.get("domain", ""),
            )
            inserted += 1
        for f in result["changed_facts"]:
            insert_fact(
                conn,
                book_num=book_num,
                chapter_num=f["chapter_num"],
                subject=f["subject"],
                fact=f["fact"],
                is_revision=True,
                old_value=f["old_value"] or None,
                revision_impacts=json.dumps(f["revision_impacts"]) if f["revision_impacts"] else None,
            )
            inserted += 1
    finally:
        conn.close()
    return inserted


# ---------------------------------------------------------------------------
# extract_all_facts() — unit tests for the extractor
# ---------------------------------------------------------------------------


class TestExtractAllFacts:
    def test_missing_log_returns_none(self, tmp_path):
        root = _book(tmp_path)
        result = extract_all_facts(root)

        assert result["extraction_method"] == "none"
        assert result["warnings"]
        assert not result["current_facts"]

    def test_empty_log_returns_none(self, tmp_path):
        root = _book(tmp_path)
        _write_log(root, "   \n  ")
        result = extract_all_facts(root)

        assert result["extraction_method"] == "none"

    def test_format_b_sections_extracted(self, tmp_path):
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 01 — Setup\n\n"
            "### Theo: locations\n"
            "- Lives in Berlin.\n"
            "- Works at the university.\n\n"
            "## Chapter 02 — Conflict\n\n"
            "### Kael: abilities\n"
            "- Kael can fly.\n"
        )
        result = extract_all_facts(root)

        assert result["extraction_method"] == "section_regex"
        facts = {f["fact"] for f in result["current_facts"]}
        assert "Lives in Berlin." in facts
        assert "Works at the university." in facts
        assert "Kael can fly." in facts

    def test_chapter_num_extracted_correctly(self, tmp_path):
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 07 — The Twist\n\n"
            "### Setting: rules\n"
            "- Magic needs consent.\n"
        )
        result = extract_all_facts(root)

        assert result["current_facts"][0]["chapter_num"] == 7

    def test_subject_extracted_from_subsection(self, tmp_path):
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 03 — Rising\n\n"
            "### Theo: skills\n"
            "- Speaks German fluently.\n"
        )
        result = extract_all_facts(root)

        assert result["current_facts"][0]["subject"] == "Theo"
        assert result["current_facts"][0]["domain"] == "skills"

    def test_changed_fact_extracted(self, tmp_path):
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 05 — Turn\n\n"
            "### Kael: relationships\n"
            "- **CHANGED**: Kael is Anna's enemy → Kael is Anna's ally "
            "(revision_impact: 06-garlic, 07-school)\n"
        )
        result = extract_all_facts(root)

        assert result["changed_facts"]
        cf = result["changed_facts"][0]
        assert cf["chapter_num"] == 5
        assert cf["old_value"] == "Kael is Anna's enemy"
        assert cf["fact"] == "Kael is Anna's ally"
        assert cf["revision_impacts"] == ["06-garlic", "07-school"]

    def test_changed_with_parenthetical_in_new_value(self, tmp_path):
        """CHANGED_RE must not drop facts whose new-value contains a parenthesis."""
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 05 — Turn\n\n"
            "### Theo: relationships\n"
            "- **CHANGED**: Theo lives alone → Theo lives with Anna (since the fire) in Berlin\n"
        )
        result = extract_all_facts(root)

        assert result["changed_facts"], "parenthetical in new-value must not drop the CHANGED line"
        cf = result["changed_facts"][0]
        assert cf["old_value"] == "Theo lives alone"
        assert "Anna" in cf["fact"], f"new-value must include the parenthetical, got: {cf['fact']!r}"
        assert cf["revision_impacts"] == []

    def test_changed_without_revision_impact(self, tmp_path):
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 03 — Change\n\n"
            "- **CHANGED**: Old thing → New thing\n"
        )
        result = extract_all_facts(root)

        assert result["changed_facts"]
        assert result["changed_facts"][0]["revision_impacts"] == []

    def test_changed_not_duplicated_in_current_facts(self, tmp_path):
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 03 — Change\n\n"
            "### Theo: traits\n"
            "- **CHANGED**: old → new\n"
            "- Regular fact.\n"
        )
        result = extract_all_facts(root)

        changed_texts = {f["fact"] for f in result["changed_facts"]}
        current_texts = {f["fact"] for f in result["current_facts"]}
        assert not changed_texts.intersection(current_texts), (
            "CHANGED entries must not appear in current_facts"
        )

    def test_no_sections_uses_heuristic(self, tmp_path):
        root = _book(tmp_path)
        _write_log(root, "- Just a bullet.\n- Another fact.\n")
        result = extract_all_facts(root)

        assert result["extraction_method"] == "heuristic"
        assert len(result["current_facts"]) == 2
        assert result["current_facts"][0]["chapter_num"] == 0

    def test_heuristic_changed_extracted(self, tmp_path):
        root = _book(tmp_path)
        _write_log(root,
            "- Normal fact.\n"
            "- **CHANGED**: Old → New (revision_impact: 03-ch)\n"
        )
        result = extract_all_facts(root)

        assert result["changed_facts"]
        assert result["changed_facts"][0]["revision_impacts"] == ["03-ch"]

    def test_memoir_reads_people_log(self, tmp_path):
        root = _book(tmp_path, category="memoir")
        _write_log(root, memoir=True, content=
            "## Chapter 01 — Opening\n\n"
            "### Mum: role\n"
            "- Mother of narrator.\n"
        )
        result = extract_all_facts(root, "memoir")

        assert result["extraction_method"] == "section_regex"
        assert result["current_facts"][0]["fact"] == "Mother of narrator."

    def test_fiction_does_not_read_people_log(self, tmp_path):
        root = _book(tmp_path)
        (root / "plot" / "people-log.md").write_text(
            "## Chapter 01 — Setup\n\n- People fact.\n", encoding="utf-8"
        )
        result = extract_all_facts(root, "fiction")

        assert result["extraction_method"] == "none"

    def test_all_chapters_extracted_no_scope_cutoff(self, tmp_path):
        """extract_all_facts must include ALL chapters — no scope window."""
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 01 — Early\n\n- Early fact.\n\n"
            "## Chapter 99 — Late\n\n- Late fact.\n"
        )
        result = extract_all_facts(root)

        facts = {f["fact"] for f in result["current_facts"]}
        assert "Early fact." in facts
        assert "Late fact." in facts

    def test_subject_before_changed_inferred(self, tmp_path):
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 10 — Reveal\n\n"
            "### Theo: cognition\n"
            "- **CHANGED**: Slow thinker → Fast thinker\n"
        )
        result = extract_all_facts(root)

        assert result["changed_facts"][0]["subject"] == "Theo"


# ---------------------------------------------------------------------------
# End-to-end migration into DB
# ---------------------------------------------------------------------------


class TestMigrateToDb:
    def test_current_facts_land_in_db(self, tmp_path, _patch_db):
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 02 — Action\n\n"
            "### Theo: traits\n"
            "- Theo likes coffee.\n"
        )
        _run_migrate(root)

        rows = _query_all(root)
        facts = {r["fact"] for r in rows}
        assert "Theo likes coffee." in facts

    def test_changed_facts_land_in_db_as_revision(self, tmp_path, _patch_db):
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 05 — Turn\n\n"
            "### Kael: relationships\n"
            "- **CHANGED**: Enemy → Ally (revision_impact: 06-ch)\n"
        )
        _run_migrate(root)

        rows = _query_all(root)
        revisions = [r for r in rows if r["is_revision"]]
        assert revisions, "CHANGED entry must be stored as is_revision=True"
        assert revisions[0]["old_value"] == "Enemy"
        assert revisions[0]["fact"] == "Ally"
        assert json.loads(revisions[0]["revision_impacts"]) == ["06-ch"]

    def test_chapter_num_stored_correctly(self, tmp_path, _patch_db):
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 07 — Twist\n\n"
            "### Setting: rules\n"
            "- Magic needs consent.\n"
        )
        _run_migrate(root)

        rows = _query_all(root)
        assert rows[0]["chapter_num"] == 7

    def test_idempotent_second_run_no_duplicates(self, tmp_path, _patch_db):
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 01 — Setup\n\n"
            "- Fact A.\n- Fact B.\n"
        )
        _run_migrate(root)
        _run_migrate(root)  # second run

        rows = _query_all(root)
        facts = [r["fact"] for r in rows]
        assert facts.count("Fact A.") == 1, "idempotent: no duplicate rows on second run"

    def test_memoir_migration_reads_people_log(self, tmp_path, _patch_db):
        root = _book(tmp_path, category="memoir")
        _write_log(root, memoir=True, content=
            "## Chapter 01 — Opening\n\n"
            "### Dad: personality\n"
            "- Quiet and determined.\n"
        )
        _run_migrate(root)

        rows = _query_all(root)
        facts = {r["fact"] for r in rows}
        assert "Quiet and determined." in facts

    def test_subject_stored_from_subsection(self, tmp_path, _patch_db):
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 03 — Rising\n\n"
            "### Anna: skills\n"
            "- Anna speaks French.\n"
        )
        _run_migrate(root)

        rows = _query_all(root)
        assert rows[0]["subject"] == "Anna"
        assert rows[0]["domain"] == "skills"

    def test_heuristic_log_chapter_num_zero(self, tmp_path, _patch_db):
        root = _book(tmp_path)
        _write_log(root, "- Heuristic fact.\n")
        _run_migrate(root)

        rows = _query_all(root)
        assert rows[0]["chapter_num"] == 0

    def test_no_log_skips_gracefully(self, tmp_path, _patch_db):
        root = _book(tmp_path)
        count = _run_migrate(root)

        assert count == 0
        assert _query_all(root) == []

    def test_real_format_b_log(self, tmp_path, _patch_db):
        """Smoke test against a realistic Format B log (the firelight format)."""
        root = _book(tmp_path)
        _write_log(root,
            "## Chapter 01 — Invisible\n\n"
            "### Theo: skills\n"
            "- Theo is 26, IT specialist at Whitmore & Associates.\n"
            "- Speaks German and English fluently.\n\n"
            "### Setting: world rules\n"
            "- Vampires cannot enter without invitation.\n\n"
            "## Chapter 02 — The Meeting\n\n"
            "### Theo: relationships\n"
            "- **CHANGED**: Theo fears Kael → Theo trusts Kael "
            "(revision_impact: 03-dinner, 04-the-park)\n"
            "- Kael is Theo's mentor.\n\n"
            "### Kael: abilities\n"
            "- Kael can read surface thoughts.\n"
        )
        _run_migrate(root)

        rows = _query_all(root)
        assert len(rows) == 6, f"expected 6 rows, got {len(rows)}: {[r['fact'] for r in rows]}"

        current = [r for r in rows if not r["is_revision"]]
        revisions = [r for r in rows if r["is_revision"]]
        assert len(current) == 5
        assert len(revisions) == 1
        assert revisions[0]["old_value"] == "Theo fears Kael"


class TestMainSkipsUnlinkedSeriesBooks:
    """Issue #584: get_book_num() (Issue #579) now raises
    BookNotLinkedToSeriesError for a book with series set but
    series_number=0. Without a catch in main()'s per-book loop, the whole
    migration run used to die on the first such book — books processed
    before it stayed committed, books after it were silently never
    attempted, no summary of what didn't run."""

    def test_main_skips_and_continues_past_unlinked_book(self, tmp_path, _patch_db, monkeypatch, capsys):
        content_root = tmp_path / "content"
        projects_dir = content_root / "projects"
        projects_dir.mkdir(parents=True)

        good_book = projects_dir / "good-book"
        _write_log(
            _book_at(good_book),
            "## Chapter 01 — Setup\n\n### Theo: traits\n- Theo likes coffee.\n",
        )

        unlinked_book = projects_dir / "unlinked-book"
        unlinked_book.mkdir(parents=True)
        (unlinked_book / "plot").mkdir()
        (unlinked_book / "chapters").mkdir()
        (unlinked_book / "characters").mkdir()
        (unlinked_book / "README.md").write_text(
            '---\ntitle: unlinked-book\nslug: unlinked-book\nbook_category: fiction\n'
            'series: "my-series"\nseries_number: 0\n---\n',
            encoding="utf-8",
        )
        _write_log(
            unlinked_book,
            "## Chapter 01 — Setup\n\n### X: traits\n- Should not crash the run.\n",
        )

        monkeypatch.setattr(
            migrate_canon_log_to_db, "load_config", lambda: {"paths": {"content_root": str(content_root)}}
        )

        with pytest.raises(SystemExit) as exc_info:
            migrate_canon_log_to_db.main()
        assert exc_info.value.code == 1

        out = capsys.readouterr().out
        assert "SKIP (error): unlinked-book" in out
        assert "my-series" in out
        # The good book must still have been processed despite the other
        # book's failure — not silently dropped by an aborted loop.
        assert "good-book" in out

    def test_main_prints_skip_summary_and_exits_nonzero(self, tmp_path, _patch_db, monkeypatch, capsys):
        """Issue #588: the per-book SKIP lines scroll away on a real run —
        a cron/CI caller needs a nonzero exit code, not just log lines, to
        notice a partial migration. exit(0) on a run that silently skipped
        books is exactly the "reports clean success" bug this closes."""
        content_root = tmp_path / "content"
        projects_dir = content_root / "projects"
        projects_dir.mkdir(parents=True)

        unlinked_book = projects_dir / "unlinked-book"
        unlinked_book.mkdir(parents=True)
        (unlinked_book / "plot").mkdir()
        (unlinked_book / "chapters").mkdir()
        (unlinked_book / "characters").mkdir()
        (unlinked_book / "README.md").write_text(
            '---\ntitle: unlinked-book\nslug: unlinked-book\nbook_category: fiction\n'
            'series: "my-series"\nseries_number: 0\n---\n',
            encoding="utf-8",
        )
        _write_log(
            unlinked_book,
            "## Chapter 01 — Setup\n\n### X: traits\n- Should not crash the run.\n",
        )

        monkeypatch.setattr(
            migrate_canon_log_to_db, "load_config", lambda: {"paths": {"content_root": str(content_root)}}
        )

        with pytest.raises(SystemExit) as exc_info:
            migrate_canon_log_to_db.main()
        assert exc_info.value.code == 1

        out = capsys.readouterr().out
        assert "1 book(s) skipped" in out

    def test_main_exits_zero_when_nothing_skipped(self, tmp_path, _patch_db, monkeypatch, capsys):
        content_root = tmp_path / "content"
        projects_dir = content_root / "projects"
        projects_dir.mkdir(parents=True)
        _write_log(
            _book_at(projects_dir / "good-book"),
            "## Chapter 01 — Setup\n\n### Theo: traits\n- Theo likes coffee.\n",
        )

        monkeypatch.setattr(
            migrate_canon_log_to_db, "load_config", lambda: {"paths": {"content_root": str(content_root)}}
        )

        migrate_canon_log_to_db.main()  # must NOT raise SystemExit

        out = capsys.readouterr().out
        assert "book(s) skipped" not in out

    def test_benign_no_log_skip_is_distinct_from_error_skip_and_does_not_exit_nonzero(
        self, tmp_path, _patch_db, monkeypatch, capsys
    ):
        """Issue #588 code review, L-3: migrate_book()'s own benign
        "SKIP: ... no log" / "no extractable facts" lines are expected
        no-ops for a book that simply has nothing to migrate — they must
        stay labeled plain "SKIP:" (not "SKIP (error):") and must not
        count toward the exit-code-driving `skipped` total, or a content
        root with several ordinary log-less books would exit nonzero for
        no actual error."""
        content_root = tmp_path / "content"
        projects_dir = content_root / "projects"
        projects_dir.mkdir(parents=True)
        # _book() with no _write_log() call — no canon-log.md/people-log.md
        # at all, the extraction_method == "none" benign-skip case.
        _book(projects_dir, "no-log-book")

        monkeypatch.setattr(
            migrate_canon_log_to_db, "load_config", lambda: {"paths": {"content_root": str(content_root)}}
        )

        migrate_canon_log_to_db.main()  # must NOT raise SystemExit

        out = capsys.readouterr().out
        assert "SKIP: no-log-book" in out
        assert "SKIP (error)" not in out
        assert "book(s) skipped" not in out
