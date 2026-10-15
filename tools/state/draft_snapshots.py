"""Draft baselines and manual-edit hunks — Epic #663 / Issue #671 (phase 2).

A baseline is the text of a chapter's ``draft.md`` as Claude last wrote it. It
is kept outside the book repository. After every Claude Write/Edit/MultiEdit
the baseline takes over **Claude's change only**, via a paragraph-level
three-way merge of (baseline, file before the edit, file after the edit); the
author's own edits stay visible as the difference between ``draft.md`` and the
baseline, even when Claude removes a review comment or edits next to them.

A PreToolUse hook keeps the draft as it is right before Claude's write; the
PostToolUse hook merges (baseline, that copy, the file afterwards). Without
that copy the hook response's ``originalFile`` is used if present; a Write
takes Claude's output as the baseline; anything else marks the baseline stale.

The author triggers the comparison themselves ("Ich habe den Text geändert");
nothing is captured automatically. Memoir books get no baseline at all, and a
book whose category cannot be read as fiction is skipped (fail closed).
"""

from __future__ import annotations

import contextlib
import difflib
import os
import re
import shutil
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

import tools.db.connection as _db
from tools.shared.paths import _validate_slug

MIN_CHANGED_WORDS = 4  # a change of up to three words is not voice evidence
DEFAULT_MAX_HUNKS = 20
DEFAULT_MAX_CHARS = 8000
LARGE_BLOCK_WORDS = 20_000
PAIR_SIMILARITY = 0.5

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_PARA_SPLIT = re.compile(r"\n\s*\n")


def snapshots_dir() -> Path:
    """Baselines live next to the databases, never inside a synced book repository.

    ``STORYFORGE_SNAPSHOT_DIR`` overrides the location (e.g. when the databases sit
    in a synced folder).
    """
    override = os.environ.get("STORYFORGE_SNAPSHOT_DIR")
    if override:
        return Path(override)
    return Path(_db.DB_DIR).parent / "snapshots"


def snapshot_file(book_slug: str, chapter_slug: str) -> Path:
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


def remove_book_snapshots(book_slug: str) -> None:
    """Delete every baseline of a book (used when a book turns out to be memoir)."""
    if not isinstance(book_slug, str) or not book_slug.strip():
        raise ValueError("book_slug must not be empty")
    _validate_slug(book_slug, "book_slug")
    shutil.rmtree(snapshots_dir() / book_slug, ignore_errors=True)


