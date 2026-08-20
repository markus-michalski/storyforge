"""Tests for tools.state.continuity_brief — Issue #100.

Verifies that build_continuity_brief() returns the correct structured
payload including canonical_calendar, travel_matrix, canon_log_facts,
character_index, and chapter_timelines for ALL chapters.
"""

from __future__ import annotations

from pathlib import Path

from tools.state.continuity_brief import (
    _build_character_index,
    _get_all_chapter_timelines,
    build_continuity_brief,
)
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


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_book(tmp_path: Path) -> tuple[Path, str]:
    book_slug = "test-book"
    book = tmp_path / book_slug
    (book / "chapters").mkdir(parents=True)
    (book / "characters").mkdir()
    (book / "plot").mkdir()
    (book / "world").mkdir()
    (book / "README.md").write_text(
        '---\ntitle: "Test Book"\nauthor: ""\n---\n\n# Test Book\n',
        encoding="utf-8",
    )
    return book, book_slug


def _add_chapter(
    book: Path,
    slug: str,
    *,
    number: int,
    status: str = "Draft",
) -> Path:
    chapter = book / "chapters" / slug
    chapter.mkdir(parents=True)
    (chapter / "README.md").write_text(
        f'---\ntitle: "Chapter {number}"\nnumber: {number}\nstatus: "{status}"\n---\n\n# Chapter {number}\n',
        encoding="utf-8",
    )
    (chapter / "draft.md").write_text(f"Draft content for chapter {number}.", encoding="utf-8")
    return chapter


def _add_character(
    book: Path,
    slug: str,
    *,
    name: str,
    role: str = "supporting",
) -> None:
    (book / "characters" / f"{slug}.md").write_text(
        f'---\nname: "{name}"\nrole: "{role}"\n---\n\n# {name}\n',
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Unit tests — _build_character_index
# ---------------------------------------------------------------------------


def test_build_character_index_finds_all_characters(tmp_path):
    book, _ = _make_book(tmp_path)
    _add_character(book, "marcus", name="Marcus", role="protagonist")
    _add_character(book, "lena", name="Lena", role="supporting")

    result = _build_character_index(book)
    assert len(result) == 2


def test_build_character_index_correct_fields(tmp_path):
    book, _ = _make_book(tmp_path)
    _add_character(book, "marcus", name="Marcus", role="protagonist")

    result = _build_character_index(book)
    assert result[0]["slug"] == "marcus"
    assert result[0]["name"] == "Marcus"
    assert result[0]["role"] == "protagonist"


def test_build_character_index_skips_index_md(tmp_path):
    book, _ = _make_book(tmp_path)
    _add_character(book, "marcus", name="Marcus", role="protagonist")
    (book / "characters" / "INDEX.md").write_text("# Characters Index\n", encoding="utf-8")

    result = _build_character_index(book)
    slugs = [c["slug"] for c in result]
    assert "INDEX" not in slugs
    assert "marcus" in slugs


def test_build_character_index_empty_chars_dir(tmp_path):
    book, _ = _make_book(tmp_path)
    result = _build_character_index(book)
    assert result == []


def test_build_character_index_missing_chars_dir(tmp_path):
    book, _ = _make_book(tmp_path)
    (book / "characters").rmdir()
    result = _build_character_index(book)
    assert result == []


# ---------------------------------------------------------------------------
# Unit tests — _get_all_chapter_timelines
# ---------------------------------------------------------------------------


def test_get_all_chapter_timelines_includes_all_statuses(tmp_path):
    """Unlike get_recent_chapter_timelines, all statuses must be included."""
    book, _ = _make_book(tmp_path)
    _add_chapter(book, "01-opening", number=1, status="Outline")
    _add_chapter(book, "02-draft", number=2, status="Draft")
    _add_chapter(book, "03-review", number=3, status="Revision")

    result = _get_all_chapter_timelines(book)
    assert len(result) == 3


def test_get_all_chapter_timelines_correct_order(tmp_path):
    book, _ = _make_book(tmp_path)
    _add_chapter(book, "01-opening", number=1)
    _add_chapter(book, "02-conflict", number=2)
    _add_chapter(book, "03-resolution", number=3)

    result = _get_all_chapter_timelines(book)
    numbers = [r["number"] for r in result]
    assert numbers == sorted(numbers)


def test_get_all_chapter_timelines_empty_book(tmp_path):
    book, _ = _make_book(tmp_path)
    result = _get_all_chapter_timelines(book)
    assert result == []


# ---------------------------------------------------------------------------
# Integration tests — build_continuity_brief
# ---------------------------------------------------------------------------


def test_build_continuity_brief_returns_all_expected_keys(tmp_path):
    """Exact match, not a subset check — every key here must also be
    documented in the get_continuity_brief router docstring (chapters.py);
    a subset check would let a field silently disappear undetected."""
    book, slug = _make_book(tmp_path)

    result = build_continuity_brief(book_root=book, book_slug=slug)

    expected_keys = {
        "book_slug",
        "canonical_calendar",
        "canonical_calendar_truncated",
        "canonical_calendar_total_count",
        "travel_matrix",
        "canon_log_facts",
        "canon_log_facts_truncated",
        "canon_log_facts_total_count",
        "character_index",
        "chapter_timelines",
        "chapter_timelines_truncated",
        "chapter_timelines_total_count",
        "character_snapshots",
        "errors",
    }
    assert expected_keys == set(result.keys())


def test_build_continuity_brief_no_errors_empty_book(tmp_path):
    book, slug = _make_book(tmp_path)

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["errors"] == []


def test_build_continuity_brief_travel_matrix_populated(tmp_path):
    book, slug = _make_book(tmp_path)
    (book / "world" / "setting.md").write_text(TRAVEL_MATRIX_SAMPLE, encoding="utf-8")

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert len(result["travel_matrix"]) == 2


def test_build_continuity_brief_canon_log_facts_populated(tmp_path, monkeypatch):
    import tools.db.connection as _db_conn
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)

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

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert len(result["canon_log_facts"]) == 3


