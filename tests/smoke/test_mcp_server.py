"""Smoke tests for the MCP server module (StoryForge MCP-pattern parity gap).

Companion to test_mcp_protocol.py, which drives the same server through the
real MCP wire protocol. This file only checks that the module imports and
that every tool the server actually registers on ``mcp`` is reachable as a
plain Python function on ``server`` — server.py re-exports each tool by hand
for direct-call tests/callers, and that list can silently drift from the
real tool registry (see the ``delete_author`` fix in this same change).

Tool inventory is derived from the live ``MCPServer`` instance instead of a
hand-maintained name list, so a new ``@mcp.tool()`` with no matching
re-export fails here immediately, by name, without editing this file.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

import server as server_mod
from tests.smoke._helpers import registered_tools


class TestServerImport:
    def test_server_module_loads_without_error(self):
        assert server_mod is not None

    def test_mcpserver_instance_exists(self):
        assert isinstance(server_mod.mcp, MCPServer)

    def test_at_least_one_tool_registered(self):
        assert len(registered_tools()) > 0


class TestToolReexports:
    """Every tool registered on ``mcp`` must be reachable as ``server.<name>``
    AND be the actual registered function, not a same-named stand-in.

    server.py hand-lists its re-exports across a dozen ``from routers.X import
    (...)`` blocks; a name that merely exists on ``server`` (e.g. a same-named
    helper pulled in by a different import) would pass a bare ``hasattr``
    check while the real tool stays unreachable — the same silent drift this
    test exists to catch. Comparing identity (``is``) against the registered
    function closes that gap.
    """

    def test_all_registered_tools_are_reexported_and_match(self):
        mismatches = {
            t.name: getattr(server_mod, t.name, None)
            for t in registered_tools()
            if getattr(server_mod, t.name, None) is not t.fn
        }
        assert not mismatches, (
            f"registered on mcp but missing or shadowed in server.py re-exports: {sorted(mismatches)}"
        )
