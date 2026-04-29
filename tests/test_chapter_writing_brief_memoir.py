"""Tests for the memoir-mode chapter writing brief (Issue #57, Path E Phase 2).

`chapter-writer` branches on `book_category`. Memoir books load real-people
profiles from `people/` (with the four-category ethics schema), surface
`consent_status_warnings` before drafting, and skip the world/setting.md +
canon-log fiction-only loads. This module covers:

- `book_category` exposure on the brief
- `characters_present` payload differs per category (memoir surfaces
  relationship + person_category + consent_status + anonymization,
  not role + knowledge + tactical)
- `consent_status_warnings` populated for memoir scenes
- Fiction brief unchanged — regression guard for the historical shape
"""

from __future__ import annotations

from pathlib import Path

from tools.state.chapter_writing_brief import build_chapter_writing_brief


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_memoir_book(tmp_path: Path, *, category: str = "memoir") -> tuple[Path, Path]:
    """Create a minimal memoir scaffold and return (book_root, plugin_root)."""
    book = tmp_path / "test-memoir"
    (book / "chapters").mkdir(parents=True)
    (book / "people").mkdir()
    (book / "plot").mkdir()
    (book / "README.md").write_text(
        f'---\ntitle: "Test Memoir"\nbook_category: "{category}"\n---\n\n# Test Memoir\n',
        encoding="utf-8",
    )
    return book, Path(__file__).resolve().parent.parent