@contextlib.contextmanager
def _lock(book_slug: str, chapter_slug: str, timeout: float = 5.0) -> Iterator[None]:
    """Best-effort per-chapter lock so parallel hooks do not lose each other's merge."""
    lock = snapshot_file(book_slug, chapter_slug).with_suffix(".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    held = False
    while not held:
        try:
            lock.touch(exist_ok=False)  # exclusive create
            held = True
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 30:
                    lock.unlink(missing_ok=True)  # abandoned lock
                    continue
            except OSError:
                continue
            if time.monotonic() > deadline:
                break
            time.sleep(0.02)
    try:
        yield
    finally:
        if held:
            lock.unlink(missing_ok=True)


# --------------------------------------------------------------------------- merge


def _paras(text: str) -> list[str]:
    return [p.strip() for p in _PARA_SPLIT.split(text.replace("\r\n", "\n")) if p.strip()]


def merge_claude_change(baseline: str, before: str, after: str) -> str:
    """Baseline after taking over only Claude's change ``before`` -> ``after``.

    ``baseline`` is what Claude last wrote, ``before`` the draft just before this
    edit (baseline plus the author's edits), ``after`` the draft just after it.
    Paragraphs Claude did not touch keep their baseline text, so the author's
    edits there remain a difference. Where Claude rewrote or removed a paragraph,
    Claude's version wins, and so does the whole of an author-edited block that
    Claude touched (an author edit inside it is absorbed: Claude saw it).
    """
    base, prev, new = _paras(baseline), _paras(before), _paras(after)

    # Which baseline paragraphs stand behind each paragraph of ``before``?
    contrib: dict[int, list[str]] = {}
    gap: dict[int, list[str]] = {}
    for tag, b1, b2, p1, p2 in difflib.SequenceMatcher(None, base, prev, autojunk=False).get_opcodes():
        if tag == "equal" or (p2 > p1 and (b2 - b1) == (p2 - p1)):
            for t in range(p2 - p1):  # same size: one to one
                contrib[p1 + t] = [base[b1 + t]]
        elif p2 > p1 and b2 > b1:
            # Unequal size: pair by similarity so an author-edited paragraph keeps its
            # baseline text and an inserted one (a comment, a new paragraph) has none.
            k = p1
            for old, cur in _pair_block(base[b1:b2], prev[p1:p2]):
                if cur:
                    contrib[k] = [old] if old else []
                    k += 1
                else:
                    gap.setdefault(k, []).append(old)  # the author deleted it
        elif p2 > p1:
            for k in range(p1, p2):
                contrib[k] = []  # inserted by the author, not in the baseline
        elif b2 > b1:
            gap.setdefault(p1, []).extend(base[b1:b2])

    out: list[str] = []
    for tag, p1, p2, d1, d2 in difflib.SequenceMatcher(None, prev, new, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(p1, p2):
                out.extend(gap.get(k, []))
                out.extend(contrib.get(k, []))
        else:
            for k in range(p1, p2):
                out.extend(gap.get(k, []))  # the author's deletion site stays untouched
            out.extend(new[d1:d2])
    out.extend(gap.get(len(prev), []))
    return "\n\n".join(out)


# --------------------------------------------------------------------------- hook


def is_fiction_category(value: Any) -> bool:
    """Only an absent or ``fiction`` category qualifies; anything else fails closed."""
    if value is None:
        return True
    return isinstance(value, str) and value.strip().lower() == "fiction"


def _fiction_book(draft: Path) -> bool:
    """True only for a readable, parseable README that declares fiction or no category."""
    readme = draft.parent.parent.parent / "README.md"
    try:
        text = readme.read_text(encoding="utf-8-sig")
    except OSError:
        return False
    match = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", text, re.DOTALL)
    if not match:
        return False
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return False
    if not isinstance(meta, dict):
        return False
    return is_fiction_category(meta.get("book_category"))


def _is_known_chapter(draft: Path, book: str, chapter: str) -> bool:
    """The file must be the draft of a book StoryForge knows, not a copy elsewhere."""
    from tools.shared.config import load_config
    from tools.shared.paths import resolve_project_path

    expected = resolve_project_path(load_config(), book) / "chapters" / chapter / "draft.md"
    try:
        return draft.resolve() == expected.resolve()
    except OSError:
        return False


def _pre_file(book_slug: str, chapter_slug: str) -> Path:
    return snapshot_file(book_slug, chapter_slug).with_suffix(".pre")


def _eligible(payload: dict[str, Any]) -> tuple[Path, str, str, dict[str, Any], str] | None:
    """(draft, book, chapter, tool_input, tool_name) for a write on a fiction chapter draft."""
    tool_input = payload.get("tool_input")
    tool_name = payload.get("tool_name")
    if not isinstance(tool_input, dict) or not isinstance(tool_name, str):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str):
        return None
    ref = chapter_ref(file_path)
    if ref is None:
        return None
    draft = Path(file_path)
    book, chapter = ref
    if not _is_known_chapter(draft, book, chapter):
        return None
    if not _fiction_book(draft):
        remove_book_snapshots(book)
        return None
    return draft, book, chapter, tool_input, tool_name


def record_pre_write(payload: dict[str, Any]) -> None:
    """PreToolUse: keep the draft as it is right before Claude's write. Never raises."""
    try:
        hit = _eligible(payload)
        if hit is None:
            return
        draft, book, chapter, _tool_input, _tool_name = hit
        pre = _pre_file(book, chapter)
        if draft.is_file() and read_snapshot(book, chapter) is not None and not is_stale(book, chapter):
            pre.parent.mkdir(parents=True, exist_ok=True)
            pre.write_text(draft.read_text(encoding="utf-8"), encoding="utf-8", newline="")
        else:
            pre.unlink(missing_ok=True)
    except Exception:
        return


def record_tool_write(payload: dict[str, Any]) -> None:
    """PostToolUse: let the baseline take over Claude's change only. Never raises."""
    try:
        hit = _eligible(payload)
        if hit is None:
            return
        draft, book, chapter, _tool_input, tool_name = hit
        if not draft.is_file():
            return

        after = draft.read_text(encoding="utf-8")
        with _lock(book, chapter):
            pre = _pre_file(book, chapter)
            before = pre.read_text(encoding="utf-8") if pre.is_file() else None
            pre.unlink(missing_ok=True)
            if is_stale(book, chapter):
                return
            baseline = read_snapshot(book, chapter)
            if baseline is None:
                write_snapshot(book, chapter, after)  # best baseline there is
                return

            if before is None:
                response = payload.get("tool_response")
                original = response.get("originalFile") if isinstance(response, dict) else None
                if isinstance(original, str):
                    before = original
                elif tool_name == "Write":
                    before = baseline  # full rewrite: Claude's output becomes the baseline
            if before is None:
                mark_stale(book, chapter)  # no way to tell Claude's change from the author's
                return
            write_snapshot(book, chapter, merge_claude_change(baseline, before, after))
    except Exception:  # a hook must never get in the way of the write
        return


# --------------------------------------------------------------------------- hunks


def _words(text: str) -> list[str]:
    return [w.casefold() for w in _WORD_RE.findall(text)]


def _changed_words(before: str, after: str) -> int:
    a, b = _words(before), _words(after)
    if len(a) + len(b) > LARGE_BLOCK_WORDS:
        return max(len(a), len(b))
    removed = added = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in {"replace", "delete"}:
            removed += i2 - i1
        if tag in {"replace", "insert"}:
            added += j2 - j1
    return max(removed, added)


def _comment_pattern(review_handle: str) -> re.Pattern[str] | None:
    handle = review_handle.strip()
    if not handle:
        return None
    return re.compile(
        rf"^\s*(?:>\s*)*(?:\*\*|__)?{re.escape(handle)}\s*(?:\*\*|__)?\s*:",
        re.IGNORECASE | re.MULTILINE,
    )


def _prose_paragraphs(text: str, review_handle: str) -> list[str]:
    paras = _paras(text)
    pattern = _comment_pattern(review_handle)
    if pattern is None:
        return paras
    return [p for p in paras if not pattern.search(p)]


def _clip(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit].rstrip() + " …", True


def _pair_block(before: list[str], after: list[str]) -> list[tuple[str, str]]:
    """Pair paragraphs of an unequal replace block by similarity; the rest stand alone."""
    pairs: list[tuple[str, str]] = []
    unused = list(range(len(after)))
    cursor = 0
    for b in before:
        best, best_ratio = None, PAIR_SIMILARITY
        for idx in unused:
            if idx < cursor:
                continue
            ratio = difflib.SequenceMatcher(None, b, after[idx], autojunk=False).ratio()
            if ratio > best_ratio:
                best, best_ratio = idx, ratio
        if best is None:
            pairs.append((b, ""))
            continue
        for idx in [i for i in unused if cursor <= i < best]:
            pairs.append(("", after[idx]))
            unused.remove(idx)
        pairs.append((b, after[best]))
        unused.remove(best)
        cursor = best + 1
    pairs.extend(("", after[idx]) for idx in unused)
    return pairs


def compute_hunks(
    baseline: str,
    current: str,
    *,
    review_handle: str = "",
    min_changed_words: int = MIN_CHANGED_WORDS,
    max_hunks: int = DEFAULT_MAX_HUNKS,
    max_chars: int = DEFAULT_MAX_CHARS,
    offset: int = 0,
) -> dict[str, Any]:
    """Paragraph-level differences between baseline and draft that look like voice edits."""
    base = _prose_paragraphs(baseline, review_handle)
    cur = _prose_paragraphs(current, review_handle)

    found: list[dict[str, Any]] = []
    ignored_small = 0
    matcher = difflib.SequenceMatcher(None, base, cur, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace" and (i2 - i1) == (j2 - j1):
            pairs = [(base[i1 + k], cur[j1 + k]) for k in range(i2 - i1)]
        elif tag == "replace":
            pairs = _pair_block(base[i1:i2], cur[j1:j2])
        else:
            pairs = [("\n\n".join(base[i1:i2]), "\n\n".join(cur[j1:j2]))]
        for before, after in pairs:
            changed = _changed_words(before, after)
            if changed < min_changed_words:
                if changed > 0:
                    ignored_small += 1
                continue
            kind = "insert" if not before else "delete" if not after else "replace"
            found.append({"kind": kind, "before": before, "after": after, "changed_words": changed})

    total = len(found)
    start = max(0, offset)
    window = found[start: start + max_hunks]
    for i, hunk in enumerate(window, start=start + 1):
        hunk["index"] = i
        hunk["before"], clipped_b = _clip(hunk["before"], max_chars)
        hunk["after"], clipped_a = _clip(hunk["after"], max_chars)
        hunk["clipped"] = clipped_b or clipped_a
    return {
        "hunks": window,
        "total": total,
        "offset": start,
        "ignored_small": ignored_small,
        "truncated": start + len(window) < total,
    }
