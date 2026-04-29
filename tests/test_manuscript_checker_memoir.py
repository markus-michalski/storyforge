"""Tests for memoir-specific manuscript checker passes (Phase 3, Issue #61).

Covers:
- _read_book_category: parses book_category from README frontmatter
- _read_people_profiles: reads person profiles from people/ directory
- _scan_timeline_ambiguity: flags chapters with excessive temporal hand-waving
- _scan_reflective_platitudes: flags chapters heavy with lesson-summary narration
- _scan_tidy_lesson_endings: flags chapters whose last paragraph ends on a moral
- _scan_anonymization_leak: flags real names appearing despite anonymization
- _scan_real_people_consistency: flags inconsistent name forms across chapters
- scan_repetitions: memoir checks run only for memoir books, not fiction
"""

from __future__ import annotations

from pathlib import Path

from tools.analysis.manuscript_checker import (
    _read_book_category,
    _read_people_profiles,
    _scan_anonymization_leak,
    _scan_real_people_consistency,
    _scan_reflective_platitudes,
    _scan_tidy_lesson_endings,
    _scan_timeline_ambiguity,
    scan_repetitions,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book(tmp_path: Path, book_category: str = "memoir") -> Path:
    """Create a minimal book scaffold with the given book_category."""
    book = tmp_path / "my-memoir"
    book.mkdir()
    readme = f"""---
title: "My Memoir"
slug: "my-memoir"
book_category: {book_category}
book_type: novel
status: Drafting
---

# My Memoir
"""
    (book / "README.md").write_text(readme, encoding="utf-8")
    (book / "chapters").mkdir()
    return book


def _add_chapter(book: Path, slug: str, prose: str) -> Path:
    ch = book / "chapters" / slug
    ch.mkdir(parents=True, exist_ok=True)
    draft = ch / "draft.md"
    draft.write_text(prose, encoding="utf-8")
    return draft


def _add_person(
    book: Path,
    slug: str,
    name: str,
    anonymization: str = "none",
    real_name: str = "",
) -> Path:
    people_dir = book / "people"
    people_dir.mkdir(exist_ok=True)
    real_name_line = f'real_name: "{real_name}"\n' if real_name else ""
    content = f"""---
name: "{name}"
slug: "{slug}"
relationship: "friend"
person_category: "inner-circle"
consent_status: "obtained"
anonymization: "{anonymization}"
{real_name_line}---

# {name}
"""
    path = people_dir / f"{slug}.md"
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _read_book_category
# ---------------------------------------------------------------------------


class TestReadBookCategory:
    def test_returns_memoir_when_set(self, tmp_path):
        book = _make_book(tmp_path, book_category="memoir")
        assert _read_book_category(book) == "memoir"

    def test_returns_fiction_when_set(self, tmp_path):
        book = _make_book(tmp_path, book_category="fiction")
        assert _read_book_category(book) == "fiction"

    def test_defaults_to_fiction_when_missing(self, tmp_path):
        book = tmp_path / "no-category"
        book.mkdir()
        (book / "README.md").write_text("---\ntitle: X\n---\n# X\n", encoding="utf-8")
        assert _read_book_category(book) == "fiction"

    def test_defaults_to_fiction_when_no_readme(self, tmp_path):
        book = tmp_path / "empty"
        book.mkdir()
        assert _read_book_category(book) == "fiction"


# ---------------------------------------------------------------------------
# _read_people_profiles
# ---------------------------------------------------------------------------


class TestReadPeopleProfiles:
    def test_empty_without_people_dir(self, tmp_path):
        book = _make_book(tmp_path)
        assert _read_people_profiles(book) == []

    def test_reads_non_anonymized_person(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "sarah", "Sarah Johnson")
        profiles = _read_people_profiles(book)
        assert len(profiles) == 1
        assert profiles[0]["name"] == "Sarah Johnson"
        assert profiles[0]["anonymization"] == "none"
        assert profiles[0]["real_name"] == ""

    def test_reads_anonymized_person_with_real_name(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "anna", "Anna", anonymization="name-changed", real_name="Maria Schmidt")
        profiles = _read_people_profiles(book)
        assert len(profiles) == 1
        assert profiles[0]["name"] == "Anna"
        assert profiles[0]["anonymization"] == "name-changed"
        assert profiles[0]["real_name"] == "Maria Schmidt"

    def test_skips_index_file(self, tmp_path):
        book = _make_book(tmp_path)
        people_dir = book / "people"
        people_dir.mkdir()
        (people_dir / "INDEX.md").write_text("# Index\n", encoding="utf-8")
        _add_person(book, "bob", "Bob")
        profiles = _read_people_profiles(book)
        assert len(profiles) == 1
        assert profiles[0]["slug"] == "bob"


# ---------------------------------------------------------------------------
# _scan_timeline_ambiguity
# ---------------------------------------------------------------------------


TIMELINE_VAGUE_PROSE = (
    """
I got on the bus. At some point, I arrived. Eventually I found the house.
Years later, it all made sense. One day I would understand. Back then I was naive.
Around that time, things shifted. Before long, everything changed.
The summer was long and hot and full of waiting.
"""
    * 15
)  # repeat to exceed density threshold


TIMELINE_CLEAN_PROSE = (
    """
On the morning of June 14th, 1987, I woke at five to the smell of rain.
By nine o'clock I was on the bus. At noon I sat across from my father.
That Tuesday felt like the longest day of my life.
"""
    * 15
)


class TestScanTimelineAmbiguity:
    def test_no_findings_for_clean_chapter(self, tmp_path):
        book = _make_book(tmp_path)
        _add_chapter(book, "01-morning", TIMELINE_CLEAN_PROSE)
        findings = _scan_timeline_ambiguity(book)
        assert findings == []

    def test_flags_vague_chapter(self, tmp_path):
        book = _make_book(tmp_path)
        _add_chapter(book, "01-vague", TIMELINE_VAGUE_PROSE)
        findings = _scan_timeline_ambiguity(book)
        assert len(findings) >= 1
        assert findings[0].category == "timeline_ambiguity"

    def test_finding_shows_chapter_slug(self, tmp_path):
        book = _make_book(tmp_path)
        _add_chapter(book, "01-vague", TIMELINE_VAGUE_PROSE)
        findings = _scan_timeline_ambiguity(book)
        assert "01-vague" in findings[0].phrase

    def test_severity_high_at_extreme_density(self, tmp_path):
        book = _make_book(tmp_path)
        # Heavy repetition of vague phrases
        prose = "At some point eventually one day back then. " * 100
        _add_chapter(book, "01-dense", prose)
        findings = _scan_timeline_ambiguity(book)
        assert any(f.severity == "high" for f in findings)

    def test_no_findings_for_empty_book(self, tmp_path):
        book = _make_book(tmp_path)
        assert _scan_timeline_ambiguity(book) == []


# ---------------------------------------------------------------------------
# _scan_reflective_platitudes
# ---------------------------------------------------------------------------


PLATITUDE_PROSE = (
    """
Looking back, I realize how blind I was. In retrospect, I should have known.
What I learned that day has stayed with me forever.
I now understand why she did it. I came to realize the truth only years later.
In hindsight, the signs were obvious. It taught me that nothing lasts.
"""
    * 5
)


PLATITUDE_CLEAN_PROSE = (
    """
She slammed the door. The glass rattled in the frame.
I stood in the hall not moving, listening to the silence settle.
The smell of coffee came from the kitchen, and I had nowhere to go.
"""
    * 20
)


class TestScanReflectivePlatitudes:
    def test_no_findings_for_scene_grounded_chapter(self, tmp_path):
        book = _make_book(tmp_path)
        _add_chapter(book, "01-scene", PLATITUDE_CLEAN_PROSE)
        findings = _scan_reflective_platitudes(book)
        assert findings == []

    def test_flags_platitude_heavy_chapter(self, tmp_path):
        book = _make_book(tmp_path)
        _add_chapter(book, "01-lessons", PLATITUDE_PROSE)
        findings = _scan_reflective_platitudes(book)
        assert len(findings) >= 1
        assert findings[0].category == "reflective_platitude"

    def test_finding_contains_chapter_slug(self, tmp_path):
        book = _make_book(tmp_path)
        _add_chapter(book, "03-reflection", PLATITUDE_PROSE)
        findings = _scan_reflective_platitudes(book)
        assert "03-reflection" in findings[0].phrase

    def test_no_findings_for_empty_book(self, tmp_path):
        book = _make_book(tmp_path)
        assert _scan_reflective_platitudes(book) == []


# ---------------------------------------------------------------------------
# _scan_tidy_lesson_endings
# ---------------------------------------------------------------------------


LESSON_ENDING_CHAPTER = """
She came in from the cold. The kettle was already boiling.
We sat across from each other for a long time.
Nobody said anything.

That winter taught me that silence can be its own kind of answer.
It made me realize some distances cannot be closed no matter how many years pass.
I had learned this lesson the hard way, and I would not forget it.
"""

SCENE_ENDING_CHAPTER = """
She came in from the cold. The kettle was already boiling.
We sat across from each other for a long time.
Nobody said anything.

She poured two cups and pushed one across the table.
I wrapped my hands around it and looked out the window at the snow.
"""


class TestScanTidyLessonEndings:
    def test_no_findings_for_scene_ending(self, tmp_path):
        book = _make_book(tmp_path)
        _add_chapter(book, "01-scene", SCENE_ENDING_CHAPTER)
        findings = _scan_tidy_lesson_endings(book)
        assert findings == []

    def test_flags_lesson_ending_chapter(self, tmp_path):
        book = _make_book(tmp_path)
        _add_chapter(book, "01-lesson", LESSON_ENDING_CHAPTER)
        findings = _scan_tidy_lesson_endings(book)
        assert len(findings) >= 1
        assert findings[0].category == "tidy_lesson_ending"

    def test_finding_contains_chapter_slug(self, tmp_path):
        book = _make_book(tmp_path)
        _add_chapter(book, "05-winter", LESSON_ENDING_CHAPTER)
        findings = _scan_tidy_lesson_endings(book)
        assert "05-winter" in findings[0].phrase

    def test_no_findings_for_empty_book(self, tmp_path):
        book = _make_book(tmp_path)
        assert _scan_tidy_lesson_endings(book) == []


# ---------------------------------------------------------------------------
# _scan_anonymization_leak
# ---------------------------------------------------------------------------


class TestScanAnonymizationLeak:
    def test_no_findings_without_people_dir(self, tmp_path):
        book = _make_book(tmp_path)
        _add_chapter(book, "01-ch", "She walked in. Maria smiled.")
        assert _scan_anonymization_leak(book) == []

    def test_no_findings_when_only_pseudonym_used(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "anna", "Anna", anonymization="name-changed", real_name="Maria Schmidt")
        _add_chapter(book, "01-ch", "Anna smiled and sat down. Anna was kind.")
        findings = _scan_anonymization_leak(book)
        assert findings == []

    def test_flags_real_name_in_chapter(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "anna", "Anna", anonymization="name-changed", real_name="Maria Schmidt")
        _add_chapter(book, "01-ch", "Maria Schmidt walked in and sat beside me.")
        findings = _scan_anonymization_leak(book)
        assert len(findings) == 1
        assert findings[0].category == "anonymization_leak"
        assert findings[0].severity == "high"

    def test_real_name_case_insensitive(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "anna", "Anna", anonymization="name-changed", real_name="Maria Schmidt")
        _add_chapter(book, "01-ch", "MARIA SCHMIDT was there.")
        findings = _scan_anonymization_leak(book)
        assert len(findings) == 1

    def test_no_findings_for_non_anonymized_person(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "bob", "Bob", anonymization="none")
        _add_chapter(book, "01-ch", "Bob walked in.")
        assert _scan_anonymization_leak(book) == []

    def test_finding_references_real_and_pseudonym_names(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "anna", "Anna", anonymization="name-changed", real_name="Maria Schmidt")
        _add_chapter(book, "01-ch", "Maria Schmidt walked in.")
        findings = _scan_anonymization_leak(book)
        assert "Maria Schmidt" in findings[0].phrase
        assert "Anna" in findings[0].phrase

    def test_no_findings_for_empty_book(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "anna", "Anna", anonymization="name-changed", real_name="Maria Schmidt")
        assert _scan_anonymization_leak(book) == []


# ---------------------------------------------------------------------------
# _scan_real_people_consistency
# ---------------------------------------------------------------------------


class TestScanRealPeopleConsistency:
    def test_no_findings_without_people_dir(self, tmp_path):
        book = _make_book(tmp_path)
        _add_chapter(book, "01-ch", "She came in.")
        assert _scan_real_people_consistency(book) == []

    def test_no_findings_when_name_consistent(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "anna", "Anna")
        _add_chapter(book, "01-ch", "Anna sat down. Anna smiled.")
        _add_chapter(book, "02-ch", "Anna came back. Anna laughed.")
        findings = _scan_real_people_consistency(book)
        assert findings == []

    def test_flags_inconsistent_capitalisation(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "anna", "Anna")
        _add_chapter(book, "01-ch", "Anna sat down.")
        _add_chapter(book, "02-ch", "anna came back.")  # lowercase variant
        findings = _scan_real_people_consistency(book)
        assert len(findings) == 1
        assert findings[0].category == "real_people_consistency"

    def test_no_findings_for_empty_book(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "anna", "Anna")
        assert _scan_real_people_consistency(book) == []


# ---------------------------------------------------------------------------
# scan_repetitions — memoir mode integration
# ---------------------------------------------------------------------------


class TestScanRepetitionsMemoirMode:
    def test_memoir_checks_run_for_memoir_book(self, tmp_path):
        """Anonymization leak must appear in results for memoir books."""
        book = _make_book(tmp_path, book_category="memoir")
        _add_person(book, "anna", "Anna", anonymization="name-changed", real_name="Maria Schmidt")
        _add_chapter(book, "01-ch", "Maria Schmidt walked in and sat beside me. " * 20)
        result = scan_repetitions(book)
        categories = {f["category"] for f in result["findings"]}
        assert "anonymization_leak" in categories

    def test_memoir_checks_do_not_run_for_fiction_book(self, tmp_path):
        """Memoir-specific categories must not appear for fiction books."""
        book = _make_book(tmp_path, book_category="fiction")
        # Even if people/ dir exists (unusual for fiction, but shouldn't crash)
        _add_person(book, "anna", "Anna", anonymization="name-changed", real_name="Maria Schmidt")
        _add_chapter(book, "01-ch", "Maria Schmidt walked in. " * 20)
        result = scan_repetitions(book)
        memoir_cats = {
            "anonymization_leak",
            "tidy_lesson_ending",
            "reflective_platitude",
            "timeline_ambiguity",
            "real_people_consistency",
        }
        found_cats = {f["category"] for f in result["findings"]}
        assert memoir_cats.isdisjoint(found_cats), f"Memoir checks ran on fiction book: {memoir_cats & found_cats}"

    def test_anonymization_leak_is_high_priority_in_sort(self, tmp_path):
        """anonymization_leak findings must appear before clichés in the output."""
        book = _make_book(tmp_path, book_category="memoir")
        _add_person(book, "anna", "Anna", anonymization="name-changed", real_name="Maria Schmidt")
        prose = (
            "Maria Schmidt walked in. Blood ran cold. "
            "Maria Schmidt sat down. Blood ran cold. "
            "Maria Schmidt left. Blood ran cold. "
        ) * 10
        _add_chapter(book, "01-ch", prose)
        result = scan_repetitions(book)
        cats_in_order = [f["category"] for f in result["findings"]]
        leak_idx = next(i for i, c in enumerate(cats_in_order) if c == "anonymization_leak")
        cliche_idx = next((i for i, c in enumerate(cats_in_order) if c == "cliche"), len(cats_in_order))
        assert leak_idx < cliche_idx, f"anonymization_leak (pos {leak_idx}) should be before cliche (pos {cliche_idx})"
