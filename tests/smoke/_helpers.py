"""Plain helpers shared by the MCP smoke/protocol tests.

Kept separate from conftest.py: pytest loads a directory's conftest.py as a
plugin *and* test modules can import it as a regular module, which gives the
file two distinct module identities. Harmless for pure functions, but a trap
waiting for the first bit of module-level state — so fixtures live in
conftest.py, plain helpers live here.
"""

from __future__ import annotations

import server as server_mod


def registered_tools():
    """Ground truth: tools actually registered on the live MCPServer.

    ``ToolManager.list_tools()`` is the public, synchronous surface for
    this — ``MCPServer.list_tools()`` itself is async and belongs to the
    protocol-level checks in test_mcp_protocol.py, not here.
    """
    return server_mod.mcp._tool_manager.list_tools()


def registered_tool_names() -> list[str]:
    return sorted(t.name for t in registered_tools())