def test_build_continuity_brief_character_index_populated(tmp_path):
    book, slug = _make_book(tmp_path)
    _add_character(book, "marcus", name="Marcus", role="protagonist")
    _add_character(book, "lena", name="Lena")

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert len(result["character_index"]) == 2
    names = {c["name"] for c in result["character_index"]}
    assert names == {"Marcus", "Lena"}


def test_build_continuity_brief_chapter_timelines_all_statuses(tmp_path):
    """Chapter timelines must include ALL chapters regardless of status."""
    book, slug = _make_book(tmp_path)
    _add_chapter(book, "01-opening", number=1, status="Outline")
    _add_chapter(book, "02-draft", number=2, status="Draft")
    _add_chapter(book, "03-done", number=3, status="Revision")

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert len(result["chapter_timelines"]) == 3


def test_build_continuity_brief_missing_optional_files_graceful(tmp_path):
    """No setting.md, no canon-log.md → empty lists, no errors."""
    book, slug = _make_book(tmp_path)

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["canonical_calendar"] == []
    assert result["travel_matrix"] == []
    assert result["canon_log_facts"] == []
    assert result["errors"] == []


# ---------------------------------------------------------------------------
# canon_log_facts size cap (Issue #501, follow-up to #500)
# ---------------------------------------------------------------------------


def test_build_continuity_brief_canon_log_facts_not_truncated_under_budget(tmp_path, monkeypatch):
    import tools.db.connection as _db_conn
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)

    db_slug = get_db_slug_for_book(book)
    conn = open_canon_db(db_slug)
    insert_fact(conn, book_num=1, chapter_num=1, subject="Marcus",
                fact="Marcus is a vampire", domain="Character Facts")
    conn.close()

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["canon_log_facts_truncated"] is False
    assert result["canon_log_facts_total_count"] == 1


