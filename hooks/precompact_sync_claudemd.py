#!/usr/bin/env python3
"""PreCompact hook: Extract prefixed entries from the session transcript
and persist them to the active book's CLAUDE.md.

Claude Code invokes this hook right before compacting the conversation
context. The hook receives a JSON payload on stdin with the transcript
path. We scan user messages for the deterministic prefixes ``Regel:``,
``Workflow:``, and ``Callback:`` and append matches to the CLAUDE.md of
the book referenced by the current StoryForge session.

The hook never calls an LLM; all extraction is pure regex. This keeps
compaction cheap even on long sessions.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent)))

# Make tools package importable when the hook runs standalone.
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))


def _read_transcript(path: Path) -> list[dict[str, Any]]:
    """Read a Claude Code transcript (JSONL) and return parsed entries."""
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _extract_user_text(entries: list[dict[str, Any]]) -> str:
    """Concatenate all user-message text from a transcript."""
    parts: list[str] = []
    for entry in entries:
        if entry.get("type") != "user":
            continue
        message = entry.get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
    return "\n".join(parts)


def _active_book_slug() -> str | None:
    """Look up the current book slug from the StoryForge state cache.

    StoryForge stores session info at ``~/.storyforge/cache/state.json``
    under the ``session.last_book`` key (see server ``update_session``).
    """
    from tools.shared.config import STATE_PATH  # local import after sys.path

    if not STATE_PATH.exists():
        return None
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    session = state.get("session") or {}
    slug = session.get("last_book")
    return slug if isinstance(slug, str) and slug else None


def run(payload: dict[str, Any]) -> dict[str, Any]:
    """Process a PreCompact payload and return a result summary."""
    transcript_path = payload.get("transcript_path") or payload.get("transcript")
    if not transcript_path:
        return {"skipped": "no transcript_path"}

    book_slug = _active_book_slug()
    if not book_slug:
        return {"skipped": "no active book in session"}

    from tools.claudemd.manager import (
        append_callback,
        append_rule,
        append_workflow,
        resolve_claudemd_path,
    )
    from tools.claudemd.parser import extract_prefixed_lines
    from tools.shared.config import load_config

    config = load_config()
    claudemd_path = resolve_claudemd_path(config, book_slug)
    if not claudemd_path.exists():
        return {"skipped": f"no CLAUDE.md for book '{book_slug}'"}

    entries = _read_transcript(Path(transcript_path))
    text = _extract_user_text(entries)
    prefixed = extract_prefixed_lines(text)

    counts = {"rule": 0, "workflow": 0, "callback": 0, "errors": 0}
    impl = {"rule": append_rule, "workflow": append_workflow, "callback": append_callback}

    for kind, body in prefixed:
        try:
            impl[kind](config, book_slug, body)
            counts[kind] += 1
        except Exception:
            counts["errors"] += 1

    return {"book": book_slug, "counts": counts}


def main() -> None:
    """Entry point. Reads JSON from stdin, writes a summary to stderr."""
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    try:
        result = run(payload)
    except Exception as exc:  # pragma: no cover — belt-and-suspenders
        # Never fail compaction: log and continue.
        print(f"precompact_sync_claudemd error: {exc}", file=sys.stderr)
        sys.exit(0)

    # Print summary to stderr so Claude Code can log it; stdout is reserved
    # for hook protocol output.
    print(json.dumps(result), file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