def _make_fiction_book(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal fiction scaffold."""
    book = tmp_path / "test-fiction"
    (book / "chapters").mkdir(parents=True)
    (book / "characters").mkdir()
    (book / "plot").mkdir()
    (book / "world").mkdir()
    (book / "README.md").write_text(
        '---\ntitle: "Test Fiction"\nbook_category: "fiction"\n---\n\n# Test Fiction\n',
        encoding="utf-8",
    )
    return book, Path(__file__).resolve().parent.parent


def _make_chapter(
    book: Path,
    slug: str,
    *,
    number: int,
    title: str,
    pov: str = "",
    body: str = "",
) -> None:
    chapter = book / "chapters" / slug
    chapter.mkdir(parents=True)
    pov_line = f'pov_character: "{pov}"\n' if pov else ""
    (chapter / "README.md").write_text(
        f'---\ntitle: "{title}"\nnumber: {number}\nstatus: "Draft"\n{pov_line}---\n\n# {title}\n\n{body}\n',
        encoding="utf-8",
    )


def _make_person(
    book: Path,
    slug: str,
    *,
    name: str,
    relationship: str = "",
    person_category: str = "private-living-person",
    consent_status: str = "pending",
    anonymization: str = "none",
) -> None:
    text = (
        "---\n"
        f'name: "{name}"\n'
        f'relationship: "{relationship}"\n'
        f'person_category: "{person_category}"\n'
        f'consent_status: "{consent_status}"\n'
        f'anonymization: "{anonymization}"\n'
        "---\n\n"
        f"# {name}\n"
    )
    (book / "people" / f"{slug}.md").write_text(text, encoding="utf-8")


def _make_character(
    book: Path,
    slug: str,
    *,
    name: str,
    role: str = "supporting",
) -> None:
    text = f'---\nname: "{name}"\nrole: "{role}"\n---\n\n# {name}\n'
    (book / "characters" / f"{slug}.md").write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# book_category exposure
# ---------------------------------------------------------------------------


class TestBookCategoryExposure:
    """The brief surfaces book_category so the skill can branch."""

    def test_memoir_book_category_exposed(self, tmp_path: Path):
        book, plugin_root = _make_memoir_book(tmp_path)
        _make_chapter(book, "01-opening", number=1, title="Opening")

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-memoir",
            chapter_slug="01-opening",
            plugin_root=plugin_root,
        )
        assert brief["book_category"] == "memoir"

    def test_fiction_book_category_exposed(self, tmp_path: Path):
        book, plugin_root = _make_fiction_book(tmp_path)
        _make_chapter(book, "01-opening", number=1, title="Opening")

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-fiction",
            chapter_slug="01-opening",
            plugin_root=plugin_root,
        )
        assert brief["book_category"] == "fiction"

    def test_legacy_book_without_category_defaults_to_fiction(self, tmp_path: Path):
        # Books written before #54 have no book_category. The brief must
        # default to fiction so the historical writing flow stays intact.
        book = tmp_path / "legacy"
        (book / "chapters").mkdir(parents=True)
        (book / "characters").mkdir()
        (book / "plot").mkdir()
        (book / "world").mkdir()
        (book / "README.md").write_text('---\ntitle: "Legacy"\n---\n\n# Legacy\n', encoding="utf-8")
        _make_chapter(book, "01-opening", number=1, title="Opening")

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="legacy",
            chapter_slug="01-opening",
            plugin_root=Path(__file__).resolve().parent.parent,
        )
        assert brief["book_category"] == "fiction"


# ---------------------------------------------------------------------------
# characters_present payload differs per category
# ---------------------------------------------------------------------------


class TestCharactersPresentBranching:
    """Memoir loads people/ with the ethics schema; fiction loads characters/."""

    def test_memoir_loads_people_not_characters(self, tmp_path: Path):
        book, plugin_root = _make_memoir_book(tmp_path)
        _make_person(
            book,
            "maria",
            name="Maria",
            relationship="sister",
            person_category="private-living-person",
            consent_status="confirmed-consent",
        )
        # Even if a stray characters/ directory exists, people/ wins for memoir.
        (book / "characters").mkdir(exist_ok=True)
        _make_chapter(
            book,
            "01-opening",
            number=1,
            title="Opening",
            pov="Maria",
            body="Maria walked through the kitchen.",
        )

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-memoir",
            chapter_slug="01-opening",
            plugin_root=plugin_root,
        )
        people = brief["characters_present"]
        assert len(people) == 1
        person = people[0]
        # Memoir schema fields surface
        assert person["name"] == "Maria"
        assert person["relationship"] == "sister"
        assert person["person_category"] == "private-living-person"
        assert person["consent_status"] == "confirmed-consent"
        assert person["anonymization"] == "none"
        # Fiction-only fields absent
        assert "role" not in person

    def test_fiction_loads_characters_with_role(self, tmp_path: Path):
        book, plugin_root = _make_fiction_book(tmp_path)
        _make_character(book, "alex", name="Alex", role="protagonist")
        _make_chapter(
            book,
            "01-opening",
            number=1,
            title="Opening",
            pov="Alex",
            body="Alex stepped into the alley.",
        )

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-fiction",
            chapter_slug="01-opening",
            plugin_root=plugin_root,
        )
        chars = brief["characters_present"]
        assert len(chars) == 1
        char = chars[0]
        # Fiction schema fields surface
        assert char["name"] == "Alex"
        assert char["role"] == "protagonist"
        # Memoir-only fields absent
        assert "consent_status" not in char
        assert "person_category" not in char

    def test_memoir_real_name_excluded_from_brief(self, tmp_path: Path):
        # real_name is private — it stays in the people file, never on the
        # brief that chapter-writer reads. Pseudonymized portrayals must
        # not leak the real name into the writing context.
        book, plugin_root = _make_memoir_book(tmp_path)
        person_path = book / "people" / "the-doctor.md"
        person_path.write_text(
            "---\n"
            'name: "The doctor"\n'
            'relationship: "diagnosing physician"\n'
            'person_category: "anonymized-or-composite"\n'
            'consent_status: "not-asking"\n'
            'anonymization: "pseudonym"\n'
            'real_name: "Dr. Henrik Lassen"\n'
            "---\n# The doctor\n",
            encoding="utf-8",
        )
        _make_chapter(
            book,
            "01-diagnosis",
            number=1,
            title="Diagnosis",
            pov="The doctor",
            body="The doctor sat across from her.",
        )

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-memoir",
            chapter_slug="01-diagnosis",
            plugin_root=plugin_root,
        )
        person = brief["characters_present"][0]
        assert "real_name" not in person


# ---------------------------------------------------------------------------
# consent_status_warnings for memoir
# ---------------------------------------------------------------------------


class TestConsentStatusWarnings:
    """The brief surfaces consent issues before drafting any memoir scene."""

    def test_pending_consent_produces_warning(self, tmp_path: Path):
        book, plugin_root = _make_memoir_book(tmp_path)
        _make_person(
            book,
            "maria",
            name="Maria",
            relationship="sister",
            consent_status="pending",
        )
        _make_chapter(
            book,
            "01-opening",
            number=1,
            title="Opening",
            pov="Maria",
            body="Maria sits across the table.",
        )

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-memoir",
            chapter_slug="01-opening",
            plugin_root=plugin_root,
        )
        warnings = brief["consent_status_warnings"]
        assert len(warnings) == 1
        assert warnings[0]["tier"] == "pending"
        assert warnings[0]["person"] == "Maria"

    def test_refused_consent_produces_warning(self, tmp_path: Path):
        book, plugin_root = _make_memoir_book(tmp_path)
        _make_person(
            book,
            "the-ex",
            name="Daniel",
            relationship="ex-partner",
            consent_status="refused",
        )
        _make_chapter(
            book,
            "02-disclosure",
            number=2,
            title="Disclosure",
            pov="Daniel",
            body="Daniel comes to the door.",
        )

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-memoir",
            chapter_slug="02-disclosure",
            plugin_root=plugin_root,
        )
        warnings = brief["consent_status_warnings"]
        assert any(w["tier"] == "refused" for w in warnings)

    def test_missing_consent_produces_warning(self, tmp_path: Path):
        # Person file with no consent_status — the user has not yet decided.
        book, plugin_root = _make_memoir_book(tmp_path)
        person_path = book / "people" / "anonymous.md"
        person_path.write_text(
            "---\n"
            'name: "Anonymous"\n'
            'relationship: "neighbor"\n'
            'person_category: "private-living-person"\n'
            "---\n# Anonymous\n",
            encoding="utf-8",
        )
        _make_chapter(
            book,
            "03-encounter",
            number=3,
            title="Encounter",
            pov="Anonymous",
            body="Anonymous waved from the porch.",
        )

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-memoir",
            chapter_slug="03-encounter",
            plugin_root=plugin_root,
        )
        warnings = brief["consent_status_warnings"]
        assert any(w["tier"] == "missing" for w in warnings)

    def test_confirmed_consent_produces_no_warning(self, tmp_path: Path):
        book, plugin_root = _make_memoir_book(tmp_path)
        _make_person(
            book,
            "father",
            name="Father",
            relationship="father",
            consent_status="confirmed-consent",
        )
        _make_person(
            book,
            "uncle",
            name="Uncle",
            relationship="uncle",
            person_category="deceased",
            consent_status="not-required",
        )
        _make_chapter(
            book,
            "04-family",
            number=4,
            title="Family",
            pov="Father",
            body="Father and Uncle were close once.",
        )

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-memoir",
            chapter_slug="04-family",
            plugin_root=plugin_root,
        )
        assert brief["consent_status_warnings"] == []

    def test_fiction_brief_has_no_consent_warnings(self, tmp_path: Path):
        # Regression guard — fiction never populates consent_status_warnings.
        book, plugin_root = _make_fiction_book(tmp_path)
        _make_character(book, "alex", name="Alex", role="protagonist")
        _make_chapter(
            book,
            "01-opening",
            number=1,
            title="Opening",
            pov="Alex",
            body="Alex stood at the door.",
        )

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-fiction",
            chapter_slug="01-opening",
            plugin_root=plugin_root,
        )
        assert brief["consent_status_warnings"] == []
