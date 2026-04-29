#!/usr/bin/env python3
"""PostToolUse hook: validate chapter ``draft.md`` after Write/Edit/MultiEdit.

Thin shim (#119). Parses the hook payload and delegates to
``tools.analysis.chapter_validator``. The validator owns all scanning
logic, mode resolution, and report rendering.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent)))
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))


from tools.analysis.chapter_validator import (  # noqa: E402, F401  (re-exports)
    DEFAULT_CHAPTER_TARGET_WORDS,
    DEFAULT_MODE,
    Finding,
    SEVERITY_BLOCK,
    SEVERITY_WARN,
    VALID_MODES,
    _chapter_target_words,
    _extract_chapter_limit,
    _scaled_scene_limit,
    resolve_mode as _resolve_mode,
    validate_chapter,
    validate_chapter_path,
)

WATCHED_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})


def _read_payload() -> dict[str, Any] | None:
    if sys.stdin.isatty():
        return None
    raw = sys.stdin.read().strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _extract_file_path(payload: dict[str, Any]) -> str | None:
    """Find the file path in the hook payload — schema differs across tools."""
    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input, dict):
        fp = tool_input.get("file_path")
        if isinstance(fp, str) and fp:
            return fp
    tool_response = payload.get("tool_response") or {}
    if isinstance(tool_response, dict):
        for key in ("filePath", "file_path"):
            fp = tool_response.get(key)
            if isinstance(fp, str) and fp:
                return fp
    return None


def main() -> int:
    """Hook entry point. Returns 0 (continue), or 2 (block + feed stderr to model)."""
    payload = _read_payload()

    file_path: str = ""
    if payload is not None:
        tool_name = payload.get("tool_name")
        if isinstance(tool_name, str) and tool_name not in WATCHED_TOOLS:
            return 0
        file_path = _extract_file_path(payload) or ""
    else:
        # Legacy fallback: positional argv (used by older invocations / tests).
        if len(sys.argv) > 1:
            file_path = sys.argv[1]
        else:
            file_path = os.environ.get("CLAUDE_FILE_PATH", "") or os.environ.get("CLAUDE_TOOL_ARG_FILE_PATH", "")

    if not file_path:
        return 0

    result = validate_chapter_path(file_path)
    if not result.findings:
        return 0

    if result.will_block:
        print(result.render_block_report(), file=sys.stderr)
        return 2

    for line in result.render_diagnostics():
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
