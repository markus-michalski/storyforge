"""Tests for tools.shared.config — Issue #124."""

from __future__ import annotations

from pathlib import Path

import yaml

from tools.shared import config as cfg_module
from tools.shared.config import (
    POST_PROCESSING_TOOLS,
    _deep_merge,
    _default_config,
    get_authors_root,
    get_book_categories_dir,
    get_content_root,
    get_genres_dir,
    get_plugin_root,
    get_post_processing_tool,
    get_reference_dir,
    get_review_handle,
    get_templates_dir,
    load_config,
)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# _default_config
# ---------------------------------------------------------------------------


class TestDefaultConfig:
    def test_has_paths_key(self):
        cfg = _default_config()
        assert "paths" in cfg

    def test_has_content_root(self):
        cfg = _default_config()
        assert "content_root" in cfg["paths"]

    def test_has_defaults_section(self):
        cfg = _default_config()
        assert cfg["defaults"]["language"] == "en"
        assert cfg["defaults"]["book_type"] == "novel"
        assert cfg["defaults"]["book_category"] == "fiction"
        assert cfg["defaults"]["review_handle"] == "Author"

    def test_has_export_section(self):
        cfg = _default_config()
        assert cfg["export"]["pdf_engine"] == "xelatex"

    def test_has_post_processing_section(self):
        cfg = _default_config()
        assert cfg["post_processing"]["tool"] == "canva"


# ---------------------------------------------------------------------------
# _deep_merge
# ---------------------------------------------------------------------------


class TestDeepMerge:
    def test_flat_override(self):
        base = {"a": 1, "b": 2}
        _deep_merge(base, {"b": 99, "c": 3})
        assert base == {"a": 1, "b": 99, "c": 3}

    def test_nested_merge(self):
        base = {"paths": {"content_root": "/old", "authors_root": "/authors"}}
        _deep_merge(base, {"paths": {"content_root": "/new"}})
        assert base["paths"]["content_root"] == "/new"
        assert base["paths"]["authors_root"] == "/authors"

    def test_non_dict_override_replaces(self):
        base = {"section": {"key": "value"}}
        _deep_merge(base, {"section": "flat"})
        assert base["section"] == "flat"


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_no_config_file_returns_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cfg_module, "CONFIG_PATH", tmp_path / "nonexistent.yaml")
        result = load_config()
        assert "paths" in result
        assert result["defaults"]["language"] == "en"

    def test_config_file_merges_into_defaults(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"defaults": {"language": "de"}}), encoding="utf-8"
        )
        monkeypatch.setattr(cfg_module, "CONFIG_PATH", config_file)
        result = load_config()
        assert result["defaults"]["language"] == "de"
        # Other defaults preserved
        assert result["defaults"]["book_type"] == "novel"

    def test_config_path_expansion(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"paths": {"content_root": "~/books"}}), encoding="utf-8"
        )
        monkeypatch.setattr(cfg_module, "CONFIG_PATH", config_file)
        result = load_config()
        assert not result["paths"]["content_root"].startswith("~")
        assert "books" in result["paths"]["content_root"]

    def test_empty_yaml_returns_defaults(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("", encoding="utf-8")
        monkeypatch.setattr(cfg_module, "CONFIG_PATH", config_file)
        result = load_config()
        assert result["defaults"]["language"] == "en"


# ---------------------------------------------------------------------------
# Accessor helpers
# ---------------------------------------------------------------------------


class TestAccessors:
    def test_get_review_handle_default(self):
        cfg = _default_config()
        assert get_review_handle(cfg) == "Author"

    def test_get_review_handle_custom(self):
        cfg = {"defaults": {"review_handle": "Markus"}}
        assert get_review_handle(cfg) == "Markus"

    def test_get_review_handle_missing_key(self):
        assert get_review_handle({}) == "Author"

    def test_get_review_handle_null_section(self):
        # `defaults:` present but empty in user YAML parses to None, not {}.
        assert get_review_handle({"defaults": None}) == "Author"

    def test_get_content_root_returns_path(self):
        cfg = {"paths": {"content_root": "/some/path"}}
        result = get_content_root(cfg)
        assert isinstance(result, Path)
        assert result == Path("/some/path")

    def test_get_authors_root_returns_path(self):
        cfg = {"paths": {"authors_root": "/authors"}}
        result = get_authors_root(cfg)
        assert isinstance(result, Path)
        assert result == Path("/authors")

    def test_get_post_processing_tool_default(self):
        cfg = _default_config()
        assert get_post_processing_tool(cfg) == "canva"

    def test_get_post_processing_tool_custom(self):
        cfg = {"post_processing": {"tool": "gimp"}}
        assert get_post_processing_tool(cfg) == "gimp"

    def test_get_post_processing_tool_missing_key(self):
        assert get_post_processing_tool({}) == "canva"

    def test_get_post_processing_tool_null_section(self):
        # `post_processing:` present but empty in user YAML parses to None, not {}.
        assert get_post_processing_tool({"post_processing": None}) == "canva"

    def test_get_post_processing_tool_unrecognized_falls_back(self):
        cfg = {"post_processing": {"tool": "affinity"}}
        assert get_post_processing_tool(cfg) == "canva"

    def test_get_post_processing_tool_all_allowed_values(self):
        for tool in ("canva", "gimp", "photoshop"):
            assert get_post_processing_tool({"post_processing": {"tool": tool}}) == tool


# ---------------------------------------------------------------------------
# POST_PROCESSING_TOOLS <-> reference/post-processing/*.md
# ---------------------------------------------------------------------------


class TestPostProcessingReferenceFiles:
    """Every allowlisted tool must have a matching reference file cover-typography-mockup
    can load — otherwise get_post_processing_tool() accepts a value the skill can't act on."""

    def test_every_allowed_tool_has_a_reference_file(self):
        for tool in POST_PROCESSING_TOOLS:
            path = PLUGIN_ROOT / "reference" / "post-processing" / f"{tool}-typography.md"
            assert path.is_file(), f"Missing reference file for allowlisted tool {tool!r}: {path}"


# ---------------------------------------------------------------------------
# get_plugin_root
# ---------------------------------------------------------------------------


class TestGetPluginRoot:
    def test_env_var_overrides(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", "/custom/plugin/root")
        result = get_plugin_root()
        assert result == Path("/custom/plugin/root")

    def test_fallback_without_env_var(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
        result = get_plugin_root()
        # Fallback goes up 3 levels from config.py which is in tools/shared/
        assert result.is_absolute()
        assert result.exists()

    def test_fallback_is_storyforge_root(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
        result = get_plugin_root()
        # Should contain tools/ directory (plugin root)
        assert (result / "tools").exists()


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------


class TestDirectoryHelpers:
    def test_get_genres_dir(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", "/plugin")
        assert get_genres_dir() == Path("/plugin/genres")

    def test_get_book_categories_dir(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", "/plugin")
        assert get_book_categories_dir() == Path("/plugin/book_categories")

    def test_get_reference_dir(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", "/plugin")
        assert get_reference_dir() == Path("/plugin/reference")

    def test_get_templates_dir(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", "/plugin")
        assert get_templates_dir() == Path("/plugin/templates")
