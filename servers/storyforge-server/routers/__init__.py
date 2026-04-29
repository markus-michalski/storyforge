"""StoryForge MCP routers package.

Importing this package triggers side-effect registration of every
``@mcp.tool()`` decorated function on the shared ``_app.mcp`` instance.
The order below is intentionally alphabetical — modules don't depend on
each other beyond the shared ``_app`` (mcp + _cache + config helpers).
"""

from __future__ import annotations

# Side-effect imports — each module registers its own @mcp.tool() handlers.
from . import (  # noqa: F401
    authors,
    books,
    chapters,
    claudemd,
    creation,
    gates,
    ideas,
    memoir,
    reference,
    scenes,
    series,
    state,
)
