"""In-process MCP protocol smoke tests (StoryForge MCP-pattern parity gap).

Unlike test_mcp_server.py, which calls tool functions directly as plain
Python functions, these tests drive the server through an actual
mcp.client.Client round-trip — the only tests in this repo that exercise
tool registration, schema validation, and JSON-RPC framing/serialization
rather than just the underlying business logic.

Pattern verified against mcp 2.0.0 (mm-dev-toolkit#114/#117); mirrored here
for parity with the mm-dev-toolkit MCP-server reference pattern.
"""

from __future__ import annotations

import json

import pytest
from mcp.client import Client

import server as server_mod
from tests.smoke._helpers import registered_tool_names


@pytest.mark.asyncio
async def test_list_tools_matches_registered_tool_names():
    async with Client(server_mod.mcp) as client:
        result = await client.list_tools()
    tool_names = {t.name for t in result.tools}
    assert tool_names, "no tools registered — registry lookup is silently vacuous"
    assert tool_names == set(registered_tool_names())


@pytest.mark.asyncio
async def test_call_tool_round_trip_through_protocol(pinned_plugin_root):
    """list_genres() reads bundled data via get_plugin_root() — pinned_plugin_root
    makes that resolve to this repo regardless of ambient $CLAUDE_PLUGIN_ROOT."""
    async with Client(server_mod.mcp) as client:
        result = await client.call_tool("list_genres", {})
    assert not result.is_error, result.content
    assert result.structured_content is not None
    payload = json.loads(result.structured_content["result"])
    assert payload["count"] == len(payload["genres"])
    assert "fantasy" in payload["genres"]


@pytest.mark.asyncio
async def test_call_tool_missing_required_arg_fails_via_protocol_validation():
    """A direct Python call to get_book_full() would raise TypeError. Through the
    protocol, mcp validates arguments against the tool's schema (Pydantic) before
    the handler ever runs — this is the actual value of the protocol test layer
    over test_mcp_server.py's direct function calls."""
    async with Client(server_mod.mcp) as client:
        result = await client.call_tool("get_book_full", {})
    assert result.is_error


@pytest.mark.asyncio
async def test_call_unknown_tool_fails_via_protocol():
    async with Client(server_mod.mcp) as client:
        result = await client.call_tool("does_not_exist", {})
    assert result.is_error


@pytest.mark.asyncio
async def test_every_tool_declares_an_output_schema():
    """Structural regression guard against the bare `-> dict` bug class
    (mm-dev-toolkit#118): mcp>=2.0.0 only populates CallToolResult.structured_content
    when a tool's return annotation is a concrete type — a bare `dict` (no type
    params) leaves output_schema None on the tool's protocol-level listing. Every
    StoryForge tool currently returns `-> str` (JSON-encoded), which does populate
    it; this guards against a future tool being added with a bare `-> dict`
    annotation instead, by name, with no fixtures or I/O required."""
    async with Client(server_mod.mcp) as client:
        result = await client.list_tools()
    missing = sorted(t.name for t in result.tools if t.output_schema is None)
    assert missing == [], (
        "these tools leave CallToolResult.structured_content unpopulated under "
        f"mcp>=2.0.0 (bare `dict` return annotation?): {missing}"
    )
