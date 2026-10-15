#!/usr/bin/env python3
"""PostToolUse hook: keep the chapter-draft baseline in step with Claude's writes.

Epic #663 / Issue #671. Replays every Write/Edit/MultiEdit on a chapter
``draft.md`` onto a baseline kept outside the book repository, so the author's
own edits remain visible as the difference between the draft and the baseline.
Memoir books are skipped. The hook only records; it never blocks, prints or fails.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent)))
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

WATCHED_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})


def main() -> int:
    try:
        raw = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
        payload = json.loads(raw) if raw else None
        if isinstance(payload, dict) and payload.get("tool_name") in WATCHED_TOOLS:
            from tools.state.draft_snapshots import record_tool_write

            record_tool_write(payload)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
