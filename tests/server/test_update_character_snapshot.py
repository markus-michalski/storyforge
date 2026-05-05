"""Tests for the ``update_character_snapshot`` MCP tool (Issues #157 / #160).

The tool persists end-of-chapter POV character state back to the character
file's frontmatter so the next brief picks it up from the highest-priority
``frontmatter`` source rather than falling through to timeline heuristics.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import routers._app as _app
from routers.claudemd import update_character_snapshot


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


def _make_char(content_root: Path, book: str, slug: str, extra: str = "") -> Path:
    char_dir = content_root / "projects" / book / "characters"
    char_dir.mkdir(parents=True, exist_ok=True)
    char_file = char_dir / f"{slug}.md"
    char_file.write_text(
        f"---\nname: {slug}\nrole: protagonist\n---\n\nProfile body.\n{extra}",
        encoding="utf-8",
    )
    return char_file


def _make_person(content_root: Path, book: str, slug: str) -> Path:
    person_dir = content_root / "projects" / book / "people"
    person_dir.mkdir(parents=True, exist_ok=True)
    person_file = person_dir / f"{slug}.md"
    person_file.write_text(
        f"---\nname: {slug}\nconsent_status: confirmed\n---\n\nPerson body.\n",
        encoding="utf-8",
    )
    return person_file


# ---------------------------------------------------------------------------
# Happy path — fiction
# ---------------------------------------------------------------------------


class TestUpdateCharacterSnapshotFiction:
    def test_writes_inventory_list(self, mock_config, content_root: Path):
        char_file = _make_char(content_root, "my-book", "theo")

        result = json.loads(
            update_character_snapshot(
                "my-book",
                "theo",
                json.dumps({"current_inventory": ["compass", "silver knife", "no-signal phone"]}),
            )
        )

        assert result["success"] is True
        assert "current_inventory" in result["updated_fields"]
        meta = yaml.safe_load(char_file.read_text(encoding="utf-8").split("---")[1])
        assert meta["current_inventory"] == ["compass", "silver knife", "no-signal phone"]

    def test_writes_all_snapshot_fields(self, mock_config, content_root: Path):
        char_file = _make_char(content_root, "my-book", "theo")
        snapshot = {
            "current_inventory": ["compass", "knife"],
            "current_clothing": ["tactical boots", "mission jacket"],
            "current_injuries": ["bandaged left hand"],
            "altered_states": ["running on 3 hours sleep"],
            "environmental_limiters": [],
            "as_of_chapter": "26-the-basement",
        }

        result = json.loads(update_character_snapshot("my-book", "theo", json.dumps(snapshot)))

        assert result["success"] is True
        meta = yaml.safe_load(char_file.read_text(encoding="utf-8").split("---")[1])
        assert meta["current_inventory"] == ["compass", "knife"]
        assert meta["current_clothing"] == ["tactical boots", "mission jacket"]
        assert meta["current_injuries"] == ["bandaged left hand"]
        assert meta["altered_states"] == ["running on 3 hours sleep"]
        assert meta["environmental_limiters"] == []
        assert meta["as_of_chapter"] == "26-the-basement"

    def test_preserves_existing_non_snapshot_fields(self, mock_config, content_root: Path):
        char_file = _make_char(content_root, "my-book", "theo")

        update_character_snapshot(
            "my-book", "theo", json.dumps({"current_inventory": ["compass"]})
        )

        meta = yaml.safe_load(char_file.read_text(encoding="utf-8").split("---")[1])
        assert meta["name"] == "theo"
        assert meta["role"] == "protagonist"

    def test_overwrites_stale_inventory(self, mock_config, content_root: Path):
        char_dir = content_root / "projects" / "my-book" / "characters"
        char_dir.mkdir(parents=True, exist_ok=True)
        char_file = char_dir / "theo.md"
        char_file.write_text(
            "---\ncurrent_inventory:\n- old item\n---\nBody.\n", encoding="utf-8"
        )

        update_character_snapshot(
            "my-book", "theo", json.dumps({"current_inventory": ["new item"]})
        )

        meta = yaml.safe_load(char_file.read_text(encoding="utf-8").split("---")[1])
        assert meta["current_inventory"] == ["new item"]

    def test_partial_snapshot_only_updates_given_fields(self, mock_config, content_root: Path):
        char_dir = content_root / "projects" / "my-book" / "characters"
        char_dir.mkdir(parents=True, exist_ok=True)
        char_file = char_dir / "theo.md"
        char_file.write_text(
            "---\ncurrent_inventory:\n- compass\ncurrent_clothing:\n- jacket\n---\nBody.\n",
            encoding="utf-8",
        )

        update_character_snapshot(
            "my-book", "theo", json.dumps({"current_injuries": ["bruised ribs"]})
        )

        meta = yaml.safe_load(char_file.read_text(encoding="utf-8").split("---")[1])
        assert meta["current_inventory"] == ["compass"]
        assert meta["current_clothing"] == ["jacket"]
        assert meta["current_injuries"] == ["bruised ribs"]

    def test_empty_list_is_valid(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")

        result = json.loads(
            update_character_snapshot(
                "my-book", "theo", json.dumps({"current_injuries": []})
            )
        )

        assert result["success"] is True

    def test_body_text_is_preserved(self, mock_config, content_root: Path):
        char_file = _make_char(content_root, "my-book", "theo")

        update_character_snapshot(
            "my-book", "theo", json.dumps({"current_inventory": ["compass"]})
        )

        content = char_file.read_text(encoding="utf-8")
        assert "Profile body." in content


# ---------------------------------------------------------------------------
# Happy path — memoir (people/ directory)
# ---------------------------------------------------------------------------


class TestUpdateCharacterSnapshotMemoir:
    def test_writes_to_people_dir(self, mock_config, content_root: Path):
        person_file = _make_person(content_root, "my-memoir", "jane")

        result = json.loads(
            update_character_snapshot(
                "my-memoir",
                "jane",
                json.dumps({"current_inventory": ["notebook", "pen"]}),
                book_category="memoir",
            )
        )

        assert result["success"] is True
        meta = yaml.safe_load(person_file.read_text(encoding="utf-8").split("---")[1])
        assert meta["current_inventory"] == ["notebook", "pen"]
        assert meta["consent_status"] == "confirmed"

    def test_memoir_does_not_touch_characters_dir(self, mock_config, content_root: Path):
        _make_person(content_root, "my-memoir", "jane")
        chars_dir = content_root / "projects" / "my-memoir" / "characters"

        update_character_snapshot(
            "my-memoir",
            "jane",
            json.dumps({"current_inventory": ["notebook"]}),
            book_category="memoir",
        )

        assert not chars_dir.exists()


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class TestUpdateCharacterSnapshotValidation:
    def test_rejects_invalid_json(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")
        result = json.loads(update_character_snapshot("my-book", "theo", "not json"))
        assert "error" in result
        assert "JSON" in result["error"]

    def test_rejects_json_array(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")
        result = json.loads(update_character_snapshot("my-book", "theo", '["list"]'))
        assert "error" in result

    def test_rejects_empty_object(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")
        result = json.loads(update_character_snapshot("my-book", "theo", "{}"))
        assert "error" in result

    def test_rejects_unknown_fields(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")
        result = json.loads(
            update_character_snapshot(
                "my-book", "theo", json.dumps({"unknown_field": ["x"]})
            )
        )
        assert "error" in result
        assert "unknown_field" in result["error"]

    def test_rejects_list_field_with_non_list_value(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")
        result = json.loads(
            update_character_snapshot(
                "my-book", "theo", json.dumps({"current_inventory": "compass"})
            )
        )
        assert "error" in result
        assert "list of strings" in result["error"]

    def test_rejects_list_with_non_string_items(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")
        result = json.loads(
            update_character_snapshot(
                "my-book", "theo", json.dumps({"current_inventory": [1, 2, 3]})
            )
        )
        assert "error" in result

    def test_rejects_as_of_chapter_non_string(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")
        result = json.loads(
            update_character_snapshot(
                "my-book", "theo", json.dumps({"as_of_chapter": 27})
            )
        )
        assert "error" in result

    def test_rejects_missing_book(self, mock_config, content_root: Path):
        result = json.loads(
            update_character_snapshot(
                "nonexistent-book", "theo", json.dumps({"current_inventory": ["x"]})
            )
        )
        assert "error" in result
        assert "nonexistent-book" in result["error"]

    def test_rejects_missing_character_file(self, mock_config, content_root: Path):
        book_dir = content_root / "projects" / "my-book"
        book_dir.mkdir(parents=True)
        result = json.loads(
            update_character_snapshot(
                "my-book", "nobody", json.dumps({"current_inventory": ["x"]})
            )
        )
        assert "error" in result
        assert "nobody" in result["error"]


# ---------------------------------------------------------------------------
# Security — path containment
# ---------------------------------------------------------------------------


class TestUpdateCharacterSnapshotSecurity:
    def test_rejects_traversal_via_character_slug(
        self, mock_config, content_root: Path, tmp_path: Path
    ):
        """A slug with '..' must not escape content_root."""
        from tools.shared.paths import resolve_project_path

        import pytest as _pytest
        with _pytest.raises(ValueError):
            resolve_project_path({"paths": {"content_root": str(content_root)}}, "../escape")

    def test_result_contains_sorted_updated_fields(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")
        snapshot = {
            "current_inventory": ["compass"],
            "as_of_chapter": "26-the-basement",
        }
        result = json.loads(update_character_snapshot("my-book", "theo", json.dumps(snapshot)))
        assert result["updated_fields"] == sorted(snapshot.keys())
