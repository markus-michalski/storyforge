"""Tests for tools.state.review_brief — Issue #99.

Verifies that build_review_brief() returns the correct structured payload
and that the individual parsers handle the template format correctly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.state.review_brief import (
    _cap_canon_facts,
    _parse_canon_log_facts,
    _parse_tonal_rules,
    _parse_travel_matrix,
    build_review_brief,
)

# ---------------------------------------------------------------------------
# Sample data matching the template format (world-setting.md, plot-tone.md, and
# a minimal canon-log fixture this test pins). The live canon-log convention is
# defined in templates/canon-log.md and exercised by tests/state/test_canon_brief.py.
# ---------------------------------------------------------------------------

TRAVEL_MATRIX_SAMPLE = """\
## Travel Matrix

| From | To | Distance | Transport | Travel Time | Notes |
|------|-----|----------|-----------|-------------|-------|
| City | Campground | 120 km | Car | 2h 30min | Highway, no traffic |
| Airport | Hotel | 15 km | Taxi | 20min | City traffic |
"""

CANON_LOG_SAMPLE = """\
## Established Facts

### Character Facts

| Fact | Established In | Status | Notes |
|------|----------------|--------|-------|
| Marcus is a vampire | Ch 1 | ACTIVE | |
| Lena eats normal food | Ch 4 (rev) | CHANGED | Was: Lena doesn't eat (Ch 4 original) |

### World / Setting Facts

| Fact | Established In | Status | Notes |
|------|----------------|--------|-------|
| Vampires can walk in daylight | Ch 1 | ACTIVE | But weakened by sunlight |
"""

TONE_SAMPLE = """\
## Non-Negotiable Rules

- At least one genuine laugh per chapter
- Minimum 40% dialog ratio

## Litmus Test

1. Does the chapter make you want to turn the page?
2. Is the protagonist's want clear by the end?

## Banned Prose Patterns (Book-Specific)

- No extended interiority without interruption
- No weather descriptions as mood-setting

## Tonal Arc

| Stage | Chapters | Dominant Mode | Secondary Mode | Warning Signs |
|-------|----------|---------------|----------------|---------------|
| Act 1 | Ch. 1-3 | humor-forward | mystery undercurrent | reads as depressive |
| Act 2 | Ch. 4-10 | tension rising | humor | no humor at all |
"""


# ---------------------------------------------------------------------------
# Parser unit tests — _parse_travel_matrix
# ---------------------------------------------------------------------------


def test_parse_travel_matrix_returns_routes():
    result = _parse_travel_matrix(TRAVEL_MATRIX_SAMPLE)
    assert len(result) == 2


def test_parse_travel_matrix_correct_fields():
    result = _parse_travel_matrix(TRAVEL_MATRIX_SAMPLE)
    first = result[0]
    assert first["from"] == "City"
    assert first["to"] == "Campground"
    assert first["distance"] == "120 km"
    assert first["travel_time"] == "2h 30min"
    assert first["notes"] == "Highway, no traffic"


def test_parse_travel_matrix_no_section():
    result = _parse_travel_matrix("# No travel matrix here\n\nSome text.")
    assert result == []


def test_parse_travel_matrix_skips_placeholder_rows():
    text = """\
## Travel Matrix

