"""Draft baselines and manual-edit hunks — Epic #663 / Issue #671 (phase 2).

A baseline is the text of a chapter's ``draft.md`` as Claude last wrote it. It
is kept outside the book repository and updated by replaying every Claude
Write/Edit/MultiEdit onto it, so the author's own edits stay visible as the
difference between ``draft.md`` and the baseline. The author triggers the
comparison themselves ("Ich habe den Text geändert"); nothing is captured
automatically. Memoir books get no baseline at all.
"""

from __future__ import annotations

import difflib
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import tools.db.connection as _db
from tools.shared.paths import _validate_slug

MIN_CHANGED_WORDS = 4  # a change of up to three words is not voice evidence
DEFAULT_MAX_HUNKS = 20
DEFAULT_MAX_CHARS = 4000

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_WORD_RE = re.compile(r"\w+", re.UNICODE)
_PARA_SPLIT = re.compile(r"\n\s*\n")


def snapshots_dir() -> Path:
    """Baselines live next to the databases, never inside a synced book repository."""
    return Path(_db.DB_DIR).parent / "snapshots"


def _check_slug(value: str, name: str) -> None:
    if not isinstance(value, str) or not _SLUG_RE.match(value) or ".." in value:
        raise ValueError(f"invalid {name}: {value!r}")


def snapshot_file(book_slug: str, chapter_slug: str) -> Path:
    _check_slug(book_slug, "book_slug")
    _check_slug(chapter_slug, "chapter_slug")
    _validate_slug(book_slug, "book_slug")
    _validate_slug(chapter_slug, "chapter_slug")
    return snapshots_dir() / book_slug / f"{chapter_slug}.md"


def _stale_file(book_slug: str, chapter_slug: str) -> Path:
    return snapshot_file(book_slug, chapter_slug).with_suffix(".stale")


def chapter_ref(path: str | Path) -> tuple[str, str] | None:
    """``(book_slug, chapter_slug)`` for ``.../{book}/chapters/{chapter}/draft.md``, else None."""
    p = Path(path)
    if p.name != "draft.md":
        return None
    parts = p.parts
    if len(parts) < 4 or parts[-3] != "chapters":
        return None
    return parts[-4], parts[-2]


def read_snapshot(book_slug: str, chapter_slug: str) -> str | None:
    f = snapshot_file(book_slug, chapter_slug)
    if not f.is_file():
        return None
    return f.read_text(encoding="utf-8")


def write_snapshot(book_slug: str, chapter_slug: str, text: str) -> None:
    """Atomically store a baseline and clear the stale marker."""
    f = snapshot_file(book_slug, chapter_slug)
    f.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=f.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(tmp, f)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    _stale_file(book_slug, chapter_slug).unlink(missing_ok=True)


def mark_stale(book_slug: str, chapter_slug: str) -> None:
    """The baseline can no longer be kept in step; drop it until it is rewritten explicitly."""
    snapshot_file(book_slug, chapter_slug).unlink(missing_ok=True)
    marker = _stale_file(book_slug, chapter_slug)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("stale\n", encoding="utf-8")


def is_stale(book_slug: str, chapter_slug: str) -> bool:
    return _stale_file(book_slug, chapter_slug).is_file()


def apply_tool_edit(text: str, tool_name: str, tool_input: dict[str, Any]) -> str | None:
    """Replay one Claude write onto ``text``. None when it cannot be applied."""
    if tool_name == "Write":
        content = tool_input.get("content")
        return content if isinstance(content, str) else None

    edits: list[Any]
    if tool_name == "Edit":
        edits = [tool_input]
    elif tool_name == "MultiEdit":
        raw = tool_input.get("edits")
        if not isinstance(raw, list):
            return None
        edits = raw
    else:
        return None

    out = text
    for edit in edits:
        if not isinstance(edit, dict):
            return None
        old, new = edit.get("old_string"), edit.get("new_string")
        if not isinstance(old, str) or not isinstance(new, str) or not old or old not in out:
            return None
        out = out.replace(old, new) if edit.get("replace_all") else out.replace(old, new, 1)
    return out