def test_build_continuity_brief_uses_quarter_of_review_brief_budget(tmp_path, monkeypatch):
    """Issue #501 review finding (originally 'half', tightened to a quarter
    by #504 review finding F2 — see _CANON_FACTS_BUDGET_DIVISOR's comment in
    continuity_brief.py): the division relationship
    (continuity_brief._CANON_FACTS_BUDGET_DIVISOR applied to
    brief_common.CANON_FACTS_CHAR_BUDGET) had no test pinning it — every
    other truncation test used a budget small enough to truncate regardless
    of whether continuity_brief used the full or the divided budget, so a
    regression loosening the division back toward the full budget would
    slip through unnoticed. This test sizes N facts to fit under
    review_brief's FULL budget but not under a QUARTER of it, so it only
    passes if build_continuity_brief actually applies the quartered budget."""
    import json
    import tools.db.connection as _db_conn
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db
    import tools.state.brief_common as brief_common_module

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)

    sample = {
        "fact": "Fact established in chapter 1", "subject": "subject-1",
        "established_in": "Ch 1", "status": "ACTIVE", "notes": "", "domain": "",
        "book_num": 1,
    }
    entry_size = len(json.dumps(sample)) + 1
    full_budget = brief_common_module.CANON_FACTS_CHAR_BUDGET
    quarter_budget = full_budget // 4
    # Enough facts to exceed a QUARTER of the budget, comfortably fewer than
    # needed to exceed the FULL budget.
    fact_count = (quarter_budget // entry_size) + 5
    assert fact_count * entry_size <= full_budget, (
        "test facts must still fit review_brief's FULL budget, or this test "
        "can't distinguish 'used a quarter' from 'used full'"
    )

    db_slug = get_db_slug_for_book(book)
    conn = open_canon_db(db_slug)
    for i in range(1, fact_count + 1):
        insert_fact(conn, book_num=1, chapter_num=i, subject=f"subject-{i}",
                    fact=f"Fact established in chapter {i}", domain="")
    conn.close()

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["canon_log_facts_truncated"] is True, (
        "must truncate under a QUARTER of review_brief's budget even though all facts fit the FULL budget"
    )


def test_build_continuity_brief_ranks_current_book_above_prior_book_when_truncated(tmp_path, monkeypatch):
    """Issue #501: build_continuity_brief must thread its own book_num into
    _cap_canon_facts (via get_book_num(book_root)) — otherwise, under a tight
    budget, an earlier book's facts in a series could starve out this book's
    own canon. Regression guard for the get_book_num wiring specifically:
    removing that wiring (passing current_book_num=None) leaves the rest of
    the suite green, since none of the other tests use a multi-book series."""
    import tools.db.connection as _db_conn
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db
    import tools.state.brief_common as brief_common_module

    # 800, not 400: continuity_brief's divisor is now 4 (Issue #504 review
    # finding F2), not 2, so 800 // 4 = 200 per group — same effective
    # per-group budget these tests originally relied on.
    monkeypatch.setattr(brief_common_module, "CANON_FACTS_CHAR_BUDGET", 800)

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)
    (book / "README.md").write_text(
        '---\ntitle: "Test Book"\nauthor: ""\nseries_number: 2\n---\n\n# Test Book\n',
        encoding="utf-8",
    )

    db_slug = get_db_slug_for_book(book)
    conn = open_canon_db(db_slug)
    for i in range(1, 11):
        insert_fact(conn, book_num=1, chapter_num=i, subject=f"prior-book-{i}",
                    fact=f"Prior book fact established in chapter {i}", domain="")
    for i in range(1, 11):
        insert_fact(conn, book_num=2, chapter_num=i, subject=f"this-book-{i}",
                    fact=f"This book fact established in chapter {i}", domain="")
    conn.close()

    result = build_continuity_brief(book_root=book, book_slug=slug)

    subjects = {f["subject"] for f in result["canon_log_facts"]}
    assert any(s.startswith("this-book-") for s in subjects)
    assert not any(s.startswith("prior-book-") for s in subjects), (
        "current-book facts must be prioritized over an earlier book's facts under a tight budget"
    )