| From | To | Distance | Transport | Travel Time | Notes |
|------|-----|----------|-----------|-------------|-------|
| *e.g. City center* | *e.g. Campground* | *120 km* | *Car* | *2h 30min* | *Highway* |
| Real City | Real Camp | 50 km | Bike | 3h | Dirt road |
"""
    result = _parse_travel_matrix(text)
    assert len(result) == 1
    assert result[0]["from"] == "Real City"


# ---------------------------------------------------------------------------
# Parser unit tests — _parse_canon_log_facts
# ---------------------------------------------------------------------------


def test_parse_canon_log_facts_extracts_all_facts():
    result = _parse_canon_log_facts(CANON_LOG_SAMPLE)
    assert len(result) == 3


def test_parse_canon_log_facts_correct_status():
    result = _parse_canon_log_facts(CANON_LOG_SAMPLE)
    by_fact = {f["fact"]: f for f in result}
    assert by_fact["Marcus is a vampire"]["status"] == "ACTIVE"
    assert by_fact["Lena eats normal food"]["status"] == "CHANGED"


def test_parse_canon_log_facts_includes_domain():
    result = _parse_canon_log_facts(CANON_LOG_SAMPLE)
    char_facts = [f for f in result if f["domain"] == "Character Facts"]
    assert len(char_facts) == 2
    world_facts = [f for f in result if f["domain"] == "World / Setting Facts"]
    assert len(world_facts) == 1


def test_parse_canon_log_facts_no_section():
    result = _parse_canon_log_facts("# Canon Log\n\nNo established facts section.")
    assert result == []


def test_parse_canon_log_facts_skips_placeholder_rows():
    text = """\
## Established Facts

### Character Facts

| Fact | Established In | Status | Notes |
|------|----------------|--------|-------|
| *e.g. Marcus is a vampire who eats normal food* | Ch 4 (rev) | CHANGED | |
| Real fact | Ch 1 | ACTIVE | |
"""
    result = _parse_canon_log_facts(text)
    assert len(result) == 1
    assert result[0]["fact"] == "Real fact"


# ---------------------------------------------------------------------------
# Parser unit tests — _parse_tonal_rules
# ---------------------------------------------------------------------------


def test_parse_tonal_rules_extracts_all_sections():
    result = _parse_tonal_rules(TONE_SAMPLE)
    assert "non_negotiable_rules" in result
    assert "litmus_test" in result
    assert "banned_prose_patterns" in result
    assert "warning_signs" in result


def test_parse_tonal_rules_non_negotiable_count():
    result = _parse_tonal_rules(TONE_SAMPLE)
    assert len(result["non_negotiable_rules"]) == 2


def test_parse_tonal_rules_litmus_test_count():
    result = _parse_tonal_rules(TONE_SAMPLE)
    assert len(result["litmus_test"]) == 2


def test_parse_tonal_rules_banned_patterns_count():
    result = _parse_tonal_rules(TONE_SAMPLE)
    assert len(result["banned_prose_patterns"]) == 2


def test_parse_tonal_rules_warning_signs_from_arc_table():
    result = _parse_tonal_rules(TONE_SAMPLE)
    assert "reads as depressive" in result["warning_signs"]
    assert "no humor at all" in result["warning_signs"]


def test_parse_tonal_rules_empty_tone_file():
    result = _parse_tonal_rules("")
    assert result["non_negotiable_rules"] == []
    assert result["litmus_test"] == []
    assert result["banned_prose_patterns"] == []
    assert result["warning_signs"] == []


# ---------------------------------------------------------------------------
# Unit tests — _cap_canon_facts (Issue #500)
# ---------------------------------------------------------------------------


def _fact(chapter: int, status: str = "ACTIVE", fact: str = "", book_num: int = 1) -> dict:
    return {
        "fact": fact or f"Fact from chapter {chapter}",
        "established_in": f"Ch {chapter}",
        "status": status,
        "notes": "",
        "domain": "",
        "book_num": book_num,
    }


def test_cap_canon_facts_no_truncation_under_budget():
    facts = [_fact(i) for i in range(5)]
    kept, truncated, total = _cap_canon_facts(facts, char_budget=100_000)
    assert truncated is False
    assert total == 5
    assert len(kept) == 5


def test_cap_canon_facts_empty_list():
    kept, truncated, total = _cap_canon_facts([], char_budget=100_000)
    assert kept == []
    assert truncated is False
    assert total == 0


def test_cap_canon_facts_truncates_oldest_active_first():
    facts = [_fact(i) for i in range(1, 11)]  # chapters 1..10
    # Each entry is roughly the same size; pick a budget that fits ~5.
    one_entry_size = len(json.dumps(facts[0])) + 1
    kept, truncated, total = _cap_canon_facts(facts, char_budget=one_entry_size * 5)

    assert truncated is True
    assert total == 10
    kept_chapters = {int(f["established_in"].split()[1]) for f in kept}
    # newest-first: chapters 10, 9, 8... must survive before chapter 1.
    assert 10 in kept_chapters
    assert 1 not in kept_chapters


def test_cap_canon_facts_changed_facts_get_priority_over_active():
    changed = [_fact(i, status="CHANGED") for i in range(1, 4)]  # 3 small facts
    active = [_fact(i) for i in range(4, 30)]  # 26 facts competing for what's left
    facts = changed + active
    one_entry_size = len(json.dumps(changed[0])) + 1
    # Budget fits all 3 CHANGED facts plus a few ACTIVE ones, not all 26.
    kept, truncated, total = _cap_canon_facts(facts, char_budget=one_entry_size * 8)

    kept_changed = [f for f in kept if f["status"] == "CHANGED"]
    assert len(kept_changed) == 3, "all CHANGED facts must survive before any ACTIVE fact"
    assert truncated is True
    assert total == 29
    assert len(kept) < 29


def test_cap_canon_facts_changed_group_is_also_bounded():
    """Issue #500 review finding: CHANGED facts must not be literally
    unbounded — a pathological book with thousands of revisions must still
    hit a ceiling instead of the 'truncated' flag misreporting False while
    the CHANGED group alone dwarfs the budget."""
    changed = [_fact(i, status="CHANGED") for i in range(1, 501)]  # many facts
    one_entry_size = len(json.dumps(changed[0])) + 1
    kept, truncated, total = _cap_canon_facts(changed, char_budget=one_entry_size * 10)

    assert truncated is True
    assert total == 500
    assert len(kept) < 500


def test_cap_canon_facts_oldest_first_applies_to_changed_group_too():
    """Issue #501 test-gap: oldest_first must invert ranking within the
    CHANGED-facts priority tier, not just the ACTIVE rest tier — continuity_brief
    relies on this (a whole-manuscript scan wants early revisions, which have
    had more subsequent chapters to go stale in, protected the same way it
    wants early ACTIVE facts protected). This was documented in
    continuity_brief.py's code comment but had no direct test."""
    changed = [_fact(i, status="CHANGED") for i in range(1, 11)]
    one_entry_size = len(json.dumps(changed[0])) + 1

    kept, truncated, total = _cap_canon_facts(
        changed, char_budget=one_entry_size * 5, oldest_first=True,
    )

    kept_chapters = {_chapter_num_from_fact(f) for f in kept}
    assert 1 in kept_chapters
    assert 10 not in kept_chapters
    assert truncated is True
    assert total == 10