def _is_memoir(draft_path: Path) -> bool:
    readme = draft_path.parent.parent.parent / "README.md"
    try:
        head = readme.read_text(encoding="utf-8").split("---", 2)
    except OSError:
        return False
    if len(head) < 3:
        return False
    return re.search(r'^book_category:\s*["\']?memoir["\']?\s*$', head[1], re.MULTILINE) is not None


def record_tool_write(payload: dict[str, Any]) -> None:
    """Keep the baseline in step with a Claude write on a chapter draft. Never raises."""
    try:
        tool_input = payload.get("tool_input")
        tool_name = payload.get("tool_name")
        if not isinstance(tool_input, dict) or not isinstance(tool_name, str):
            return
        file_path = tool_input.get("file_path")
        if not isinstance(file_path, str):
            return
        ref = chapter_ref(file_path)
        if ref is None:
            return
        draft = Path(file_path)
        if _is_memoir(draft):
            return
        book, chapter = ref
        if is_stale(book, chapter):
            return

        current = read_snapshot(book, chapter)
        if current is None:
            # First write we see: the file as it is now is the best baseline there is.
            if draft.is_file():
                write_snapshot(book, chapter, draft.read_text(encoding="utf-8"))
            return

        updated = apply_tool_edit(current, tool_name, tool_input)
        if updated is None:
            mark_stale(book, chapter)
        else:
            write_snapshot(book, chapter, updated)
    except Exception:  # a hook must never get in the way of the write
        return


def _paragraphs(text: str, review_handle: str) -> list[str]:
    paras = [p.strip() for p in _PARA_SPLIT.split(text.replace("\r\n", "\n")) if p.strip()]
    if review_handle:
        prefix = f"{review_handle.casefold()}:"
        paras = [p for p in paras if not p.casefold().startswith(prefix)]
    return paras


def _words(text: str) -> list[str]:
    return [w.casefold() for w in _WORD_RE.findall(text)]


def _changed_words(before: str, after: str) -> int:
    a, b = _words(before), _words(after)
    removed = added = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in {"replace", "delete"}:
            removed += i2 - i1
        if tag in {"replace", "insert"}:
            added += j2 - j1
    return max(removed, added)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


def compute_hunks(
    baseline: str,
    current: str,
    *,
    review_handle: str = "",
    min_changed_words: int = MIN_CHANGED_WORDS,
    max_hunks: int = DEFAULT_MAX_HUNKS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> dict[str, Any]:
    """Paragraph-level differences between baseline and draft that look like voice edits."""
    base = _paragraphs(baseline, review_handle)
    cur = _paragraphs(current, review_handle)

    hunks: list[dict[str, Any]] = []
    ignored_small = 0
    matcher = difflib.SequenceMatcher(None, base, cur, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        # Equal paragraph counts are paired one to one so every rewritten paragraph is
        # its own hunk; otherwise the whole block is one hunk.
        if tag == "replace" and (i2 - i1) == (j2 - j1):
            pairs = [(base[i1 + k], cur[j1 + k]) for k in range(i2 - i1)]
        else:
            pairs = [("\n\n".join(base[i1:i2]), "\n\n".join(cur[j1:j2]))]
        for before, after in pairs:
            changed = _changed_words(before, after)
            if changed < min_changed_words:
                if changed > 0:
                    ignored_small += 1
                continue
            kind = "insert" if not before else "delete" if not after else "replace"
            hunks.append({
                "kind": kind,
                "before": before,
                "after": after,
                "changed_words": changed,
            })

    total = len(hunks)
    shown = hunks[:max_hunks]
    for i, hunk in enumerate(shown, start=1):
        hunk["index"] = i
        hunk["before"] = _clip(hunk["before"], max_chars)
        hunk["after"] = _clip(hunk["after"], max_chars)
    return {
        "hunks": shown,
        "total": total,
        "ignored_small": ignored_small,
        "truncated": total > len(shown),
    }
