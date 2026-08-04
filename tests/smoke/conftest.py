"""Shared fixtures for MCP smoke/protocol tests."""

from __future__ import annotations

from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def pinned_plugin_root(monkeypatch):
    """Deterministic plugin-root resolution for tools that read bundled data
    (genres, craft references) via ``get_plugin_root()``.

    ``get_plugin_root()`` prefers ``$CLAUDE_PLUGIN_ROOT`` over its repo-relative
    fallback, and every real plugin session sets that var (``.mcp.json`` launches
    the server as ``${CLAUDE_PLUGIN_ROOT}/bin/run-server``) — so a test that reads
    real bundled data must pin it explicitly rather than rely on it being unset
    in whatever environment runs pytest.
    """
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(PLUGIN_ROOT))
