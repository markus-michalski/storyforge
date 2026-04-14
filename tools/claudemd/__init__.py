"""Per-book CLAUDE.md management.

Provides functions to initialize and maintain a CLAUDE.md file in each book
project root that persists workflow rules, callbacks, and book facts across
Claude Code sessions.

The file is structured with HTML-comment markers that allow deterministic
appending without parsing markdown:

    <!-- RULES:START -->
    <!-- RULES:END -->

User-facing prefixes (Regel:, Workflow:, Callback:) are extracted by the
PreCompact hook and persisted via these functions.
"""

from tools.claudemd.manager import (
    append_callback,
    append_rule,
    append_workflow,
    get_claudemd,
    init_claudemd,
    resolve_claudemd_path,
    update_book_facts,
)
from tools.claudemd.parser import (
    SECTION_MARKERS,
    extract_prefixed_lines,
    parse_prefixed_entry,
)

__all__ = [
    "SECTION_MARKERS",
    "append_callback",
    "append_rule",
    "append_workflow",
    "extract_prefixed_lines",
    "get_claudemd",
    "init_claudemd",
    "parse_prefixed_entry",
    "resolve_claudemd_path",
    "update_book_facts",
]
