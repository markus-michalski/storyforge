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

    # Note: tools.db.connection.DB_DIR is already redirected to a per-test
    # tmp dir by the autouse `_isolate_db_dir` fixture in tests/conftest.py
    # (Issue #407), and it resolves to the exact same path we'd pick here
    # (`content_root.parent / "db"` == `tmp_path / "db"`) — no need to
    # monkeypatch it again.

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

    def test_snapshot_prefers_db_over_stale_frontmatter(self, mock_config, content_root: Path):
        # Since Issue #281, update_character_snapshot() writes end-of-chapter
        # state to the per-series/per-book character_snapshots DB and never
        # touches the character file's frontmatter. Before this fix,
        # read_character_for_harvest only ever read frontmatter, so it
        # silently returned an empty snapshot for any character whose state
        # was actually written the normal way (at chapter close), the exact
        # same root cause read_tracker_for_bootstrap() had before its own fix
        # (see test_read_tracker_for_bootstrap.py). The DB row must win when
        # both exist and disagree.
        import tools.db.connection as conn_mod
        from tools.db.character_snapshots import upsert_snapshot

        _make_book_char(
            content_root,
            "my-book",
            "kael",
            snapshot={
                "current_inventory": ["stale frontmatter knife"],
                "current_clothing": [],
                "current_injuries": [],
                "altered_states": [],
                "environmental_limiters": [],
                "as_of_chapter": "01-stale",
            },
        )
        conn = conn_mod.open_canon_db(conn_mod.get_db_slug_for_book(content_root / "projects" / "my-book"))
        try:
            upsert_snapshot(
                conn,
                char_slug="kael",
                book_num=1,
                chapter_num=30,
                inventory=["silver knife", "stolen signet ring"],
                injuries=["missing left eye"],
                clothing=[],
                altered_states=["distrustful"],
                environmental_limiters="mountains, no signal",
            )
        finally:
            conn.close()

        result = json.loads(read_character_for_harvest("my-book", "kael"))
        snap = result["snapshot"]
        assert snap["current_inventory"] == ["silver knife", "stolen signet ring"]
        assert snap["current_injuries"] == ["missing left eye"]
        assert snap["altered_states"] == ["distrustful"]
        assert snap["environmental_limiters"] == ["mountains", "no signal"]
        # The stale frontmatter value must NOT leak through.
        assert "stale frontmatter knife" not in snap["current_inventory"]
        # as_of_chapter must reflect the DB row's chapter_num, not be blanked
        # out (the DB path used to hardcode "" here, defeating the one
        # staleness signal Step 3c shows before a permanent tracker write).
        assert snap["as_of_chapter"] == "30"
        assert result["snapshot_source"] == "db"

    def test_snapshot_prefers_frontmatter_when_strictly_newer_than_db(self, mock_config, content_root: Path):
        # A DB row exists but is from an earlier chapter than a hand-edited
        # frontmatter as_of_chapter (e.g. a final polish pass recorded after
        # the last chapter-close write). The more current source must win —
        # the DB is the default, not an unconditional override.
        import tools.db.connection as conn_mod
        from tools.db.character_snapshots import upsert_snapshot

        _make_book_char(
            content_root,
            "my-book",
            "kael",
            snapshot={
                "current_inventory": ["hand-edited final inventory"],
                "current_clothing": [],
                "current_injuries": [],
                "altered_states": [],
                "environmental_limiters": [],
                "as_of_chapter": "30-final",
            },
        )
        conn = conn_mod.open_canon_db(conn_mod.get_db_slug_for_book(content_root / "projects" / "my-book"))
        try:
            upsert_snapshot(
                conn,
                char_slug="kael",
                book_num=1,
                chapter_num=10,
                inventory=["early-chapter knife"],
                injuries=[],
                clothing=[],
                altered_states=[],
                environmental_limiters="",
            )
        finally:
            conn.close()

        result = json.loads(read_character_for_harvest("my-book", "kael"))
        snap = result["snapshot"]
        assert snap["current_inventory"] == ["hand-edited final inventory"]
        assert snap["as_of_chapter"] == "30-final"
        assert result["snapshot_source"] == "frontmatter"

    def test_snapshot_falls_back_to_frontmatter_when_db_empty(self, mock_config, content_root: Path):
        # No DB row for this character/book — falls back to frontmatter,
        # e.g. a hand-edited file or state from before Issue #281.
        _make_book_char(
            content_root,
            "my-book",
            "kael",
            snapshot={
                "current_inventory": ["silver knife"],
                "current_clothing": ["leather coat"],
                "current_injuries": [],
                "altered_states": [],
                "environmental_limiters": [],
                "as_of_chapter": "30-final",
            },
        )
        result = json.loads(read_character_for_harvest("my-book", "kael"))
        assert result["snapshot"]["current_inventory"] == ["silver knife"]
        assert result["snapshot"]["as_of_chapter"] == "30-final"
        assert result["snapshot_source"] == "frontmatter"


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
        # consent_status is projected for memoir reads so the harvest skill's
        # consent gate can read it here instead of the indexer's book.people
        # (which has no legacy-layout fallback — see the next two tests).
        assert result["consent_status"] == "confirmed"

    def test_consent_status_refused_is_returned(self, mock_config, content_root: Path):
        _make_book_person(content_root, "my-memoir", "estranged-uncle")
        person_file = content_root / "projects" / "my-memoir" / "people" / "estranged-uncle.md"
        person_file.write_text(
            person_file.read_text(encoding="utf-8").replace("consent_status: confirmed", "consent_status: refused"),
            encoding="utf-8",
        )
        result = json.loads(read_character_for_harvest("my-memoir", "estranged-uncle", book_category="memoir"))
        assert result["consent_status"] == "refused"

    def test_consent_status_found_via_legacy_characters_layout(self, mock_config, content_root: Path):
        # Pre-#59 memoir books never got a people/ directory — their cast
        # still lives under characters/. resolve_people_dir() falls back to
        # characters/ for these books; read_character_for_harvest must
        # surface consent_status from whichever file it actually resolves to.
        legacy_dir = content_root / "projects" / "legacy-memoir" / "characters"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        (legacy_dir / "grandma.md").write_text(
            "---\nname: Grandma\nperson_category: family\nconsent_status: refused\n---\n\n# Grandma\n",
            encoding="utf-8",
        )
        result = json.loads(read_character_for_harvest("legacy-memoir", "grandma", book_category="memoir"))
        assert result.get("error") is None
        assert result["consent_status"] == "refused"

    def test_consent_status_absent_from_fiction_response(self, mock_config, content_root: Path):
        # consent_status is a memoir-only concept — fiction reads must not
        # carry the key at all (not even as an empty string).
        _make_book_char(content_root, "my-book", "kael")
        result = json.loads(read_character_for_harvest("my-book", "kael"))
        assert "consent_status" not in result


class TestReadCharacterForHarvestErrors:
    def test_book_not_found(self, mock_config, content_root: Path):
        result = json.loads(read_character_for_harvest("ghost-book", "kael"))
        assert "not found" in result["error"].lower()

    def test_character_not_found(self, mock_config, content_root: Path):
        # Make a book but no character.
        (content_root / "projects" / "my-book" / "characters").mkdir(parents=True)
        result = json.loads(read_character_for_harvest("my-book", "ghost"))
        assert "not found" in result["error"].lower()