def test_build_continuity_brief_truncation_keeps_earliest_chapters_first(tmp_path, monkeypatch):
    """Issue #501 review finding: a whole-manuscript caller has no single
    'current chapter' to anchor on, so the newest-chapter-first fallback used
    by review_brief would systematically drop the earliest, most foundational
    facts under truncation — exactly what late chapters are most likely to
    accidentally contradict. build_continuity_brief must pass oldest_first=True
    so early chapters survive instead."""
    import tools.db.connection as _db_conn
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db
    import tools.state.brief_common as brief_common_module

    # 800, not 400: continuity_brief's divisor is now 4 (Issue #504 review
    # finding F2), not 2, so 800 // 4 = 200 per group — same effective
    # per-group budget these tests originally relied on.
    monkeypatch.setattr(brief_common_module, "CANON_FACTS_CHAR_BUDGET", 800)

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)

    db_slug = get_db_slug_for_book(book)
    conn = open_canon_db(db_slug)
    for i in range(1, 21):
        insert_fact(conn, book_num=1, chapter_num=i, subject=f"subject-{i}",
                    fact=f"Fact established in chapter {i}", domain="")
    conn.close()

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["canon_log_facts_truncated"] is True
    kept_chapters = {int(f["established_in"].split()[1]) for f in result["canon_log_facts"]}
    assert 1 in kept_chapters
    assert 20 not in kept_chapters


def test_build_continuity_brief_truncates_when_over_budget(tmp_path, monkeypatch):
    """Issue #501: continuity_brief must apply the same size-bounded
    _cap_canon_facts truncation shipped for get_review_brief in #500 —
    unbounded canon_log_facts (plus the all-chapter timelines this brief
    also loads) is structurally guaranteed to blow the MCP tool output
    limit on long books, same failure mode as #500's 330K-char Firelight
    brief. No domain filtering (e.g. dropping domain="timeline") — that
    domain is a documented first-class canon domain, not noise."""
    import tools.db.connection as _db_conn
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db
    import tools.state.brief_common as brief_common_module

    monkeypatch.setattr(brief_common_module, "CANON_FACTS_CHAR_BUDGET", 200)

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)

    db_slug = get_db_slug_for_book(book)
    conn = open_canon_db(db_slug)
    for i in range(20):
        insert_fact(conn, book_num=1, chapter_num=i + 1, subject=f"subject-{i}",
                    fact=f"Fact number {i} established in this chapter", domain="timeline")
    conn.close()

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["canon_log_facts_truncated"] is True
    assert result["canon_log_facts_total_count"] == 20
    assert len(result["canon_log_facts"]) < 20


def test_build_continuity_brief_changed_facts_rank_newest_first_end_to_end(tmp_path, monkeypatch):
    """Issue #506 failure mode 1, end-to-end through the DB -> assembler ->
    cap_canon_facts path — not just the unit-level _cap_canon_facts tests
    against hand-built dict fixtures. build_continuity_brief hardcodes
    oldest_first=True at its call site (protecting early ACTIVE canon on a
    whole-manuscript scan); this pins that CHANGED-status revisions still
    survive newest-first through that same call, guarding against a future
    caller-side wiring regression (e.g. someone flipping or dropping the
    oldest_first=True kwarg) that the internal unit tests structurally
    cannot catch."""
    import tools.db.connection as _db_conn
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db
    import tools.state.brief_common as brief_common_module

    # 800, not a smaller value: continuity_brief's divisor is 4, so
    # 800 // 4 = 200 per group — enough for ~5 of these small entries,
    # matching the per-group budget other tests in this file rely on.
    monkeypatch.setattr(brief_common_module, "CANON_FACTS_CHAR_BUDGET", 800)

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)

    db_slug = get_db_slug_for_book(book)
    conn = open_canon_db(db_slug)
    for i in range(1, 11):
        insert_fact(
            conn, book_num=1, chapter_num=i, subject=f"revision-{i}",
            fact=f"Revised fact from chapter {i}", domain="", is_revision=True,
        )
    conn.close()

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["canon_log_facts_truncated"] is True
    kept_chapters = {
        int(f["established_in"].split()[1]) for f in result["canon_log_facts"]
    }
    assert 10 in kept_chapters, "newest revision must survive truncation end-to-end"
    assert 1 not in kept_chapters, "oldest revision must be dropped first, not kept"


