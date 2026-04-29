"""StoryForge MCP Server — bootstrap and backward-compat surface.

The 59 ``@mcp.tool()`` handlers were split out of this module into
domain-specific routers under ``routers/`` (#120). This file now exists
to:

1. Set up ``sys.path`` so plain ``import routers`` works when ``server.py``
   is launched as a script via ``runpy.run_path`` from ``run.py``.
2. Trigger side-effect tool registration by importing the ``routers``
   package (its ``__init__`` imports every domain module).
3. Re-export the shared ``mcp`` and ``_cache`` instances plus every
   domain tool function. This preserves the historical contract that
   tests can ``import server`` and reach ``server.create_chapter``,
   ``server.list_books`` etc. directly.
4. Re-export ``load_config`` and ``get_content_root`` so the legacy
   ``monkeypatch.setattr(server, "load_config", ...)`` pattern keeps
   compiling — but **note**: tests targeting the new code path should
   patch ``routers._app.load_config`` instead, since that is the single
   symbol the router functions actually look up.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure plugin root is on path so `tools` can be imported as a package.
plugin_root = os.environ.get(
    "CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent.parent)
)
if plugin_root not in sys.path:
    sys.path.insert(0, plugin_root)

# Make `routers` importable when this file is loaded via runpy.run_path —
# `servers/storyforge-server/` is not a package, so the directory itself
# must be on sys.path.
_server_dir = str(Path(__file__).resolve().parent)
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

# Shared FastMCP instance + cache.
from routers._app import _cache, mcp  # noqa: E402

# Side-effect import — every router module registers its @mcp.tool()
# handlers on `mcp` as a side effect of being imported.
import routers  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Backward-compatible re-exports
# ---------------------------------------------------------------------------
#
# Tests and external callers historically reached every tool via
# ``server.<tool_name>`` and patched ``server.load_config``. Preserve that
# surface by re-exporting the relevant symbols from the routers + the
# shared config helpers.

from tools.shared.config import (  # noqa: E402
    get_book_categories_dir,
    get_content_root,
    get_genres_dir,
    get_reference_dir,
    get_review_handle,
    load_config,
)

from routers.authors import (  # noqa: E402, F401
    create_author,
    get_author,
    list_authors,
    update_author,
)
from routers.books import (  # noqa: E402, F401
    count_words,
    find_book,
    get_book_full,
    get_book_progress,
    list_books,
    list_chapters,
)
from routers.chapters import (  # noqa: E402, F401
    get_chapter,
    get_chapter_writing_brief,
    get_continuity_brief,
    get_current_story_anchor,
    get_recent_chapter_timelines,
    get_review_brief,
    start_chapter_draft,
    verify_tactical_setup,
)
from routers.claudemd import (  # noqa: E402, F401
    append_book_callback,
    append_book_rule,
    append_book_workflow,
    get_book_claudemd,
    get_character,
    init_book_claudemd,
    sync_book_claudemd_from_text,
    update_book_claudemd_facts,
)
from routers.creation import (  # noqa: E402, F401
    create_book_structure,
    create_chapter,
    create_character,
)
from routers.gates import (  # noqa: E402, F401
    check_memoir_consent,
    run_pre_export_gates,
    run_quality_gates,
    scan_manuscript,
    validate_book_structure,
    validate_chapter,
    validate_timeline_consistency,
    verify_callbacks,
)
from routers.ideas import (  # noqa: E402, F401
    create_idea,
    get_idea,
    list_ideas,
    promote_idea,
    update_idea,
)
from routers.memoir import (  # noqa: E402, F401
    create_person,
    set_memoir_structure_type,
)
from routers.reference import (  # noqa: E402, F401
    get_craft_reference,
    get_genre,
    list_craft_references,
    list_genres,
)
from routers.scenes import (  # noqa: E402, F401
    create_scene_list,
    update_scene,
)
from routers.series import (  # noqa: E402, F401
    add_book_to_series,
    create_series,
    get_series,
)
from routers.state import (  # noqa: E402, F401
    get_book_category_dir,
    get_review_handle_config,
    get_session,
    rebuild_state,
    resolve_path,
    update_field,
    update_session,
)

# ---------------------------------------------------------------------------
# Patch-mirroring shim — preserves the legacy ``server.load_config`` patch
# point.
# ---------------------------------------------------------------------------
#
# The router modules call ``_app.load_config()`` (and the other config
# helpers), not ``server.load_config()``. After the #120 split, a test that
# does ``patch.object(server, "load_config", return_value=fake)`` would only
# patch the re-export here while the actual call site (``_app``) keeps
# returning the real config.
#
# Rather than rewrite every existing test (~13 files), we hook this module's
# ``__setattr__`` to mirror writes for the specific config helpers onto
# ``routers._app`` (and ``tools.shared.config``, since that is what
# ``tools.state.indexer`` imports). This means ``patch.object(server, ...)``
# Just Works for the legacy test surface without leaking into other module
# attributes.
import routers._app as _app_module  # noqa: E402
import tools.shared.config as _config_module  # noqa: E402

_MIRRORED_SYMBOLS = {
    "load_config",
    "get_content_root",
    "get_genres_dir",
    "get_reference_dir",
    "get_review_handle",
    "get_book_categories_dir",
}


class _PatchMirroringModule(type(sys.modules[__name__])):
    """Module subclass that mirrors writes for known config helpers."""

    def __setattr__(self, name: str, value) -> None:  # noqa: ANN001
        super().__setattr__(name, value)
        if name in _MIRRORED_SYMBOLS:
            setattr(_app_module, name, value)
            setattr(_config_module, name, value)


sys.modules[__name__].__class__ = _PatchMirroringModule


if __name__ == "__main__":
    mcp.run(transport="stdio")
