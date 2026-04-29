"""Tests for memoir ethics checker (Phase 3, Issue #65).

Covers:
- read_people_for_ethics: reads person profiles from people/ dir
- check_consent: classifies each person as PASS / WARN / FAIL
- Overall verdict: FAIL beats WARN beats PASS
- Fiction books: raises ValueError (ethics checker is memoir-only)
- Edge cases: empty people/, missing person_category, missing consent_status
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.analysis.memoir_ethics import check_consent, read_people_for_ethics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book(tmp_path: Path, book_category: str = "memoir") -> Path:
    book = tmp_path / "my-memoir"
    book.mkdir()
    readme = f"""---
title: "My Memoir"
slug: "my-memoir"
book_category: {book_category}
status: Drafting
---

# My Memoir
"""
    (book / "README.md").write_text(readme, encoding="utf-8")
    (book / "people").mkdir()
    return book


def _add_person(
    book: Path,
    slug: str,
    name: str,
    person_category: str = "private-living-person",
    consent_status: str = "confirmed-consent",
    anonymization: str = "none",
    real_name: str = "",
) -> None:
    real_name_line = f"real_name: {real_name}" if real_name else ""
    content = f"""---
name: {name}
person_category: {person_category}
consent_status: {consent_status}
anonymization: {anonymization}
{real_name_line}
---

