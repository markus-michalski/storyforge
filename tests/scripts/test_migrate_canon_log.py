"""Tests for scripts/migrate_canon_log_to_db.py — Issue #297.

Verifies that the migration script correctly handles Format B
(## Chapter NN / ### Subject: topic / bullets / **CHANGED**) for both
fiction (canon-log.md) and memoir (people-log.md).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.db.connection as _db_conn
from tools.db.canon_facts import insert_fact, query_facts
from tools.db.connection import get_book_num, get_db_slug_for_book, open_canon_db
from tools.state.loaders.canon_log_extractor import extract_all_facts


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _book(tmp_path: Path, slug: str = "my-book", *, category: str = "fiction") -> Path:
    root = tmp_path / slug
    (root / "chapters").mkdir(parents=True)
    (root / "plot").mkdir()
    (root / "characters").mkdir()
    (root / "README.md").write_text(
        f"---\ntitle: {slug}\nslug: {slug}\nbook_category: {category}\n---\n",
        encoding="utf-8",
    )
    return root


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
