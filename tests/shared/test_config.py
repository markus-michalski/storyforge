"""Tests for tools.shared.config — Issue #124."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from tools.shared import config as cfg_module
from tools.shared.config import (
    _deep_merge,
    _default_config,
    get_authors_root,
    get_book_categories_dir,
    get_content_root,
    get_genres_dir,
    get_plugin_root,
    get_reference_dir,
    get_review_handle,
    get_templates_dir,
    load_config,
)


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
