#!/usr/bin/env python3
"""Pre/PostToolUse hook: keep the chapter-draft baseline in step with Claude's writes.

Epic #663 / Issue #671. ``snapshot_draft.py pre`` keeps the draft as it is right
before a Write/Edit/MultiEdit; ``snapshot_draft.py post`` lets the baseline (kept
outside the book repository) take over Claude's change only, so the author's own
edits remain visible as the difference between the draft and the baseline.
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
            from tools.state import draft_snapshots

            if len(sys.argv) > 1 and sys.argv[1] == "pre":
                draft_snapshots.record_pre_write(payload)
            else:
                draft_snapshots.record_tool_write(payload)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
