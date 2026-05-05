"""Tests for tools.state.review_brief — Issue #99.

Verifies that build_review_brief() returns the correct structured payload
and that the individual parsers handle the template format correctly.
"""

from __future__ import annotations

from pathlib import Path

from tools.state.review_brief import (
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
        "tonal_rules",
        "active_rules",
        "active_callbacks",
        "errors",
    }
    assert expected_keys <= set(result.keys())


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


def test_build_review_brief_canon_log_facts_populated(tmp_path):
    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)
    (book / "plot" / "canon-log.md").write_text(CANON_LOG_SAMPLE, encoding="utf-8")

    result = build_review_brief(
        book_root=book,
        book_slug=slug,
        chapter_slug="01-opening",
    )

    assert len(result["canon_log_facts"]) == 3
    changed = [f for f in result["canon_log_facts"] if f["status"] == "CHANGED"]
    assert len(changed) == 1


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


def test_build_review_brief_active_rules_from_claudemd(tmp_path):
    book, slug = _make_book(tmp_path)
    _make_chapter(book, "01-opening", number=1)
    (book / "CLAUDE.md").write_text(
        "# Book Rules\n\n"
        "## Rules\n\n"
        "- Never contradict the canon log\n"
        "- Always load the timeline before writing\n\n"
        "## Callback Register\n\n"
        "- Marcus must reveal his secret by Ch 10\n",
        encoding="utf-8",
    )

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
    assert result["tonal_rules"] == {}
    assert result["errors"] == []
