"""StoryForge MCP Server — entry point and tool surface.

The @mcp.tool() handlers live in domain modules under routers/ (#120).
This file bootstraps the server and re-exports every tool function so tests
and callers can reach them via ``import server``.

Patch target for tests: ``routers._app.load_config`` (not this module).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure plugin root is on path so `tools` can be imported as a package.
plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent.parent))
if plugin_root not in sys.path:
    sys.path.insert(0, plugin_root)

# Make `routers` importable when this file is loaded via runpy.run_path.
_server_dir = str(Path(__file__).resolve().parent)
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

from routers._app import _cache, mcp  # noqa: E402,F401
import routers  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Re-exports — tool surface for ``import server`` callers and tests.
# ---------------------------------------------------------------------------

from routers.authors import (  # noqa: E402, F401
    add_vocabulary_entry,
    create_author,
    delete_discovery,
    extract_text_from_file,
    get_author,
    harvest_book_rules,
    list_authors,
    update_author,
    update_discovery_metadata,
    write_author_banned_phrase,
    write_author_discovery,
)
from routers.books import (  # noqa: E402, F401
    count_words,
    find_book,
    get_book_full,
    get_book_progress,
    get_canon_brief,
    list_books,
    list_chapters,
)
from routers.chapters import (  # noqa: E402, F401
    get_chapter_promises,
    get_chapter_writing_brief,
    get_continuity_brief,
    get_current_story_anchor,
    get_recent_chapter_timelines,
    get_review_brief,
    register_chapter_promises,
    start_chapter_draft,
    verify_tactical_setup,
)
from routers.claudemd import (  # noqa: E402, F401
    append_book_callback,
    append_book_rule,
    append_book_workflow,
    get_book_claudemd,
    init_book_claudemd,
    lint_book_rules,
    list_book_rules,
    sync_book_claudemd_from_text,
    update_book_rule,
    update_character_snapshot,
)
from routers.creation import (  # noqa: E402, F401
    create_book_structure,
    create_chapter,
    create_character,
)
from routers.gates import (  # noqa: E402, F401
    analyze_plot_logic,
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
    bootstrap_character_for_new_book,
    copy_recurring_chars_to_new_book,
    create_character_tracker,
    create_series,
    list_series_trackers_for_book,
    read_character_for_harvest,
    read_tracker_for_bootstrap,
    write_series_evolution_section,
)
from routers.canon import (  # noqa: E402, F401
    add_canon_fact,
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

if __name__ == "__main__":
    mcp.run(transport="stdio")
