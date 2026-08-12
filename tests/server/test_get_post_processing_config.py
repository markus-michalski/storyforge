"""Tests for get_post_processing_config() MCP tool — Issue #552.

Mirrors get_review_handle_config() (routers/state.py): a thin read-only
accessor so cover-typography-mockup can read the configured post-processing
tool without duplicating config-loading logic.
"""

from __future__ import annotations

import json

import pytest

import routers._app as _app
from routers.cover import get_post_processing_config
from tools.shared.config import _default_config


class TestGetPostProcessingConfig:
    def test_default_tool_is_canva(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_app, "load_config", _default_config)
        result = json.loads(get_post_processing_config())
        assert result == {"tool": "canva"}

    def test_configured_tool_is_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = _default_config()
        cfg["post_processing"]["tool"] = "photoshop"
        monkeypatch.setattr(_app, "load_config", lambda: cfg)
        result = json.loads(get_post_processing_config())
        assert result == {"tool": "photoshop"}

    def test_missing_section_falls_back_to_canva(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_app, "load_config", lambda: {})
        result = json.loads(get_post_processing_config())
        assert result == {"tool": "canva"}

    def test_null_section_falls_back_to_canva(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # `post_processing:` present but empty in user YAML parses to None, not {}.
        monkeypatch.setattr(_app, "load_config", lambda: {"post_processing": None})
        result = json.loads(get_post_processing_config())
        assert result == {"tool": "canva"}

    def test_unrecognized_tool_falls_back_with_warning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = _default_config()
        cfg["post_processing"]["tool"] = "affinity"
        monkeypatch.setattr(_app, "load_config", lambda: cfg)
        result = json.loads(get_post_processing_config())
        assert result["tool"] == "canva"
        assert "affinity" in result["warning"]
