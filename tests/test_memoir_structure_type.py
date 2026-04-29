"""Tests for the memoir structure type selector (Issue #58, Path E Phase 2).

`plot-architect` (memoir mode) lets the user pick one of four narrative
structures from `book_categories/memoir/craft/memoir-structure-types.md`:
chronological / thematic / braided / vignette. The choice persists to
`plot/structure.md` frontmatter via the `set_memoir_structure_type` MCP
tool so downstream skills (`chapter-writer` memoir mode #57,
`rolling-planner`) can read it without re-asking the user.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.state.parsers import (
    is_valid_memoir_structure_type,
    parse_frontmatter,
)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class TestValidateMemoirStructureType:
    """Only the four documented structure types are accepted."""

    @pytest.mark.parametrize(
        "value", ["chronological", "thematic", "braided", "vignette"]
    )
    def test_valid_types_accepted(self, value: str):
        assert is_valid_memoir_structure_type(value)

    @pytest.mark.parametrize(
        "value",
        [
            "linear",  # adjacent term that is not the canonical one
            "three-act",  # fiction structure, wrong category
            "snowflake",  # fiction method, wrong category
            "CHRONOLOGICAL",  # case-sensitive
            "",
            "hybrid",  # explicitly not allowed — earn hybrids in prose, not metadata
        ],
    )
    def test_invalid_types_rejected(self, value: str):
        assert not is_valid_memoir_structure_type(value)


# ---------------------------------------------------------------------------
# set_memoir_structure_type MCP tool
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

    with patch.object(server_mod, "load_config", return_value=fake_config), \
         patch.object(server_mod, "get_content_root", return_value=content_root), \
         patch.object(indexer_mod, "load_config", return_value=fake_config):
        server_mod._cache.invalidate()
        yield fake_config


@pytest.fixture
def server_module(mock_config):  # noqa: F811
    import server as server_mod
    return server_mod


class TestSetMemoirStructureTypeValidation:
    """Enum validation + memoir-only gate."""

    def test_invalid_structure_type_rejected(
        self, server_module, content_root: Path
    ):
        json.loads(
            server_module.create_book_structure(
                title="Memoir A", book_category="memoir"
            )
        )

        result = json.loads(
            server_module.set_memoir_structure_type(
                book_slug="memoir-a", structure_type="five-act"
            )
        )
        assert "error" in result
        assert "structure_type" in result["error"]
        # Valid options surfaced for the user.
        for valid in ["chronological", "thematic", "braided", "vignette"]:
            assert valid in result["error"]

    def test_rejects_fiction_book(self, server_module, content_root: Path):
        json.loads(
            server_module.create_book_structure(
                title="Fiction Plot", book_category="fiction"
            )
        )
        server_module._cache.invalidate()

        result = json.loads(
            server_module.set_memoir_structure_type(
                book_slug="fiction-plot", structure_type="chronological"
            )
        )
        assert "error" in result
        assert "memoir" in result["error"].lower()

    def test_rejects_unknown_book(self, server_module):
        result = json.loads(
            server_module.set_memoir_structure_type(
                book_slug="does-not-exist", structure_type="chronological"
            )
        )
        assert "error" in result
        assert "not found" in result["error"].lower()


class TestSetMemoirStructureTypePersistence:
    """Successful calls write the choice to plot/structure.md frontmatter."""

    def test_writes_structure_type_to_existing_scaffold(
        self, server_module, content_root: Path
    ):
        # The #63 scaffold creates plot/structure.md without frontmatter.
        # set_memoir_structure_type must add frontmatter while preserving
        # the scaffold body.
        json.loads(
            server_module.create_book_structure(
                title="Year of Glass", book_category="memoir"
            )
        )

        structure_path = (
            content_root / "projects" / "year-of-glass" / "plot" / "structure.md"
        )
        scaffold_text = structure_path.read_text(encoding="utf-8")
        assert "Memoir Structure" in scaffold_text  # #63 scaffold marker

        result = json.loads(
            server_module.set_memoir_structure_type(
                book_slug="year-of-glass", structure_type="chronological"
            )
        )
        assert result.get("success") is True
        assert result["structure_type"] == "chronological"

        new_text = structure_path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(new_text)
        assert meta["structure_type"] == "chronological"
        # Original body content is preserved.
        assert "Memoir Structure" in body

    def test_overwrites_previous_choice(
        self, server_module, content_root: Path
    ):
        # A user may revise the choice mid-conceptualization.
        json.loads(
            server_module.create_book_structure(
                title="Revision Memoir", book_category="memoir"
            )
        )

        json.loads(
            server_module.set_memoir_structure_type(
                book_slug="revision-memoir", structure_type="chronological"
            )
        )
        json.loads(
            server_module.set_memoir_structure_type(
                book_slug="revision-memoir", structure_type="braided"
            )
        )

        structure_path = (
            content_root / "projects" / "revision-memoir" / "plot" / "structure.md"
        )
        meta, _ = parse_frontmatter(structure_path.read_text(encoding="utf-8"))
        assert meta["structure_type"] == "braided"

    def test_creates_file_when_legacy_memoir_lacks_structure_md(
        self, server_module, content_root: Path
    ):
        # Memoir books scaffolded before #63 do not have plot/structure.md.
        # The tool must create it rather than failing.
        json.loads(
            server_module.create_book_structure(
                title="Legacy Memoir", book_category="memoir"
            )
        )

        # Simulate a legacy memoir by deleting the scaffolded structure.md.
        structure_path = (
            content_root / "projects" / "legacy-memoir" / "plot" / "structure.md"
        )
        structure_path.unlink()
        assert not structure_path.exists()

        result = json.loads(
            server_module.set_memoir_structure_type(
                book_slug="legacy-memoir", structure_type="thematic"
            )
        )
        assert result.get("success") is True
        assert structure_path.exists()
        meta, _ = parse_frontmatter(structure_path.read_text(encoding="utf-8"))
        assert meta["structure_type"] == "thematic"

    @pytest.mark.parametrize(
        "structure_type",
        ["chronological", "thematic", "braided", "vignette"],
    )
    def test_all_four_types_persist(
        self, server_module, content_root: Path, structure_type: str
    ):
        # Each of the four valid types persists identically.
        title = f"Memoir {structure_type}"
        json.loads(
            server_module.create_book_structure(
                title=title, book_category="memoir"
            )
        )

        slug = title.lower().replace(" ", "-")
        result = json.loads(
            server_module.set_memoir_structure_type(
                book_slug=slug, structure_type=structure_type
            )
        )
        assert result.get("success") is True
        assert result["structure_type"] == structure_type
