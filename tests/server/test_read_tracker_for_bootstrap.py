"""Tests for ``read_tracker_for_bootstrap`` MCP tool (Issue #203, D-2 of #195).

The bootstrap skill calls this once per recurring tracker to get the
data it needs for snapshot synthesis: the previous book's Ende narrative
(what D-1 wrote), the new book's planned narrative, the prev book
character file's existing snapshot for comparison, and identity fields.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.series import read_tracker_for_bootstrap


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


def _make_tracker(
    content_root: Path,
    series: str,
    slug: str,
    *,
    book_slug: str | None = None,
    role: str = "supporting",
    recurs_in: list[str] | None = None,
    body: str = "",
) -> Path:
    chars_dir = content_root / "series" / series / "characters"
    chars_dir.mkdir(parents=True, exist_ok=True)
    book_slug_line = f"book_slug: {book_slug}\n" if book_slug else ""
    fm = (
        "---\n"
        f"name: {slug.title()}\n"
        f"slug: {slug}\n"
        f"{book_slug_line}"
        f"role: {role}\n"
        "status: Profile\n"
        f"recurs_in: {recurs_in or ['B1', 'B2']}\n"
        "tracker_type: thin\n"
        "---\n\n"
    )
    path = chars_dir / f"{slug}.md"
    path.write_text(fm + body, encoding="utf-8")
    return path


def _make_book_char(
    content_root: Path,
    book: str,
    slug: str,
    *,
    snapshot: dict | None = None,
    body: str = "Profile",
    layout: str = "characters",
) -> Path:
    char_dir = content_root / "projects" / book / layout
    char_dir.mkdir(parents=True, exist_ok=True)
    snap_lines = ""
    if snapshot:
        for k, v in snapshot.items():
            snap_lines += f"{k}: {v}\n" if isinstance(v, list) else f"{k}: {v!r}\n"
    char_file = char_dir / f"{slug}.md"
    char_file.write_text(
        f"---\nname: {slug}\nrole: protagonist\n{snap_lines}---\n\n{body}\n",
        encoding="utf-8",
    )
    return char_file


class TestReadTrackerForBootstrap:
    def test_returns_prev_ende_and_new_geplant(self, mock_config, content_root: Path):
        _make_tracker(
            content_root,
            "blood-and-binary",
            "kael",
            recurs_in=["B1", "B2", "B3"],
            body=(
                "## Evolution per Band\n\n"
                "### B1 Firelight\n"
                "- **Start:** Cabin-Einsiedler.\n"
                "- **Ende:** Mit Theo zusammen, Sera tot, zurueck am Hof.\n\n"
                "### B2 Moonrise (geplant)\n"
                "- Trauernder Bruder.\n"
                "- Macht-Asymmetrie kippt.\n"
            ),
        )

        result = json.loads(read_tracker_for_bootstrap("blood-and-binary", "kael", prev_band="B1", new_band="B2"))
        assert result.get("error") is None
        assert result["tracker_slug"] == "kael"
        assert result["book_slug"] == "kael"
        assert "Mit Theo zusammen" in result["prev_band"]["ende"]
        assert "Trauernder Bruder" in result["new_band"]["geplant"]
        # Empty slots are still present in the response — not stripped.
        assert "start" in result["prev_band"]
        assert "ende" in result["new_band"]

    def test_resolves_book_slug_via_194(self, mock_config, content_root: Path):
        _make_tracker(
            content_root,
            "blood-and-binary",
            "king-caelan",
            book_slug="caelan",
            recurs_in=["B1", "B2", "B3"],
            body=("## Evolution per Band\n\n### B1 Firelight\n- **Ende:** Sera trauert.\n"),
        )
        result = json.loads(read_tracker_for_bootstrap("blood-and-binary", "king-caelan", "B1", "B2"))
        assert result["tracker_slug"] == "king-caelan"
        assert result["book_slug"] == "caelan"

    def test_returns_prev_book_snapshot_when_provided(self, mock_config, content_root: Path):
        # When prev_book_slug is provided, also project the prev book's
        # existing snapshot frontmatter — useful for diff display.
        _make_tracker(
            content_root,
            "my-series",
            "kael",
            recurs_in=["B1", "B2"],
            body=("## Evolution per Band\n\n### B1\n- **Ende:** End state.\n"),
        )
        _make_book_char(
            content_root,
            "firelight",
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
        result = json.loads(
            read_tracker_for_bootstrap(
                "my-series",
                "kael",
                "B1",
                "B2",
                prev_book_slug="firelight",
            )
        )
        assert result["prev_book_snapshot"]["current_inventory"] == ["silver knife"]
        assert result["prev_book_snapshot"]["as_of_chapter"] == "30-final"

    def test_prev_book_snapshot_prefers_db_over_frontmatter(self, mock_config, content_root: Path):
        # Since Issue #281, update_character_snapshot() writes end-of-chapter
        # state to the per-series character_snapshots DB and never touches
        # the character file's frontmatter. Before this fix, prev_book_
        # snapshot only ever read frontmatter, so it silently missed any
        # snapshot tracked during the prev book's actual chapter-by-chapter
        # writing. The DB row must win when both exist and disagree.
        import tools.db.connection as conn_mod
        from tools.db.character_snapshots import upsert_snapshot

        _make_tracker(
            content_root,
            "my-series",
            "kael",
            recurs_in=["B1", "B2"],
            body=("## Evolution per Band\n\n### B1\n- **Ende:** End state.\n"),
        )
        _make_book_char(
            content_root,
            "firelight",
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
        conn = conn_mod.open_canon_db(conn_mod.get_db_slug_for_book(content_root / "projects" / "firelight"))
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

        result = json.loads(
            read_tracker_for_bootstrap(
                "my-series",
                "kael",
                "B1",
                "B2",
                prev_book_slug="firelight",
            )
        )
        snap = result["prev_book_snapshot"]
        assert snap["current_inventory"] == ["silver knife", "stolen signet ring"]
        assert snap["current_injuries"] == ["missing left eye"]
        assert snap["altered_states"] == ["distrustful"]
        assert snap["environmental_limiters"] == ["mountains", "no signal"]
        # The stale frontmatter value must NOT leak through.
        assert "stale frontmatter knife" not in snap["current_inventory"]

    def test_prev_book_snapshot_falls_back_to_frontmatter_when_db_empty(self, mock_config, content_root: Path):
        # No DB row for this character/book — falls back to frontmatter,
        # e.g. a character whose snapshot only ever came from a prior
        # bootstrap_character_for_new_book write, or a hand-edit.
        _make_tracker(
            content_root,
            "my-series",
            "kael",
            recurs_in=["B1", "B2"],
            body=("## Evolution per Band\n\n### B1\n- **Ende:** End state.\n"),
        )
        _make_book_char(
            content_root,
            "firelight",
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
        result = json.loads(
            read_tracker_for_bootstrap(
                "my-series",
                "kael",
                "B1",
                "B2",
                prev_book_slug="firelight",
            )
        )
        assert result["prev_book_snapshot"]["current_inventory"] == ["silver knife"]
        assert result["prev_book_snapshot"]["as_of_chapter"] == "30-final"

    def test_prev_book_snapshot_falls_back_to_frontmatter_for_unlinked_series_book(
        self, mock_config, content_root: Path
    ):
        """Issue #579: the prev book's README has series set but
        series_number=0 (never linked via add_book_to_series()) —
        get_book_num() now raises BookNotLinkedToSeriesError instead of
        silently querying book 1's DB rows. Must fall back to frontmatter,
        same as the DB-empty case above, not crash the whole tool.

        Seeds a real book_num=1 DB snapshot with a DIFFERENT inventory
        value first, so the assertion proves the guard actually prevented
        that collision (frontmatter wins) rather than merely coinciding
        with an empty DB."""
        import tools.db.connection as conn_mod
        from tools.db.character_snapshots import upsert_snapshot

        _make_tracker(
            content_root,
            "my-series",
            "kael",
            recurs_in=["B1", "B2"],
            body=("## Evolution per Band\n\n### B1\n- **Ende:** End state.\n"),
        )
        _make_book_char(
            content_root,
            "firelight",
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
        (content_root / "projects" / "firelight" / "README.md").write_text(
            '---\ntitle: "Firelight"\nseries: "my-series"\nseries_number: 0\n---\n',
            encoding="utf-8",
        )
        conn = conn_mod.open_canon_db(
            conn_mod.get_db_slug_for_book(content_root / "projects" / "firelight")
        )
        try:
            upsert_snapshot(
                conn,
                char_slug="kael",
                book_num=1,
                chapter_num=99,
                inventory=["book_num=1's knife — must not leak"],
                injuries=[],
                clothing=[],
                altered_states=[],
                environmental_limiters="",
            )
        finally:
            conn.close()

        result = json.loads(
            read_tracker_for_bootstrap(
                "my-series",
                "kael",
                "B1",
                "B2",
                prev_book_slug="firelight",
            )
        )
        assert result["prev_book_snapshot"]["current_inventory"] == ["silver knife"]
        assert result["prev_book_snapshot"]["as_of_chapter"] == "30-final"
        assert "book_num=1's knife — must not leak" not in result["prev_book_snapshot"]["current_inventory"]

    def test_prev_book_snapshot_omitted_when_no_prev_book(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "kael", recurs_in=["B1", "B2"])
        result = json.loads(read_tracker_for_bootstrap("my-series", "kael", "B1", "B2"))
        # Without prev_book_slug, the field is absent OR explicitly None.
        assert result.get("prev_book_snapshot") in (None, {})

    def test_prev_book_snapshot_handles_missing_char_file(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "tristan", recurs_in=["B2", "B3"])
        # prev_book_slug provided but no char file there (Tristan first
        # appears in B2). Tool returns None / empty — not error.
        result = json.loads(
            read_tracker_for_bootstrap(
                "my-series",
                "tristan",
                "B1",
                "B2",
                prev_book_slug="firelight",
            )
        )
        assert result.get("prev_book_snapshot") in (None, {})

    def test_includes_identity_fields(self, mock_config, content_root: Path):
        _make_tracker(
            content_root,
            "my-series",
            "kael",
            role="love-interest",
            recurs_in=["B1", "B2"],
        )
        result = json.loads(read_tracker_for_bootstrap("my-series", "kael", "B1", "B2"))
        assert result["name"] == "Kael"
        assert result["role"] == "love-interest"

    def test_invalid_band_returns_error(self, mock_config, content_root: Path):
        result = json.loads(read_tracker_for_bootstrap("my-series", "kael", "Book1", "B2"))
        assert "band" in result["error"].lower()

    def test_series_not_found(self, mock_config, content_root: Path):
        result = json.loads(read_tracker_for_bootstrap("ghost-series", "kael", "B1", "B2"))
        assert "not found" in result["error"].lower()

    def test_tracker_not_found(self, mock_config, content_root: Path):
        (content_root / "series" / "my-series" / "characters").mkdir(parents=True)
        result = json.loads(read_tracker_for_bootstrap("my-series", "ghost-char", "B1", "B2"))
        assert "not found" in result["error"].lower()

    def test_rejects_traversal_tracker_slug(self, mock_config, content_root: Path):
        """Issue #524: tracker_path = series_dir / "characters" / f"{tracker_slug}.md"
        builds the path directly from the raw MCP parameter with zero
        validation. Confirmed exploitable: a file outside the series
        characters/ dir was read (frontmatter leaked) via a traversal
        tracker_slug before this fix."""
        (content_root / "series" / "my-series" / "characters").mkdir(parents=True)
        secret = content_root / "series" / "SECRET.md"
        secret.write_text("---\nname: leaked\nrole: supporting\n---\n\nsecret body\n", encoding="utf-8")

        result = json.loads(read_tracker_for_bootstrap("my-series", "../../SECRET", "B1", "B2"))
        assert "tracker_slug" in result["error"]
        assert "leaked" not in json.dumps(result)

    def test_handles_missing_evolution_section_gracefully(self, mock_config, content_root: Path):
        # Tracker without Evolution per Band yet — empty bands, no error.
        _make_tracker(
            content_root,
            "my-series",
            "kael",
            recurs_in=["B1", "B2"],
            body="## Snapshot\n\nEssence.\n",
        )
        result = json.loads(read_tracker_for_bootstrap("my-series", "kael", "B1", "B2"))
        assert result["prev_band"]["ende"] == ""
        assert result["new_band"]["geplant"] == ""