def test_cap_canon_facts_ranks_current_book_above_prior_book():
    """Issue #500 review finding: canon_log_facts includes every prior book
    in a series (query_facts includes book_num < current unconditionally).
    Sorting by chapter_num alone is book-blind — chapter 34 of book 1 would
    outrank chapter 2 of the book actually under review, starving it of its
    own canon under a tight budget."""
    book1_facts = [_fact(i, book_num=1) for i in range(1, 35)]  # late chapters, old book
    book2_facts = [_fact(i, book_num=2) for i in range(1, 4)]  # early chapters, THIS book
    facts = book1_facts + book2_facts
    one_entry_size = len(json.dumps(book1_facts[0])) + 1

    kept, truncated, total = _cap_canon_facts(
        facts, current_book_num=2, char_budget=one_entry_size * 5,
    )

    kept_book2 = [f for f in kept if f["book_num"] == 2]
    assert len(kept_book2) == 3, "all of the current book's own facts must survive first"
    assert truncated is True
    assert total == 37


def test_cap_canon_facts_ranks_at_or_before_current_chapter_first():
    """Issue #500 round-3 review finding: newest-chapter-first alone shows a
    reviewer checking an EARLY chapter the LEAST relevant facts (from near
    the end of the book) first, silently truncating away the ones from
    chapters 1..N that the chapter under review could actually contradict."""
    later_facts = [_fact(i) for i in range(20, 35)]  # chapters 20-34, can't be contradicted by ch. 5
    earlier_facts = [_fact(i) for i in range(1, 6)]  # chapters 1-5, what ch. 5 could conflict with
    facts = later_facts + earlier_facts
    one_entry_size = len(json.dumps(facts[0])) + 1

    kept, truncated, total = _cap_canon_facts(
        facts, current_chapter_num=5, char_budget=one_entry_size * 5,
    )

    kept_chapters = {_chapter_num_from_fact(f) for f in kept}
    assert kept_chapters == {1, 2, 3, 4, 5}, "chapters at/before the reviewed one must survive first"
    assert truncated is True
    assert total == 20