Notes about {name}.
"""
    (book / "people" / f"{slug}.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# read_people_for_ethics
# ---------------------------------------------------------------------------


class TestReadPeopleForEthics:
    def test_returns_empty_list_when_no_people_dir(self, tmp_path):
        book = tmp_path / "bare-book"
        book.mkdir()
        (book / "README.md").write_text("---\nbook_category: memoir\n---\n", encoding="utf-8")
        result = read_people_for_ethics(book)
        assert result == []

    def test_returns_empty_list_when_people_dir_empty(self, tmp_path):
        book = _make_book(tmp_path)
        result = read_people_for_ethics(book)
        assert result == []

    def test_skips_index_md(self, tmp_path):
        book = _make_book(tmp_path)
        (book / "people" / "INDEX.md").write_text("# People Index\n", encoding="utf-8")
        result = read_people_for_ethics(book)
        assert result == []

    def test_returns_person_with_all_fields(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "alice", "Alice Smith", consent_status="confirmed-consent")
        result = read_people_for_ethics(book)
        assert len(result) == 1
        p = result[0]
        assert p["slug"] == "alice"
        assert p["name"] == "Alice Smith"
        assert p["consent_status"] == "confirmed-consent"
        assert p["person_category"] == "private-living-person"
        assert p["anonymization"] == "none"

    def test_returns_multiple_people(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "alice", "Alice", consent_status="confirmed-consent")
        _add_person(book, "bob", "Bob", consent_status="refused")
        result = read_people_for_ethics(book)
        slugs = {p["slug"] for p in result}
        assert slugs == {"alice", "bob"}

    def test_handles_missing_frontmatter_fields(self, tmp_path):
        book = _make_book(tmp_path)
        (book / "people" / "unknown.md").write_text("---\nname: Unknown\n---\nNo category here.\n", encoding="utf-8")
        result = read_people_for_ethics(book)
        assert len(result) == 1
        p = result[0]
        assert p["consent_status"] == ""
        assert p["person_category"] == ""


# ---------------------------------------------------------------------------
# check_consent — individual verdicts
# ---------------------------------------------------------------------------


class TestCheckConsentIndividualVerdicts:
    def test_confirmed_consent_is_pass(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "alice", "Alice", consent_status="confirmed-consent")
        result = check_consent(book)
        alice = next(p for p in result["people"] if p["slug"] == "alice")
        assert alice["verdict"] == "PASS"

    def test_not_required_is_pass(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(
            book,
            "pub-fig",
            "Famous Politician",
            person_category="public-figure",
            consent_status="not-required",
        )
        result = check_consent(book)
        person = result["people"][0]
        assert person["verdict"] == "PASS"

    def test_refused_is_fail(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "ex", "Ex Partner", consent_status="refused")
        result = check_consent(book)
        person = result["people"][0]
        assert person["verdict"] == "FAIL"

    def test_pending_is_warn(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "friend", "Old Friend", consent_status="pending")
        result = check_consent(book)
        person = result["people"][0]
        assert person["verdict"] == "WARN"

    def test_not_asking_is_warn(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "abuser", "The Abuser", consent_status="not-asking")
        result = check_consent(book)
        person = result["people"][0]
        assert person["verdict"] == "WARN"

    def test_missing_consent_status_is_warn(self, tmp_path):
        book = _make_book(tmp_path)
        (book / "people" / "mystery.md").write_text(
            "---\nname: Mystery Person\nperson_category: private-living-person\n---\n",
            encoding="utf-8",
        )
        result = check_consent(book)
        person = result["people"][0]
        assert person["verdict"] == "WARN"

    def test_unknown_consent_status_is_warn(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "weird", "Weird Person", consent_status="some-unknown-value")
        result = check_consent(book)
        person = result["people"][0]
        assert person["verdict"] == "WARN"

    def test_missing_person_category_is_warn(self, tmp_path):
        book = _make_book(tmp_path)
        (book / "people" / "nocat.md").write_text(
            "---\nname: No Category\nconsent_status: confirmed-consent\n---\n",
            encoding="utf-8",
        )
        result = check_consent(book)
        person = result["people"][0]
        assert person["verdict"] == "WARN"

    def test_verdict_includes_reason_string(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "bob", "Bob", consent_status="refused")
        result = check_consent(book)
        person = result["people"][0]
        assert isinstance(person["reason"], str)
        assert len(person["reason"]) > 0


# ---------------------------------------------------------------------------
# check_consent — overall verdicts
# ---------------------------------------------------------------------------


class TestCheckConsentOverallVerdict:
    def test_all_pass_gives_overall_pass(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "alice", "Alice", consent_status="confirmed-consent")
        _add_person(book, "bob", "Bob", person_category="deceased", consent_status="not-required")
        result = check_consent(book)
        assert result["overall"] == "PASS"

    def test_one_warn_gives_overall_warn(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "alice", "Alice", consent_status="confirmed-consent")
        _add_person(book, "bob", "Bob", consent_status="pending")
        result = check_consent(book)
        assert result["overall"] == "WARN"

    def test_one_fail_gives_overall_fail(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "alice", "Alice", consent_status="confirmed-consent")
        _add_person(book, "bob", "Bob", consent_status="refused")
        result = check_consent(book)
        assert result["overall"] == "FAIL"

    def test_fail_beats_warn(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "warned", "Warned", consent_status="pending")
        _add_person(book, "failed", "Failed", consent_status="refused")
        result = check_consent(book)
        assert result["overall"] == "FAIL"

    def test_empty_people_gives_overall_pass(self, tmp_path):
        book = _make_book(tmp_path)
        result = check_consent(book)
        assert result["overall"] == "PASS"
        assert result["people"] == []

    def test_result_includes_counts(self, tmp_path):
        book = _make_book(tmp_path)
        _add_person(book, "alice", "Alice", consent_status="confirmed-consent")
        _add_person(book, "bob", "Bob", consent_status="pending")
        _add_person(book, "carol", "Carol", consent_status="refused")
        result = check_consent(book)
        assert result["pass_count"] == 1
        assert result["warn_count"] == 1
        assert result["fail_count"] == 1

    def test_result_includes_book_slug(self, tmp_path):
        book = _make_book(tmp_path)
        result = check_consent(book)
        assert result["book_slug"] == "my-memoir"


# ---------------------------------------------------------------------------
# check_consent — memoir-only gate
# ---------------------------------------------------------------------------


class TestCheckConsentMemoirOnly:
    def test_raises_for_fiction_book(self, tmp_path):
        book = _make_book(tmp_path, book_category="fiction")
        with pytest.raises(ValueError, match="memoir"):
            check_consent(book)

    def test_raises_when_no_readme(self, tmp_path):
        book = tmp_path / "orphan"
        book.mkdir()
        (book / "people").mkdir()
        with pytest.raises((ValueError, FileNotFoundError)):
            check_consent(book)