# ---------------------------------------------------------------------------
# chapter_timelines size cap (Issue #504)
# ---------------------------------------------------------------------------


def test_build_continuity_brief_chapter_timelines_not_truncated_under_budget(tmp_path):
    book, slug = _make_book(tmp_path)
    _add_chapter(book, "01-opening", number=1)
    _add_chapter(book, "02-conflict", number=2)

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["chapter_timelines_truncated"] is False
    assert result["chapter_timelines_total_count"] == 2
    assert len(result["chapter_timelines"]) == 2


def test_build_continuity_brief_chapter_timelines_total_count_excludes_non_numbered_dirs(tmp_path):
    """Issue #504 review finding (test-gap pass): chapter_timelines_total_count
    is documented as 'chapters with a parseable timeline grid, NOT the total
    chapter count' — a non-numbered chapters/ subdirectory (notes, appendix,
    archived drafts, etc.) fails _CHAPTER_NUM_RE and is silently excluded
    upstream by _get_all_chapter_timelines(), before total_count is even
    computed. That claim had no test pinning it."""
    book, slug = _make_book(tmp_path)
    _add_chapter(book, "01-opening", number=1)
    _add_chapter(book, "02-conflict", number=2)
    (book / "chapters" / "notes").mkdir()
    (book / "chapters" / "notes" / "README.md").write_text("# Notes\n", encoding="utf-8")

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["chapter_timelines_total_count"] == 2
    assert len(result["chapter_timelines"]) == 2
    assert result["chapter_timelines_truncated"] is False


def test_build_continuity_brief_chapter_timelines_truncates_when_over_budget(tmp_path, monkeypatch):
    """Issue #504: chapter_timelines was the field named as most likely to
    grow with book length (one entry per chapter, unlike character_index/
    character_snapshots which scale with the roughly-fixed cast size). This
    reproduces that failure mode at test scale via a monkeypatched budget,
    the same pattern #500/#501 used for canon_log_facts."""
    import tools.state.continuity_brief as continuity_brief_module

    monkeypatch.setattr(continuity_brief_module, "_CHAPTER_TIMELINES_CHAR_BUDGET", 300)

    book, slug = _make_book(tmp_path)
    for i in range(1, 21):
        _add_chapter(book, f"{i:02d}-chapter", number=i)

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["chapter_timelines_truncated"] is True
    assert result["chapter_timelines_total_count"] == 20
    assert len(result["chapter_timelines"]) < 20


def test_build_continuity_brief_chapter_timelines_truncation_keeps_earliest_chapters_first(
    tmp_path, monkeypatch
):
    """Same 'protect foundational canon' rationale as canon_log_facts's
    oldest_first=True: a whole-manuscript scan has no single 'current
    chapter' to anchor a newest-first cap on, so truncation must keep the
    earliest chapters, not the latest ones."""
    import tools.state.continuity_brief as continuity_brief_module

    monkeypatch.setattr(continuity_brief_module, "_CHAPTER_TIMELINES_CHAR_BUDGET", 300)

    book, slug = _make_book(tmp_path)
    for i in range(1, 21):
        _add_chapter(book, f"{i:02d}-chapter", number=i)

    result = build_continuity_brief(book_root=book, book_slug=slug)

    kept_numbers = {c["number"] for c in result["chapter_timelines"]}
    assert 1 in kept_numbers
    assert 20 not in kept_numbers