def _chapter_num_from_fact(fact: dict) -> int:
    return int(fact["established_in"].split()[1])


def test_cap_canon_facts_current_chapter_num_none_falls_back_to_newest_first():
    """No chapter context (e.g. an unparseable slug) must not crash — falls
    back to the pre-M1 newest-chapter-first behavior."""
    facts = [_fact(i) for i in range(1, 11)]
    one_entry_size = len(json.dumps(facts[0])) + 1

    kept, truncated, total = _cap_canon_facts(
        facts, current_chapter_num=None, char_budget=one_entry_size * 5,
    )

    kept_chapters = {_chapter_num_from_fact(f) for f in kept}
    assert 10 in kept_chapters
    assert 1 not in kept_chapters


def test_cap_canon_facts_oldest_first_keeps_earliest_chapters():
    """Issue #501: a whole-manuscript caller (continuity_brief) has no single
    chapter to anchor on, so the newest-first fallback would systematically
    drop the earliest, most foundational facts — exactly what late chapters
    are most likely to accidentally contradict. oldest_first=True inverts
    the within-group ranking so early chapters survive truncation instead."""
    facts = [_fact(i) for i in range(1, 11)]
    one_entry_size = len(json.dumps(facts[0])) + 1

    kept, truncated, total = _cap_canon_facts(
        facts, current_chapter_num=None, char_budget=one_entry_size * 5, oldest_first=True,
    )

    kept_chapters = {_chapter_num_from_fact(f) for f in kept}
    assert 1 in kept_chapters
    assert 10 not in kept_chapters
    assert truncated is True
    assert total == 10


def test_cap_canon_facts_keeps_chapter_unattributed_facts():
    """Issue #500 review finding: chapter_num=0 (heuristically migrated,
    no chapter attribution) must not be treated as 'oldest, drop first' —
    tools/state/loaders/canon_brief.py already treats these as always in
    scope; _cap_canon_facts must not contradict that."""
    unattributed = [_fact(0, fact="Migrated global fact")]
    active = [_fact(i) for i in range(1, 30)]  # many newer-looking facts
    facts = unattributed + active
    one_entry_size = len(json.dumps(active[0])) + 1

    kept, truncated, total = _cap_canon_facts(facts, char_budget=one_entry_size * 5)

    assert unattributed[0] in kept
    assert truncated is True


# ---------------------------------------------------------------------------
# Integration tests — build_review_brief
# ---------------------------------------------------------------------------


def _make_book(tmp_path: Path) -> tuple[Path, str]:
    book_slug = "test-book"
    book = tmp_path / book_slug
    (book / "chapters").mkdir(parents=True)
    (book / "plot").mkdir()
    (book / "world").mkdir()
    (book / "README.md").write_text(
        '---\ntitle: "Test Book"\nauthor: ""\n---\n\n# Test Book\n',
        encoding="utf-8",
    )
    return book, book_slug


