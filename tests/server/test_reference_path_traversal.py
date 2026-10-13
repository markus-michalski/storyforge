"""Tests for path-traversal guards in reference.py MCP tools (Issue #321).

get_genre() and get_craft_reference() must reject names that escape the
plugin's genres/ and reference/ directories via path traversal.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from routers.reference import get_craft_reference, get_genre, list_genres


class TestGetGenrePathTraversal:
    """Issue #321 — get_genre() must reject traversal names."""

    def _patch_genres_dir(self, path: Path):
        """Point both the builtin and user genre dirs at the same empty test
        dir — equivalent to "no genres exist anywhere" for these guard tests."""
        return patch.multiple(
            "routers.reference._app",
            get_builtin_genres_dir=lambda: path,
            get_user_genres_dir=lambda: path,
        )

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


class TestUserGenresSurvivePluginUpdate:
    """Issue #643: custom genres created by genre-creator must live outside
    CLAUDE_PLUGIN_ROOT (replaced wholesale on every plugin update) and must be
    visible to list_genres()/get_genre() alongside the plugin's built-ins,
    with a same-named user genre taking precedence."""

    def _patch_dirs(self, builtin_dir: Path, user_dir: Path):
        return patch.multiple(
            "routers.reference._app",
            get_builtin_genres_dir=lambda: builtin_dir,
            get_user_genres_dir=lambda: user_dir,
        )

    def test_list_genres_includes_user_only_genre(self, tmp_path: Path) -> None:
        builtin_dir = tmp_path / "plugin-genres"
        user_dir = tmp_path / "user-genres"
        (builtin_dir / "horror").mkdir(parents=True)
        (builtin_dir / "horror" / "README.md").write_text("# Horror", encoding="utf-8")
        (user_dir / "cozy-mystery").mkdir(parents=True)
        (user_dir / "cozy-mystery" / "README.md").write_text("# Cozy Mystery", encoding="utf-8")

        with self._patch_dirs(builtin_dir, user_dir):
            result = json.loads(list_genres())

        assert result["genres"] == ["cozy-mystery", "horror"]

    def test_user_genre_survives_when_builtin_dir_is_absent(self, tmp_path: Path) -> None:
        """Simulates a fresh plugin update: CLAUDE_PLUGIN_ROOT/genres doesn't
        even need to contain the custom genre for it to keep working."""
        builtin_dir = tmp_path / "plugin-genres"  # does not exist
        user_dir = tmp_path / "user-genres"
        (user_dir / "cozy-mystery").mkdir(parents=True)
        (user_dir / "cozy-mystery" / "README.md").write_text("# Cozy Mystery", encoding="utf-8")

        with self._patch_dirs(builtin_dir, user_dir):
            result = get_genre("cozy-mystery")

        assert "Cozy Mystery" in result

    def test_user_genre_takes_precedence_over_same_named_builtin(self, tmp_path: Path) -> None:
        builtin_dir = tmp_path / "plugin-genres"
        user_dir = tmp_path / "user-genres"
        (builtin_dir / "horror").mkdir(parents=True)
        (builtin_dir / "horror" / "README.md").write_text("# Builtin Horror", encoding="utf-8")
        (user_dir / "horror").mkdir(parents=True)
        (user_dir / "horror" / "README.md").write_text("# User Horror Override", encoding="utf-8")

        with self._patch_dirs(builtin_dir, user_dir):
            result = get_genre("horror")

        assert "User Horror Override" in result


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