# ---------------------------------------------------------------------------
# Total assembled-brief size ceiling (Issue #504)
# ---------------------------------------------------------------------------


def test_build_continuity_brief_total_wire_size_stays_under_ceiling(tmp_path, monkeypatch):
    """Issue #504 (review finding F2 — budgets originally didn't sum to a safe
    total, this fixture now stress-tests all three capped fields at once, not
    just canon_log_facts + chapter_timelines): no single field's cap
    guarantees the ASSEMBLED brief stays small — this pins the combined
    total. Ceiling is set comfortably above the worst-case combined budgets
    (2x canon_log_facts's quartered budget + chapter_timelines's budget +
    canonical_calendar's budget + the small uncapped fields — see
    _CANON_FACTS_BUDGET_DIVISOR's comment in continuity_brief.py for the
    full math) but far below the 330K-char failure #500 hit on an unbounded
    get_review_brief, so a regression that drops a cap (or loosens a budget
    far past its current value) gets caught here even though no individual
    field test would."""
    import json
    import tools.db.connection as _db_conn
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)
    for i in range(1, 51):
        _add_chapter(book, f"{i:02d}-chapter", number=i)
    for i in range(1, 11):
        _add_character(book, f"character-{i}", name=f"Character {i}")
    _write_timeline_md(book, 200)

    db_slug = get_db_slug_for_book(book)
    conn = open_canon_db(db_slug)
    for i in range(500):
        insert_fact(
            conn, book_num=1, chapter_num=(i % 50) + 1, subject=f"subject-{i}",
            fact=f"Fact number {i} established in this chapter, with some extra "
                 f"descriptive detail to approximate a real canon-log entry.",
            domain="timeline",
        )
    conn.close()

    result = build_continuity_brief(book_root=book, book_slug=slug)

    # Ceiling is deliberately tight, not just "well below #500's 330K-char
    # failure": with all three caps active (canon_log_facts, chapter_timelines,
    # AND canonical_calendar all stress-tested by this fixture) this measures
    # ~27K chars; with all three caps disabled it measures ~157K (verified by
    # temporarily patching all three budgets to a no-op value during test
    # development). A loose ceiling would stay green in that broken state and
    # not actually catch the regression it claims to. 45K — matching this
    # repo's own precedent for the sibling get_canon_brief tool
    # (tests/state/test_canon_brief.py's <45_000 assertion, itself set against
    # the real ~50K MCP output limit) — sits with ~1.65x headroom above the
    # capped case (no flake risk) and far below the uncapped case.
    total_size = len(json.dumps(result))
    assert total_size < 45_000, (
        f"assembled continuity brief is {total_size} chars — a cap likely "
        "regressed (compare against #500's 330K-char unbounded failure)"
    )


# ---------------------------------------------------------------------------
# canonical_calendar size cap (Issue #504)
# ---------------------------------------------------------------------------


def _write_timeline_md(book: Path, num_events: int) -> None:
    plot_dir = book / "plot"
    plot_dir.mkdir(exist_ok=True)
    rows = "\n".join(
        f"| Day {i} | Dec {(i % 28) + 1}, 2025 | Thursday | {i:02d}-chapter | Home | "
        f"Event {i} happens | Theo |"
        for i in range(1, num_events + 1)
    )
    body = (
        "# Story Timeline\n\n"
        "## Anchor Point\n\n"
        "| Story Start | Real Date | Day of Week | Notes |\n"
        "|---|---|---|---|\n"
        "| Day 1 | Dec 25, 2025 | Thursday | Story begins here |\n\n"
        "## Event Calendar\n\n"
        "| Story Day | Real Date | Day of Week | Chapter | Location | Key Events | Characters |\n"
        "|---|---|---|---|---|---|---|\n"
        f"{rows}\n"
    )
    (plot_dir / "timeline.md").write_text(body, encoding="utf-8")


