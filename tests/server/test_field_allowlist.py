"""Tests for field allowlist validation — Issue #328.

update_author() enforces a strict allowlist of known profile fields.
update_field() enforces a field-name format regex that rejects null bytes,
shell metacharacters, and path-like strings.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Fixtures (mirrors test_update_field.py setup)
# ---------------------------------------------------------------------------


import pytest


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
        "defaults": {"language": "en", "book_type": "novel"},
    }

    import routers._app as server_mod
    from tools.state import indexer as indexer_mod

    fake_state_path = content_root / "_cache" / "state.json"

    with (
        patch.object(server_mod, "load_config", return_value=fake_config),
        patch.object(server_mod, "get_content_root", return_value=content_root),
        patch.object(indexer_mod, "load_config", return_value=fake_config),
        patch.object(indexer_mod, "STATE_PATH", fake_state_path),
        patch.object(indexer_mod, "CACHE_DIR", fake_state_path.parent),
    ):
        server_mod._cache.invalidate()
        yield fake_config


@pytest.fixture
def server_module(mock_config):
    import server as server_mod
    return server_mod


@pytest.fixture
def author_dir(content_root: Path) -> Path:
    authors_root = content_root / "authors"
    author = authors_root / "test-author"
    author.mkdir(parents=True)
    profile = author / "profile.md"
    profile.write_text(
        '---\nname: "Test Author"\nslug: "test-author"\ntone: []\n---\n',
        encoding="utf-8",
    )
    return author


# ---------------------------------------------------------------------------
# update_author — allowlist enforcement (Issue #328)
# ---------------------------------------------------------------------------


class TestUpdateAuthorAllowlist:
    def test_allowed_field_accepted(self, server_module, author_dir: Path):
        result = json.loads(server_module.update_author("test-author", "tone", "dark"))
        assert result.get("success") is True

    def test_disallowed_field_rejected(self, server_module, author_dir: Path):
        result = json.loads(server_module.update_author("test-author", "status", "published"))
        assert "error" in result
        assert "status" in result["error"]

    def test_internal_slug_field_rejected(self, server_module, author_dir: Path):
        result = json.loads(server_module.update_author("test-author", "slug", "hacked"))
        assert "error" in result

    def test_arbitrary_key_rejected(self, server_module, author_dir: Path):
        result = json.loads(server_module.update_author("test-author", "is_admin", "true"))
        assert "error" in result

    def test_author_writing_mode_accepted(self, server_module, author_dir: Path):
        result = json.loads(server_module.update_author("test-author", "author_writing_mode", "discovery"))
        assert result.get("success") is True

    def test_native_language_accepted(self, server_module, author_dir: Path):
        result = json.loads(server_module.update_author("test-author", "native_language", "de"))
        assert result.get("success") is True

    def test_subject_position_memoir_accepted(self, server_module, author_dir: Path):
        result = json.loads(server_module.update_author("test-author", "subject_position", "writing-self"))
        assert result.get("success") is True

    def test_unknown_author_still_returns_error(self, server_module, content_root: Path):
        result = json.loads(server_module.update_author("no-such-author", "tone", "bright"))
        assert "error" in result


# ---------------------------------------------------------------------------
# update_author -> get_author round-trip (regression for the fix that added
# the four quantitative-target fields, e69f... / "author-check quantitative
# targets" branch). Being on the allowlist only guarantees a field can be
# *written* to profile.md frontmatter — get_author() actually reads the
# state-cache projection built by parse_author_profile(), a separate
# explicit per-field whitelist. A field can pass every test above and still
# never reach author-check if parse_author_profile() doesn't also return it.
# ---------------------------------------------------------------------------


class TestUpdateAuthorGetAuthorRoundTrip:
    def test_dialog_ratio_target_round_trips_through_get_author(self, server_module, author_dir: Path):
        write_result = json.loads(
            server_module.update_author("test-author", "dialog_ratio_target", "0.35-0.45")
        )
        assert write_result.get("success") is True

        author = json.loads(server_module.get_author("test-author"))
        assert author["dialog_ratio_target"] == "0.35-0.45"


# ---------------------------------------------------------------------------
# update_author — list-typed field coercion (found via create-author's live-MCP
# eval tier: create_author() writes primary_genres/tone/avoid as real YAML lists
# via json.dumps(list), but update_author()'s value param is a plain str — without
# coercion, updating themes/influences/tone/avoid/off_limits writes a scalar
# comma-string instead, silently diverging from every other list field's schema.
# ---------------------------------------------------------------------------


class TestUpdateAuthorListFieldCoercion:
    def test_comma_separated_string_becomes_list(self, server_module, author_dir: Path):
        result = json.loads(
            server_module.update_author("test-author", "themes", "isolation, complicity")
        )
        assert result.get("success") is True
        assert result["value"] == ["isolation", "complicity"]

        author = json.loads(server_module.get_author("test-author"))
        assert author["themes"] == ["isolation", "complicity"]

    def test_json_array_string_becomes_list(self, server_module, author_dir: Path):
        result = json.loads(
            server_module.update_author("test-author", "influences", '["Mary Karr", "Tara Westover"]')
        )
        assert result.get("success") is True
        assert result["value"] == ["Mary Karr", "Tara Westover"]

    def test_single_value_becomes_one_item_list(self, server_module, author_dir: Path):
        result = json.loads(server_module.update_author("test-author", "tone", "dark"))
        assert result.get("success") is True
        assert result["value"] == ["dark"]

    def test_empty_string_becomes_empty_list(self, server_module, author_dir: Path):
        result = json.loads(server_module.update_author("test-author", "avoid", ""))
        assert result.get("success") is True
        assert result["value"] == []

    def test_scalar_field_is_not_coerced(self, server_module, author_dir: Path):
        result = json.loads(
            server_module.update_author("test-author", "author_writing_mode", "discovery")
        )
        assert result.get("success") is True
        assert result["value"] == "discovery"


# ---------------------------------------------------------------------------
# update_field — field name format validation (Issue #328)
# ---------------------------------------------------------------------------


class TestUpdateFieldNameValidation:
    def test_valid_snake_case_field_accepted(self, server_module, content_root: Path):
        target = content_root / "README.md"
        target.write_text("---\nstatus: Draft\n---\n", encoding="utf-8")
        result = json.loads(server_module.update_field(str(target), "author_writing_mode", "discovery"))
        assert result.get("success") is True

    def test_valid_hyphenated_field_accepted(self, server_module, content_root: Path):
        target = content_root / "README.md"
        target.write_text("---\nstatus: Draft\n---\n", encoding="utf-8")
        result = json.loads(server_module.update_field(str(target), "book-category", "fiction"))
        assert result.get("success") is True

    def test_field_with_null_byte_rejected(self, server_module, content_root: Path):
        target = content_root / "README.md"
        target.write_text("---\nstatus: Draft\n---\n", encoding="utf-8")
        result = json.loads(server_module.update_field(str(target), "field\x00inject", "val"))
        assert "error" in result

    def test_field_with_newline_rejected(self, server_module, content_root: Path):
        target = content_root / "README.md"
        target.write_text("---\nstatus: Draft\n---\n", encoding="utf-8")
        result = json.loads(server_module.update_field(str(target), "field\nevil: true\n#", "val"))
        assert "error" in result

    def test_field_starting_with_digit_rejected(self, server_module, content_root: Path):
        target = content_root / "README.md"
        target.write_text("---\nstatus: Draft\n---\n", encoding="utf-8")
        result = json.loads(server_module.update_field(str(target), "1field", "val"))
        assert "error" in result

    def test_field_with_colon_rejected(self, server_module, content_root: Path):
        target = content_root / "README.md"
        target.write_text("---\nstatus: Draft\n---\n", encoding="utf-8")
        result = json.loads(server_module.update_field(str(target), "key: injected", "val"))
        assert "error" in result

    def test_empty_field_rejected(self, server_module, content_root: Path):
        target = content_root / "README.md"
        target.write_text("---\nstatus: Draft\n---\n", encoding="utf-8")
        result = json.loads(server_module.update_field(str(target), "", "val"))
        assert "error" in result

    def test_very_long_field_rejected(self, server_module, content_root: Path):
        target = content_root / "README.md"
        target.write_text("---\nstatus: Draft\n---\n", encoding="utf-8")
        result = json.loads(server_module.update_field(str(target), "a" * 65, "val"))
        assert "error" in result

    def test_status_field_accepted(self, server_module, content_root: Path):
        target = content_root / "README.md"
        target.write_text("---\nstatus: Draft\n---\n", encoding="utf-8")
        result = json.loads(server_module.update_field(str(target), "status", "Review"))
        assert result.get("success") is True
