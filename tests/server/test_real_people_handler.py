"""Tests for the memoir real-people handler (Issue #59, Path E Phase 2).

`character-creator` branches on `book_category`. Memoir books store real
people in `people/{slug}.md` with the four-category ethics schema from
`book_categories/memoir/craft/real-people-ethics.md`. This module covers:

- `resolve_people_dir` / `resolve_person_path` path resolution
- `parse_person_file` schema parsing
- `create_person` MCP tool (validation, file layout, memoir-only gate)
- Indexer projection — `book["people"]` for memoir, `book["characters"]`
  unchanged for fiction
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.shared.paths import (
    resolve_people_dir,
    resolve_person_path,
)
from tools.state.parsers import (
    is_valid_anonymization,
    is_valid_consent_status,
    is_valid_person_category,
    parse_person_file,
)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


class TestResolvePeopleDir:
    """resolve_people_dir branches on book_category."""

    def test_fiction_always_returns_characters(self, tmp_path: Path):
        project = tmp_path / "fiction-book"
        project.mkdir()
        result = resolve_people_dir(project, "fiction")
        assert result == project / "characters"

    def test_memoir_prefers_people(self, tmp_path: Path):
        project = tmp_path / "memoir-book"
        project.mkdir()
        (project / "people").mkdir()
        result = resolve_people_dir(project, "memoir")
        assert result == project / "people"

    def test_memoir_falls_back_to_characters_when_only_legacy_exists(self, tmp_path: Path):
        # A memoir book scaffolded before #63 may have characters/ but no
        # people/ — the resolver must find the existing dir, not return a
        # phantom path.
        project = tmp_path / "legacy-memoir"
        project.mkdir()
        (project / "characters").mkdir()
        result = resolve_people_dir(project, "memoir")
        assert result == project / "characters"

    def test_memoir_returns_canonical_when_neither_exists(self, tmp_path: Path):
        # Brand-new memoir before any scaffold — return the canonical
        # `people/` so the caller can mkdir it.
        project = tmp_path / "fresh-memoir"
        project.mkdir()
        result = resolve_people_dir(project, "memoir")
        assert result == project / "people"

    def test_default_category_is_fiction(self, tmp_path: Path):
        project = tmp_path / "default-book"
        project.mkdir()
        result = resolve_people_dir(project)  # no book_category arg
        assert result == project / "characters"


class TestResolvePersonPath:
    """resolve_person_path returns the file inside the right directory."""

    def test_fiction_writes_under_characters(self, tmp_path: Path):
        config = {"paths": {"content_root": str(tmp_path)}}
        path = resolve_person_path(config, "my-novel", "alex", "fiction")
        assert path == tmp_path / "projects" / "my-novel" / "characters" / "alex.md"

    def test_memoir_writes_under_people(self, tmp_path: Path):
        config = {"paths": {"content_root": str(tmp_path)}}
        # Pre-create the project + people/ so resolve_people_dir picks people.
        (tmp_path / "projects" / "my-memoir" / "people").mkdir(parents=True)
        path = resolve_person_path(config, "my-memoir", "maria", "memoir")
        assert path == tmp_path / "projects" / "my-memoir" / "people" / "maria.md"


# ---------------------------------------------------------------------------
# Schema validators
# ---------------------------------------------------------------------------


class TestSchemaValidators:
    """The four-category ethics model is enforced by enum validators."""

    @pytest.mark.parametrize(
        "value",
        [
            "public-figure",
            "private-living-person",
            "deceased",
            "anonymized-or-composite",
        ],
    )
    def test_valid_person_categories_accepted(self, value: str):
        assert is_valid_person_category(value)

    @pytest.mark.parametrize("value", ["villain", "protagonist", "", "PUBLIC-FIGURE"])
    def test_invalid_person_categories_rejected(self, value: str):
        assert not is_valid_person_category(value)

    @pytest.mark.parametrize(
        "value",
        [
            "confirmed-consent",
            "pending",
            "not-required",
            "refused",
            "not-asking",
        ],
    )
    def test_valid_consent_statuses_accepted(self, value: str):
        assert is_valid_consent_status(value)

    @pytest.mark.parametrize("value", ["maybe", "yes", "approved", ""])
    def test_invalid_consent_statuses_rejected(self, value: str):
        assert not is_valid_consent_status(value)

    @pytest.mark.parametrize("value", ["none", "partial", "pseudonym", "composite"])
    def test_valid_anonymization_accepted(self, value: str):
        assert is_valid_anonymization(value)

    @pytest.mark.parametrize("value", ["full", "yes", "anonymous", ""])
    def test_invalid_anonymization_rejected(self, value: str):
        assert not is_valid_anonymization(value)


# ---------------------------------------------------------------------------
# parse_person_file
# ---------------------------------------------------------------------------


class TestParsePersonFile:
    """parse_person_file extracts the memoir schema from a markdown file."""

    def test_minimal_person_file(self, tmp_path: Path):
        path = tmp_path / "maria.md"
        path.write_text(
            "---\n"
            'name: "Maria"\n'
            'relationship: "sister"\n'
            'person_category: "private-living-person"\n'
            'consent_status: "pending"\n'
            'anonymization: "none"\n'
            "---\n# Maria\n",
            encoding="utf-8",
        )

        result = parse_person_file(path)
        assert result["slug"] == "maria"
        assert result["name"] == "Maria"
        assert result["relationship"] == "sister"
        assert result["person_category"] == "private-living-person"
        assert result["consent_status"] == "pending"
        assert result["anonymization"] == "none"

    def test_pseudonymized_person_carries_real_name(self, tmp_path: Path):
        path = tmp_path / "the-doctor.md"
        path.write_text(
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

        result = parse_person_file(path)
        assert result["anonymization"] == "pseudonym"
        # real_name stays available for the memoirist's records
        assert result["real_name"] == "Dr. Henrik Lassen"

    def test_unknown_values_pass_through_for_ethics_checker(self, tmp_path: Path):
        # The parser must not silently coerce — memoir-ethics-checker (#65)
        # depends on seeing exactly what's on disk so it can flag invalid
        # values for the user.
        path = tmp_path / "bad.md"
        path.write_text(
            '---\nname: "Bad"\nrelationship: "?"\nperson_category: "neighbor"\n---\n# Bad\n',
            encoding="utf-8",
        )
        result = parse_person_file(path)
        assert result["person_category"] == "neighbor"  # unchanged


# ---------------------------------------------------------------------------
# create_person MCP tool — validation + file layout
# ---------------------------------------------------------------------------


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    root.mkdir()
    return root


@pytest.fixture
def mock_config(content_root: Path):
    fake_config = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(content_root / "authors"),
        },
        "defaults": {
            "language": "en",
            "book_type": "novel",
            "book_category": "fiction",
        },
    }

    import routers._app as server_mod
    from tools.state import indexer as indexer_mod  # noqa: WPS433

    with (
        patch.object(server_mod, "load_config", return_value=fake_config),
        patch.object(server_mod, "get_content_root", return_value=content_root),
        patch.object(indexer_mod, "load_config", return_value=fake_config),
    ):
        server_mod._cache.invalidate()
        yield fake_config


@pytest.fixture
def server_module(mock_config):  # noqa: F811
    import server as server_mod

    return server_mod


class TestCreatePersonValidation:
    """create_person enforces required fields and enum validity."""

    def test_relationship_required(self, server_module, content_root: Path):
        # Set up a memoir book so we get past the book-existence check.
        json.loads(server_module.create_book_structure(title="Test Memoir", book_category="memoir"))

        result = json.loads(
            server_module.create_person(
                book_slug="test-memoir",
                name="Anonymous",
                relationship="",  # empty
                person_category="private-living-person",
            )
        )
        assert "error" in result
        assert "relationship" in result["error"].lower()

    def test_invalid_person_category_rejected(self, server_module, content_root: Path):
        json.loads(server_module.create_book_structure(title="Memoir Two", book_category="memoir"))

        result = json.loads(
            server_module.create_person(
                book_slug="memoir-two",
                name="Maria",
                relationship="sister",
                person_category="protagonist",  # fiction concept, invalid here
            )
        )
        assert "error" in result
        assert "person_category" in result["error"]

    def test_invalid_consent_status_rejected(self, server_module, content_root: Path):
        json.loads(server_module.create_book_structure(title="Memoir Three", book_category="memoir"))

        result = json.loads(
            server_module.create_person(
                book_slug="memoir-three",
                name="Maria",
                relationship="sister",
                person_category="private-living-person",
                consent_status="approved",  # not in the allowed set
            )
        )
        assert "error" in result
        assert "consent_status" in result["error"]

    def test_invalid_anonymization_rejected(self, server_module, content_root: Path):
        json.loads(server_module.create_book_structure(title="Memoir Four", book_category="memoir"))

        result = json.loads(
            server_module.create_person(
                book_slug="memoir-four",
                name="Maria",
                relationship="sister",
                person_category="private-living-person",
                anonymization="full",  # not in the allowed set
            )
        )
        assert "error" in result
        assert "anonymization" in result["error"]


class TestCreatePersonMemoirGate:
    """create_person rejects fiction books — schema mismatch."""

    def test_rejects_fiction_book(self, server_module, content_root: Path):
        json.loads(server_module.create_book_structure(title="Fiction Book", book_category="fiction"))
        server_module._cache.invalidate()

        result = json.loads(
            server_module.create_person(
                book_slug="fiction-book",
                name="Maria",
                relationship="sister",
                person_category="private-living-person",
            )
        )
        assert "error" in result
        assert "memoir" in result["error"].lower()

    def test_rejects_unknown_book(self, server_module):
        result = json.loads(
            server_module.create_person(
                book_slug="does-not-exist",
                name="Maria",
                relationship="sister",
                person_category="private-living-person",
            )
        )
        assert "error" in result
        assert "not found" in result["error"].lower()


class TestCreatePersonFileLayout:
    """Successful create_person writes to people/{slug}.md with the schema."""

    def test_writes_to_people_dir_with_frontmatter(self, server_module, content_root: Path):
        json.loads(server_module.create_book_structure(title="Year of Glass", book_category="memoir"))

        result = json.loads(
            server_module.create_person(
                book_slug="year-of-glass",
                name="Maria",
                relationship="sister",
                person_category="private-living-person",
                consent_status="pending",
                anonymization="none",
                description="The sister who stayed.",
            )
        )
        assert result.get("success") is True
        assert result["slug"] == "maria"

        person_file = content_root / "projects" / "year-of-glass" / "people" / "maria.md"
        assert person_file.exists()
        # No phantom characters/maria.md.
        assert not (content_root / "projects" / "year-of-glass" / "characters" / "maria.md").exists()

        text = person_file.read_text(encoding="utf-8")
        assert 'relationship: "sister"' in text
        assert 'person_category: "private-living-person"' in text
        assert 'consent_status: "pending"' in text
        assert 'anonymization: "none"' in text

    def test_pseudonymized_person_persists_real_name(self, server_module, content_root: Path):
        json.loads(server_module.create_book_structure(title="The Diagnosis", book_category="memoir"))

        json.loads(
            server_module.create_person(
                book_slug="the-diagnosis",
                name="The doctor",
                relationship="diagnosing physician",
                person_category="anonymized-or-composite",
                consent_status="not-asking",
                anonymization="pseudonym",
                real_name="Dr. Henrik Lassen",
            )
        )

        person_file = content_root / "projects" / "the-diagnosis" / "people" / "the-doctor.md"
        assert person_file.exists()
        text = person_file.read_text(encoding="utf-8")
        assert 'real_name: "Dr. Henrik Lassen"' in text

    def test_duplicate_person_rejected(self, server_module, content_root: Path):
        json.loads(server_module.create_book_structure(title="Duplicate Memoir", book_category="memoir"))

        first = json.loads(
            server_module.create_person(
                book_slug="duplicate-memoir",
                name="Maria",
                relationship="sister",
                person_category="private-living-person",
            )
        )
        assert first.get("success") is True

        second = json.loads(
            server_module.create_person(
                book_slug="duplicate-memoir",
                name="Maria",
                relationship="sister",
                person_category="private-living-person",
            )
        )
        assert "error" in second
        assert "already exists" in second["error"].lower()


# ---------------------------------------------------------------------------
# Indexer projection
# ---------------------------------------------------------------------------


class TestIndexerScansPeopleForMemoir:
    """The indexer populates book['people'] for memoir, characters for fiction."""

    def test_memoir_book_exposes_people_count(self, server_module, content_root: Path):
        json.loads(server_module.create_book_structure(title="Indexer Memoir", book_category="memoir"))
        json.loads(
            server_module.create_person(
                book_slug="indexer-memoir",
                name="Maria",
                relationship="sister",
                person_category="private-living-person",
            )
        )
        json.loads(
            server_module.create_person(
                book_slug="indexer-memoir",
                name="Father",
                relationship="father",
                person_category="deceased",
                consent_status="not-required",
            )
        )

        server_module._cache.invalidate()
        result = json.loads(server_module.get_book_full("indexer-memoir"))

        assert result["book_category"] == "memoir"
        assert result["people_count"] == 2
        assert "maria" in result["people"]
        assert "father" in result["people"]
        # characters/ stays empty for memoir.
        assert result["character_count"] == 0

    def test_fiction_book_does_not_populate_people(self, server_module, content_root: Path):
        json.loads(server_module.create_book_structure(title="Indexer Fiction", book_category="fiction"))
        json.loads(
            server_module.create_character(
                book_slug="indexer-fiction",
                name="Alex",
                role="protagonist",
            )
        )

        server_module._cache.invalidate()
        result = json.loads(server_module.get_book_full("indexer-fiction"))

        assert result["book_category"] == "fiction"
        assert result["character_count"] == 1
        assert "alex" in result["characters"]
        # Fiction books carry an empty people projection — never populated.
        assert result["people_count"] == 0
        assert result["people"] == {}