def test_build_continuity_brief_canonical_calendar_not_truncated_under_budget(tmp_path):
    book, slug = _make_book(tmp_path)
    _write_timeline_md(book, 2)

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["canonical_calendar_truncated"] is False
    assert result["canonical_calendar_total_count"] == 2
    assert len(result["canonical_calendar"]) == 2


def test_build_continuity_brief_canonical_calendar_truncates_when_over_budget(tmp_path, monkeypatch):
    """Issue #504: canonical_calendar was found during review to scale with
    book length the same way chapter_timelines does (one entry per story-day
    with free-text key_events) — this reproduces truncation at test scale."""
    import tools.state.continuity_brief as continuity_brief_module

    monkeypatch.setattr(continuity_brief_module, "_CANONICAL_CALENDAR_CHAR_BUDGET", 300)

    book, slug = _make_book(tmp_path)
    _write_timeline_md(book, 20)

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["canonical_calendar_truncated"] is True
    assert result["canonical_calendar_total_count"] == 20
    assert len(result["canonical_calendar"]) < 20


def test_build_continuity_brief_canonical_calendar_truncation_keeps_earliest_days_first(
    tmp_path, monkeypatch
):
    import tools.state.continuity_brief as continuity_brief_module

    monkeypatch.setattr(continuity_brief_module, "_CANONICAL_CALENDAR_CHAR_BUDGET", 300)

    book, slug = _make_book(tmp_path)
    _write_timeline_md(book, 20)

    result = build_continuity_brief(book_root=book, book_slug=slug)

    kept_days = {e["story_day"] for e in result["canonical_calendar"]}
    assert 1 in kept_days
    assert 20 not in kept_days


# ---------------------------------------------------------------------------
# Size-cap error-fallback safety (Issue #504 review finding L-3)
# ---------------------------------------------------------------------------


def test_build_continuity_brief_chapter_timelines_cap_failure_falls_back_to_empty_truncated(
    tmp_path, monkeypatch
):
    """The ([], True) fallback in the chapter_timelines_cap recorder.run() call
    is the line that prevents a failure in the cap itself from reintroducing
    an unbounded payload — same safety property canon_log_facts_cap already
    has. Verify it actually engages on a real exception, not just in theory."""
    import tools.state.continuity_brief as continuity_brief_module

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated cap_group failure")

    monkeypatch.setattr(continuity_brief_module, "_cap_group", _boom)

    book, slug = _make_book(tmp_path)
    _add_chapter(book, "01-opening", number=1)
    _add_chapter(book, "02-conflict", number=2)

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["chapter_timelines"] == []
    assert result["chapter_timelines_truncated"] is True
    assert result["chapter_timelines_total_count"] == 2
    assert any(e["component"] == "chapter_timelines_cap" for e in result["errors"])


def test_build_continuity_brief_canon_log_facts_cap_failure_falls_back_to_empty_truncated(
    tmp_path, monkeypatch
):
    """Symmetric to the chapter_timelines_cap test above — canon_log_facts_cap
    uses the identical recorder.run(..., ([], True, len(raw))) fail-safe
    pattern; verify it too actually engages on a real exception."""
    import tools.db.connection as _db_conn
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db
    import tools.state.continuity_brief as continuity_brief_module

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated cap_canon_facts failure")

    monkeypatch.setattr(continuity_brief_module, "_cap_canon_facts", _boom)

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)

    book, slug = _make_book(tmp_path)

    db_slug = get_db_slug_for_book(book)
    conn = open_canon_db(db_slug)
    insert_fact(conn, book_num=1, chapter_num=1, subject="Marcus",
                fact="Marcus is a vampire", domain="Character Facts")
    insert_fact(conn, book_num=1, chapter_num=2, subject="Lena",
                fact="Lena is a witch", domain="Character Facts")
    conn.close()

    result = build_continuity_brief(book_root=book, book_slug=slug)

    assert result["canon_log_facts"] == []
    assert result["canon_log_facts_truncated"] is True
    assert result["canon_log_facts_total_count"] == 2
    assert any(e["component"] == "canon_log_facts_cap" for e in result["errors"])
