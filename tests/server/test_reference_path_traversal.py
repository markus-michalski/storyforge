"""Tests for path-traversal guards in reference.py MCP tools (Issue #321).

get_genre() and get_craft_reference() must reject names that escape the
plugin's genres/ and reference/ directories via path traversal.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from routers.reference import get_craft_reference, get_genre


class TestGetGenrePathTraversal:
    """Issue #321 — get_genre() must reject traversal names."""

    def _patch_genres_dir(self, path: Path):
        return patch("routers.reference._app.get_genres_dir", return_value=path)

    def test_rejects_dotdot_in_name(self, tmp_path: Path) -> None:
        genres_dir = tmp_path / "genres"
        genres_dir.mkdir()

        with self._patch_genres_dir(genres_dir):
            result = json.loads(get_genre("../../etc/passwd"))

        assert "error" in result
        assert "Invalid genre name" in result["error"]

    def test_rejects_slash_in_name(self, tmp_path: Path) -> None:
        genres_dir = tmp_path / "genres"
        genres_dir.mkdir()

        with self._patch_genres_dir(genres_dir):
            result = json.loads(get_genre("horror/../../secret"))

        assert "error" in result
        assert "Invalid genre name" in result["error"]

    def test_rejects_backslash_in_name(self, tmp_path: Path) -> None:
        genres_dir = tmp_path / "genres"
        genres_dir.mkdir()

        with self._patch_genres_dir(genres_dir):
            result = json.loads(get_genre("horror\\..\\secret"))

        assert "error" in result
        assert "Invalid genre name" in result["error"]

    def test_rejects_null_byte_in_name(self, tmp_path: Path) -> None:
        genres_dir = tmp_path / "genres"
        genres_dir.mkdir()

        with self._patch_genres_dir(genres_dir):
            result = json.loads(get_genre("horror\x00../../secret"))

        assert "error" in result
        assert "Invalid genre name" in result["error"]

    def test_returns_not_found_for_unknown_genre(self, tmp_path: Path) -> None:
        genres_dir = tmp_path / "genres"
        genres_dir.mkdir()

        with self._patch_genres_dir(genres_dir):
            result = json.loads(get_genre("nonexistent-genre"))

        assert "error" in result
        assert "not found" in result["error"]

    def test_returns_content_for_valid_genre(self, tmp_path: Path) -> None:
        genres_dir = tmp_path / "genres"
        genre_dir = genres_dir / "horror"
        genre_dir.mkdir(parents=True)
        (genre_dir / "README.md").write_text("# Horror Genre", encoding="utf-8")

        with self._patch_genres_dir(genres_dir):
            result = get_genre("horror")

        assert "Horror Genre" in result


class TestGetCraftReferencePathTraversal:
    """Issue #321 — get_craft_reference() must reject traversal names."""

    def _patch_reference_dir(self, path: Path):
        return patch("routers.reference._app.get_reference_dir", return_value=path)

    def test_rejects_dotdot_in_name(self, tmp_path: Path) -> None:
        ref_dir = tmp_path / "reference"
        (ref_dir / "craft").mkdir(parents=True)

        with self._patch_reference_dir(ref_dir):
            result = json.loads(get_craft_reference("../../.storyforge/config"))

        assert "error" in result
        assert "Invalid reference name" in result["error"]

    def test_rejects_slash_in_name(self, tmp_path: Path) -> None:
        ref_dir = tmp_path / "reference"
        (ref_dir / "craft").mkdir(parents=True)

        with self._patch_reference_dir(ref_dir):
            result = json.loads(get_craft_reference("craft/../../secret"))

        assert "error" in result
        assert "Invalid reference name" in result["error"]

    def test_rejects_backslash_in_name(self, tmp_path: Path) -> None:
        ref_dir = tmp_path / "reference"
        (ref_dir / "craft").mkdir(parents=True)

        with self._patch_reference_dir(ref_dir):
            result = json.loads(get_craft_reference("craft\\..\\..\\secret"))

        assert "error" in result
        assert "Invalid reference name" in result["error"]

    def test_rejects_null_byte_in_name(self, tmp_path: Path) -> None:
        ref_dir = tmp_path / "reference"
        (ref_dir / "craft").mkdir(parents=True)

        with self._patch_reference_dir(ref_dir):
            result = json.loads(get_craft_reference("story\x00../../etc/passwd"))

        assert "error" in result
        assert "Invalid reference name" in result["error"]

    def test_returns_not_found_for_unknown_reference(self, tmp_path: Path) -> None:
        ref_dir = tmp_path / "reference"
        (ref_dir / "craft").mkdir(parents=True)
        (ref_dir / "genre").mkdir(parents=True)

        with self._patch_reference_dir(ref_dir):
            result = json.loads(get_craft_reference("nonexistent-doc"))

        assert "error" in result
        assert "not found" in result["error"]

    def test_returns_craft_doc_for_valid_name(self, tmp_path: Path) -> None:
        ref_dir = tmp_path / "reference"
        craft_dir = ref_dir / "craft"
        craft_dir.mkdir(parents=True)
        (craft_dir / "story-structure.md").write_text("# Story Structure", encoding="utf-8")

        with self._patch_reference_dir(ref_dir):
            result = get_craft_reference("story-structure")

        assert "Story Structure" in result

    def test_falls_back_to_genre_subdir(self, tmp_path: Path) -> None:
        ref_dir = tmp_path / "reference"
        (ref_dir / "craft").mkdir(parents=True)
        genre_dir = ref_dir / "genre"
        genre_dir.mkdir(parents=True)
        (genre_dir / "horror-craft.md").write_text("# Horror Craft", encoding="utf-8")

        with self._patch_reference_dir(ref_dir):
            result = get_craft_reference("horror-craft")

        assert "Horror Craft" in result