def _make_chapter(
    book: Path,
    slug: str,
    *,
    number: int,
    status: str = "Draft",
    has_timeline: bool = False,
) -> Path:
    chapter = book / "chapters" / slug
    chapter.mkdir(parents=True)
    timeline_section = (
        ("\n\n## Chapter Timeline\n\n**Start:** Day 5 (Dec 25, 2025) — 14:30\n**End:** Day 5 (Dec 25, 2025) — 17:00\n")
        if has_timeline
        else ""
    )
    (chapter / "README.md").write_text(
        f'---\ntitle: "Chapter {number}"\nnumber: {number}\n'
        f'status: "{status}"\n---\n\n# Chapter {number}\n{timeline_section}',
        encoding="utf-8",
    )
    (chapter / "draft.md").write_text("The chapter draft content.", encoding="utf-8")
    return chapter


def test_build_review_brief_returns_all_expected_keys(tmp_path):
    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)

    result = build_review_brief(
        book_root=book,
        book_slug=slug,
        chapter_slug="01-opening",
    )

    expected_keys = {
        "book_slug",
        "chapter_slug",
        "chapter_timeline",
        "previous_chapter_timeline",
        "canonical_timeline_entries",
        "travel_matrix",
        "canon_log_facts",
        "canon_log_facts_truncated",
        "canon_log_facts_total_count",
        "changed_facts",
        "tonal_rules",
        "active_rules",
        "active_callbacks",
        "errors",
    }
    assert expected_keys <= set(result.keys())


def test_build_review_brief_rejects_traversal_chapter_slug(tmp_path):
    """Issue #538: chapter_slug reaches `chapters_dir / chapter_slug` with
    zero validation — same bug shape as #524. Raises rather than degrading
    gracefully, matching resolve_*_path()'s own convention; the caller
    (routers/chapters.py::get_review_brief) is already
    @catch_slug_value_error-decorated and converts this into the standard
    JSON error contract."""
    from tools.shared.paths import SlugValidationError

    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)

    with pytest.raises(SlugValidationError):
        build_review_brief(book_root=book, book_slug=slug, chapter_slug="../../../etc")


def test_build_review_brief_no_errors_for_minimal_book(tmp_path):
    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)

    result = build_review_brief(
        book_root=book,
        book_slug=slug,
        chapter_slug="01-opening",
    )

    assert result["errors"] == []


def test_build_review_brief_travel_matrix_populated(tmp_path):
    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)
    (book / "world" / "setting.md").write_text(TRAVEL_MATRIX_SAMPLE, encoding="utf-8")

    result = build_review_brief(
        book_root=book,
        book_slug=slug,
        chapter_slug="01-opening",
    )

    assert len(result["travel_matrix"]) == 2
    assert result["travel_matrix"][0]["from"] == "City"


def test_build_review_brief_canon_log_facts_populated(tmp_path, monkeypatch):
    import tools.db.connection as _db_conn
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)

    # Insert facts via DB (matching the 3 rows from the old CANON_LOG_SAMPLE):
    # 2 ACTIVE + 1 CHANGED
    db_slug = get_db_slug_for_book(book)
    conn = open_canon_db(db_slug)
    insert_fact(conn, book_num=1, chapter_num=1, subject="Marcus",
                fact="Marcus is a vampire", domain="Character Facts")
    insert_fact(conn, book_num=1, chapter_num=4, subject="Lena",
                fact="Lena eats normal food", domain="Character Facts",
                is_revision=True, old_value="Lena doesn't eat")
    insert_fact(conn, book_num=1, chapter_num=1, subject="World",
                fact="Vampires can walk in daylight", domain="World / Setting Facts")
    conn.close()

    result = build_review_brief(
        book_root=book,
        book_slug=slug,
        chapter_slug="01-opening",
    )

    assert len(result["canon_log_facts"]) == 3
    changed = [f for f in result["canon_log_facts"] if f["status"] == "CHANGED"]
    assert len(changed) == 1


