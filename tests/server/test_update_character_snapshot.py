"""Tests for update_character_snapshot MCP tool — Issues #157 / #160 / #281.

Phase 3 rewrite: snapshots now write to character_snapshots in SQLite
(per-series DB) instead of YAML frontmatter in characters/*.md.
Character files still exist for validation; they are not modified.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

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

    import tools.db.connection as conn_mod
    db_dir = content_root.parent / "db"
    db_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(conn_mod, "DB_DIR", db_dir)

    return cfg


def _make_char(content_root: Path, book: str, slug: str) -> Path:
    char_dir = content_root / "projects" / book / "characters"
    char_dir.mkdir(parents=True, exist_ok=True)
    char_file = char_dir / f"{slug}.md"
    char_file.write_text(
        f"---\nname: {slug}\nrole: protagonist\n---\n\nProfile body.\n",
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


def _get_snapshot(content_root: Path, book_slug: str, char_slug: str) -> dict | None:
    """Read latest snapshot for char from the book's DB."""
    db_dir = content_root.parent / "db"
    db_path = db_dir / f"{book_slug}.db"
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM character_snapshots WHERE char_slug=? ORDER BY book_num DESC, chapter_num DESC LIMIT 1",
        (char_slug,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    result = dict(row)
    for field in ("injuries", "clothing", "inventory", "altered_states"):
        raw = result.get(field)
        if isinstance(raw, str):
            try:
                result[field] = json.loads(raw)
            except json.JSONDecodeError:
                result[field] = []
    return result


# ---------------------------------------------------------------------------
# Happy path — fiction
# ---------------------------------------------------------------------------


class TestUpdateCharacterSnapshotFiction:
    def test_writes_inventory_to_db(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")

        result = json.loads(
            update_character_snapshot(
                "my-book",
                "theo",
                json.dumps({"current_inventory": ["compass", "silver knife", "no-signal phone"]}),
            )
        )

        assert result["success"] is True
        assert "current_inventory" in result["updated_fields"]
        snap = _get_snapshot(content_root, "my-book", "theo")
        assert snap is not None
        assert snap["inventory"] == ["compass", "silver knife", "no-signal phone"]

    def test_writes_all_snapshot_fields(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")
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
        snap = _get_snapshot(content_root, "my-book", "theo")
        assert snap is not None
        assert snap["inventory"] == ["compass", "knife"]
        assert snap["clothing"] == ["tactical boots", "mission jacket"]
        assert snap["injuries"] == ["bandaged left hand"]
        assert snap["altered_states"] == ["running on 3 hours sleep"]
        assert snap["chapter_num"] == 26

    def test_character_file_not_modified(self, mock_config, content_root: Path):
        char_file = _make_char(content_root, "my-book", "theo")
        original = char_file.read_text(encoding="utf-8")

        update_character_snapshot(
            "my-book", "theo", json.dumps({"current_inventory": ["compass"]})
        )

        assert char_file.read_text(encoding="utf-8") == original

    def test_overwrites_previous_snapshot_same_chapter(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")
        update_character_snapshot(
            "my-book", "theo",
            json.dumps({"current_inventory": ["old item"], "as_of_chapter": "5-scene"}),
        )
        update_character_snapshot(
            "my-book", "theo",
            json.dumps({"current_inventory": ["new item"], "as_of_chapter": "5-scene"}),
        )
        snap = _get_snapshot(content_root, "my-book", "theo")
        assert snap is not None
        assert snap["inventory"] == ["new item"]

    def test_partial_snapshot_merges_with_existing(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")
        update_character_snapshot(
            "my-book", "theo",
            json.dumps({
                "current_inventory": ["compass"],
                "current_clothing": ["jacket"],
                "as_of_chapter": "5-setup",
            }),
        )
        update_character_snapshot(
            "my-book", "theo",
            json.dumps({"current_injuries": ["bruised ribs"], "as_of_chapter": "6-fight"}),
        )
        snap = _get_snapshot(content_root, "my-book", "theo")
        assert snap is not None
        assert snap["inventory"] == ["compass"]
        assert snap["clothing"] == ["jacket"]
        assert snap["injuries"] == ["bruised ribs"]

    def test_empty_list_is_valid(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")

        result = json.loads(
            update_character_snapshot(
                "my-book", "theo", json.dumps({"current_injuries": []})
            )
        )

        assert result["success"] is True

    def test_updated_fields_in_response(self, mock_config, content_root: Path):
        _make_char(content_root, "my-book", "theo")
        snapshot = {
            "current_inventory": ["compass"],
            "as_of_chapter": "26-the-basement",
        }
        result = json.loads(update_character_snapshot("my-book", "theo", json.dumps(snapshot)))
        assert result["success"] is True
        assert result["updated_fields"] == sorted(snapshot.keys())


# ---------------------------------------------------------------------------
# Happy path — memoir (people/ directory)
# ---------------------------------------------------------------------------


class TestUpdateCharacterSnapshotMemoir:
    def test_writes_to_db_for_memoir(self, mock_config, content_root: Path):
        _make_person(content_root, "my-memoir", "jane")

        result = json.loads(
            update_character_snapshot(
                "my-memoir",
                "jane",
                json.dumps({"current_inventory": ["notebook", "pen"]}),
                book_category="memoir",
            )
        )

        assert result["success"] is True
        snap = _get_snapshot(content_root, "my-memoir", "jane")
        assert snap is not None
        assert snap["inventory"] == ["notebook", "pen"]

    def test_memoir_does_not_touch_people_file(self, mock_config, content_root: Path):
        person_file = _make_person(content_root, "my-memoir", "jane")
        original = person_file.read_text(encoding="utf-8")

        update_character_snapshot(
            "my-memoir",
            "jane",
            json.dumps({"current_inventory": ["notebook"]}),
            book_category="memoir",
        )

        assert person_file.read_text(encoding="utf-8") == original


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
