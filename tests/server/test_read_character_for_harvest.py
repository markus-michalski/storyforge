"""Tests for the ``read_character_for_harvest`` MCP tool (Issue #200, D-1 of #195).

The harvest skill reads a book-level character file's end-of-book state and
proposes a ``B{N} Ende`` summary for the matching series-tracker. This tool
projects exactly the fields the skill needs in one call:

- snapshot fields written by ``update_character_snapshot`` (POV inventory,
  clothing, injuries, altered states, environmental limiters, as_of_chapter)
- relationships section text (``## Relationships`` body)
- identity fields (name, role, description)

Memoir books read from ``people/`` instead of ``characters/`` and the
relationships heading may be ``## Relationship`` (singular) on legacy files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.series import read_character_for_harvest


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    root.mkdir()
    return root


@pytest.fixture
def mock_config(content_root: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    cfg = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(content_root / "authors"),
        },
        "defaults": {"language": "en", "book_type": "novel"},
    }
    monkeypatch.setattr(_app, "load_config", lambda: cfg)
    _app._cache.invalidate()
    return cfg


def _make_book_char(
    content_root: Path,
    book: str,
    slug: str,
    *,
    name: str = "Kael",
    role: str = "deuteragonist",
    description: str = "Vampire prince.",
    snapshot: dict | None = None,
    body_extra: str = "",
) -> Path:
    char_dir = content_root / "projects" / book / "characters"
    char_dir.mkdir(parents=True, exist_ok=True)
    char_file = char_dir / f"{slug}.md"
    snap_lines = ""
    if snapshot is not None:
        for k, v in snapshot.items():
            if isinstance(v, list):
                snap_lines += f"{k}: {v}\n"
            else:
                snap_lines += f"{k}: {v!r}\n" if isinstance(v, str) else f"{k}: {v}\n"
    char_file.write_text(
        f"---\nname: {name}\nrole: {role}\ndescription: {description}\n{snap_lines}---\n\n# {name}\n\n{body_extra}",
        encoding="utf-8",
    )
    return char_file


def _make_book_person(
    content_root: Path,
    book: str,
    slug: str,
    body_extra: str = "",
) -> Path:
    person_dir = content_root / "projects" / book / "people"
    person_dir.mkdir(parents=True, exist_ok=True)
    person_file = person_dir / f"{slug}.md"
    person_file.write_text(
        f"---\nname: {slug}\nperson_category: family\nconsent_status: confirmed\n---\n\n# {slug}\n\n{body_extra}",
        encoding="utf-8",
    )
    return person_file


class TestReadCharacterForHarvestFiction:
    def test_returns_snapshot_and_identity(self, mock_config, content_root: Path):
        _make_book_char(
            content_root,
            "blood-and-binary-firelight",
            "kael",
            name='Kaelen "Kael"',
            role="deuteragonist",
            snapshot={
                "current_inventory": ["silver knife", "phone"],
                "current_clothing": ["leather coat"],
                "current_injuries": [],
                "altered_states": [],
                "environmental_limiters": [],
                "as_of_chapter": "30-final",
            },
            body_extra=("## Relationships\n\n- **Theo:** Lover, partner.\n- **Caelan:** Father.\n"),
        )

        result = json.loads(read_character_for_harvest("blood-and-binary-firelight", "kael"))
        assert result.get("error") is None
        assert result["name"] == 'Kaelen "Kael"'
        assert result["role"] == "deuteragonist"
        assert result["description"] == "Vampire prince."
        assert result["snapshot"]["current_inventory"] == ["silver knife", "phone"]
        assert result["snapshot"]["current_clothing"] == ["leather coat"]
        assert result["snapshot"]["as_of_chapter"] == "30-final"

    def test_returns_relationships_text(self, mock_config, content_root: Path):
        _make_book_char(
            content_root,
            "my-book",
            "kael",
            body_extra=(
                "## Relationships\n\n- **Theo:** Lover, partner.\n- **Caelan:** Father.\n\n## Voice\n\nIronic.\n"
            ),
        )
        result = json.loads(read_character_for_harvest("my-book", "kael"))
        rel = result["relationships_text"]
        assert "**Theo:**" in rel
        assert "**Caelan:**" in rel
        # Voice section is NOT included.
        assert "Ironic" not in rel

    def test_missing_snapshot_fields_default_to_empty(self, mock_config, content_root: Path):
        # Character file with no snapshot frontmatter at all.
        _make_book_char(content_root, "my-book", "kael")
        result = json.loads(read_character_for_harvest("my-book", "kael"))
        assert result["snapshot"]["current_inventory"] == []
        assert result["snapshot"]["current_clothing"] == []
        assert result["snapshot"]["as_of_chapter"] == ""

    def test_missing_relationships_section_returns_empty_string(self, mock_config, content_root: Path):
        _make_book_char(content_root, "my-book", "kael", body_extra="No rel section.")
        result = json.loads(read_character_for_harvest("my-book", "kael"))
        assert result["relationships_text"] == ""


class TestReadCharacterForHarvestMemoir:
    def test_reads_from_people_dir(self, mock_config, content_root: Path):
        _make_book_person(
            content_root,
            "my-memoir",
            "mom",
            body_extra=("## Relationships\n\n- **Author:** Mother-daughter dynamic.\n"),
        )
        result = json.loads(read_character_for_harvest("my-memoir", "mom", book_category="memoir"))
        assert result.get("error") is None
        assert "**Author:**" in result["relationships_text"]


class TestReadCharacterForHarvestErrors:
    def test_book_not_found(self, mock_config, content_root: Path):
        result = json.loads(read_character_for_harvest("ghost-book", "kael"))
        assert "not found" in result["error"].lower()

    def test_character_not_found(self, mock_config, content_root: Path):
        # Make a book but no character.
        (content_root / "projects" / "my-book" / "characters").mkdir(parents=True)
        result = json.loads(read_character_for_harvest("my-book", "ghost"))
        assert "not found" in result["error"].lower()