def test_build_review_brief_keeps_timeline_domain_facts(tmp_path, monkeypatch):
    """Issue #500: domain="timeline" is a documented first-class canon domain
    (reference/craft/chapter-writing-shared.md) — the review brief must not
    drop it. The 330K-char blowup on Firelight is handled by size-bounded
    truncation (see test_build_review_brief_truncates_when_over_budget
    below), not by assuming an entire domain is safe to discard."""
    import tools.db.connection as _db_conn
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)

    db_slug = get_db_slug_for_book(book)
    conn = open_canon_db(db_slug)
    insert_fact(conn, book_num=1, chapter_num=1, subject="Theo",
                fact="Theo is 26", domain="")
    insert_fact(conn, book_num=1, chapter_num=1, subject="general",
                fact="Storm hits midday Saturday", domain="timeline")
    conn.close()

    result = build_review_brief(book_root=book, book_slug=slug, chapter_slug="01-opening")

    facts = result["canon_log_facts"]
    assert len(facts) == 2
    assert result["canon_log_facts_truncated"] is False
    assert result["canon_log_facts_total_count"] == 2


def test_build_review_brief_truncates_when_over_budget(tmp_path, monkeypatch):
    """Reproduces the Firelight failure mode at test scale: many canon facts
    must trigger truncation with the two report fields set, rather than
    silently ballooning the brief past the MCP tool output limit."""
    import tools.db.connection as _db_conn
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db
    import tools.state.brief_common as brief_common_module

    monkeypatch.setattr(brief_common_module, "CANON_FACTS_CHAR_BUDGET", 200)

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)

    db_slug = get_db_slug_for_book(book)
    conn = open_canon_db(db_slug)
    for i in range(20):
        insert_fact(conn, book_num=1, chapter_num=i + 1, subject=f"subject-{i}",
                    fact=f"Fact number {i} established in this chapter", domain="timeline")
    conn.close()

    result = build_review_brief(book_root=book, book_slug=slug, chapter_slug="01-opening")

    assert result["canon_log_facts_truncated"] is True
    assert result["canon_log_facts_total_count"] == 20
    assert len(result["canon_log_facts"]) < 20


def test_build_review_brief_prioritizes_facts_at_or_before_reviewed_chapter(tmp_path, monkeypatch):
    """Issue #500 round-3 review finding: build_review_brief must parse the
    chapter number out of chapter_slug and thread it into _cap_canon_facts —
    otherwise reviewing an early chapter shows facts from the end of the
    book first, which that early chapter cannot possibly contradict."""
    import tools.db.connection as _db_conn
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db
    import tools.state.brief_common as brief_common_module

    monkeypatch.setattr(brief_common_module, "CANON_FACTS_CHAR_BUDGET", 500)

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)
    _make_chapter(book, "03-third", number=3)

    db_slug = get_db_slug_for_book(book)
    conn = open_canon_db(db_slug)
    for i in range(1, 21):
        insert_fact(conn, book_num=1, chapter_num=i, subject=f"subject-{i}",
                    fact=f"Fact established in chapter {i}", domain="")
    conn.close()

    result = build_review_brief(book_root=book, book_slug=slug, chapter_slug="03-third")

    assert result["canon_log_facts_truncated"] is True
    kept_chapters = {f["established_in"] for f in result["canon_log_facts"]}
    assert "Ch 1" in kept_chapters
    assert "Ch 20" not in kept_chapters


def test_build_review_brief_changed_facts_populated(tmp_path, monkeypatch):
    """Issue #500: changed_facts feeds chapter-reviewer checklist point 19
    (stale-reference check), which needs revision_impact — canon_log_facts
    alone doesn't carry that field."""
    import tools.db.connection as _db_conn
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)

    db_slug = get_db_slug_for_book(book)
    conn = open_canon_db(db_slug)
    insert_fact(conn, book_num=1, chapter_num=4, subject="Lena",
                fact="Lena eats normal food", domain="Character Facts",
                is_revision=True, old_value="Lena doesn't eat",
                revision_impacts='["05-aftermath"]')
    conn.close()

    result = build_review_brief(book_root=book, book_slug=slug, chapter_slug="01-opening")

    assert len(result["changed_facts"]) == 1
    entry = result["changed_facts"][0]
    assert entry["old"] == "Lena doesn't eat"
    assert entry["new"] == "Lena eats normal food"
    assert entry["revision_impact"] == ["05-aftermath"]


