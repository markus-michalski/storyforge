"""Shared FastMCP instance and module-level state for all router modules.

Every router module imports the shared ``mcp`` and ``_cache`` from here so that
all ``@mcp.tool()`` decorators register on a single FastMCP server. Common
config helpers are also re-exported so router modules — and tests — have a
single, stable patch target (``routers._app.load_config`` etc.) regardless
of which domain module the tool itself lives in.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from tools.shared.config import (
    get_book_categories_dir,
    get_content_root,
    get_genres_dir,
    get_reference_dir,
    get_review_handle,
    load_config,
)
from tools.state.indexer import StateCache

# Single FastMCP instance shared by every router module.
mcp = FastMCP("storyforge-mcp")

# Single state cache shared by every router module.
_cache = StateCache()


__all__ = [
    "mcp",
    "_cache",
    "load_config",
    "get_content_root",
    "get_genres_dir",
    "get_reference_dir",
    "get_review_handle",
    "get_book_categories_dir",
]