def test_build_review_brief_tonal_rules_populated(tmp_path):
    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)
    (book / "plot" / "tone.md").write_text(TONE_SAMPLE, encoding="utf-8")

    result = build_review_brief(
        book_root=book,
        book_slug=slug,
        chapter_slug="01-opening",
    )

    assert len(result["tonal_rules"]["non_negotiable_rules"]) == 2
    assert len(result["tonal_rules"]["warning_signs"]) == 2


def test_build_review_brief_previous_chapter_populated(tmp_path):
    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)
    _make_chapter(book, "02-conflict", number=2)

    result = build_review_brief(
        book_root=book,
        book_slug=slug,
        chapter_slug="02-conflict",
    )

    assert result["previous_chapter_timeline"] is not None
    assert result["previous_chapter_timeline"]["slug"] == "01-opening"


def test_build_review_brief_no_previous_for_first_chapter(tmp_path):
    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)

    result = build_review_brief(
        book_root=book,
        book_slug=slug,
        chapter_slug="01-opening",
    )

    assert result["previous_chapter_timeline"] is None


def test_build_review_brief_active_rules_from_db(tmp_path, monkeypatch):
    import tools.db.connection as _db_conn
    from tools.db.book_rules import insert_rule
    from tools.db.connection import get_db_slug_for_book, open_canon_db

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)

    db_slug = get_db_slug_for_book(book)
    conn = open_canon_db(db_slug)
    insert_rule(conn, book_num=1, rule_type="rule", text="Never contradict the canon log")
    insert_rule(conn, book_num=1, rule_type="rule", text="Always load the timeline before writing")
    insert_rule(conn, book_num=1, rule_type="callback", text="Marcus must reveal his secret by Ch 10")
    conn.close()

    result = build_review_brief(
        book_root=book,
        book_slug=slug,
        chapter_slug="01-opening",
    )

    assert len(result["active_rules"]) == 2
    assert len(result["active_callbacks"]) == 1


def test_build_review_brief_missing_optional_files_graceful(tmp_path):
    """No setting.md, no canon-log.md, no tone.md → empty lists, no errors."""
    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)

    result = build_review_brief(
        book_root=book,
        book_slug=slug,
        chapter_slug="01-opening",
    )

    assert result["travel_matrix"] == []
    assert result["canon_log_facts"] == []
    assert result["canon_log_facts_truncated"] is False
    assert result["canon_log_facts_total_count"] == 0
    assert result["changed_facts"] == []
    assert result["tonal_rules"] == {}
    assert result["errors"] == []


# ---------------------------------------------------------------------------
# book_category + consent_status_warnings (Issue #176 follow-up) — added
# because chapter-reviewer/chapter-reviewer-memoir's Step 0 / Step 1b both
# read these fields "from the review brief," but build_review_brief() never
# computed either one until now — a real gap, not an eval-design issue,
# found via chapter-reviewer-memoir's live-MCP eval tier.
# ---------------------------------------------------------------------------


def _make_memoir_book(tmp_path: Path) -> tuple[Path, str]:
    book_slug = "test-memoir-book"
    book = tmp_path / book_slug
    (book / "chapters").mkdir(parents=True)
    (book / "plot").mkdir()
    (book / "people").mkdir()
    (book / "README.md").write_text(
        '---\ntitle: "Test Memoir Book"\nbook_category: "memoir"\n---\n\n# Test Memoir Book\n',
        encoding="utf-8",
    )
    return book, book_slug


def _make_person(book: Path, slug: str, *, name: str, consent_status: str) -> None:
    (book / "people" / f"{slug}.md").write_text(
        "---\n"
        f'name: "{name}"\n'
        'relationship: "relative"\n'
        'person_category: "private-living-person"\n'
        f'consent_status: "{consent_status}"\n'
        "---\n\nNotes.\n",
        encoding="utf-8",
    )


def test_build_review_brief_book_category_defaults_fiction(tmp_path):
    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)

    result = build_review_brief(book_root=book, book_slug=slug, chapter_slug="01-opening")

    assert result["book_category"] == "fiction"
    assert result["consent_status_warnings"] == []


def test_build_review_brief_book_category_memoir(tmp_path):
    book, slug = _make_memoir_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)

    result = build_review_brief(book_root=book, book_slug=slug, chapter_slug="01-opening")

    assert result["book_category"] == "memoir"


def test_build_review_brief_consent_warnings_person_named_in_readme(tmp_path):
    book, slug = _make_memoir_book(tmp_path)
    chapter = book / "chapters" / "01-opening"
    chapter.mkdir(parents=True)
    (chapter / "README.md").write_text(
        '---\ntitle: "Chapter 1"\nnumber: 1\nstatus: "Draft"\n---\n\n'
        "# Chapter 1\n\n## Scene Beats\n\n1. Uncle Frank arrives unannounced.\n",
        encoding="utf-8",
    )
    (chapter / "draft.md").write_text("Some prose without the name.", encoding="utf-8")
    _make_person(book, "uncle-frank", name="Uncle Frank", consent_status="refused")

    result = build_review_brief(book_root=book, book_slug=slug, chapter_slug="01-opening")

    warnings = result["consent_status_warnings"]
    assert len(warnings) == 1
    assert warnings[0]["person"] == "Uncle Frank"
    assert warnings[0]["tier"] == "refused"


def test_build_review_brief_consent_warnings_person_named_only_in_draft(tmp_path):
    """A person absent from the outline but present in the finished draft
    must still trip the consent gate — the review brief scans draft.md too,
    unlike chapter_writing_brief's outline-only scan (see _memoir_consent_warnings
    docstring for why the two differ)."""
    book, slug = _make_memoir_book(tmp_path)
    chapter = book / "chapters" / "01-opening"
    chapter.mkdir(parents=True)
    (chapter / "README.md").write_text(
        '---\ntitle: "Chapter 1"\nnumber: 1\nstatus: "Draft"\n---\n\n# Chapter 1\n',
        encoding="utf-8",
    )
    (chapter / "draft.md").write_text(
        "Aunt Marie showed up at the door, unannounced.", encoding="utf-8"
    )
    _make_person(book, "aunt-marie", name="Aunt Marie", consent_status="pending")

    result = build_review_brief(book_root=book, book_slug=slug, chapter_slug="01-opening")

    warnings = result["consent_status_warnings"]
    assert len(warnings) == 1
    assert warnings[0]["person"] == "Aunt Marie"
    assert warnings[0]["tier"] == "pending"


def test_build_review_brief_no_consent_warnings_for_fiction_book(tmp_path):
    """A fiction book must never run the memoir-only consent-gate scan,
    even if a people/ directory happens to exist (e.g. a legacy layout)."""
    book, slug = _make_book(tmp_path)
    (book / "people").mkdir()
    _make_person(book, "someone", name="Someone", consent_status="refused")
    chapter = book / "chapters" / "01-opening"
    chapter.mkdir(parents=True)
    (chapter / "README.md").write_text(
        '---\ntitle: "Chapter 1"\nnumber: 1\nstatus: "Draft"\n---\n\n# Chapter 1\nSomeone.\n',
        encoding="utf-8",
    )
    (chapter / "draft.md").write_text("Someone appears here.", encoding="utf-8")

    result = build_review_brief(book_root=book, book_slug=slug, chapter_slug="01-opening")

    assert result["book_category"] == "fiction"
    assert result["consent_status_warnings"] == []


def test_build_review_brief_no_consent_warnings_when_nobody_named(tmp_path):
    book, slug = _make_memoir_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)
    _make_person(book, "uncle-frank", name="Uncle Frank", consent_status="refused")

    result = build_review_brief(book_root=book, book_slug=slug, chapter_slug="01-opening")

    assert result["consent_status_warnings"] == []
