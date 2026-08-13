"""Callback register validator.

Parses the ``## Callback Register`` section from a book's CLAUDE.md and
cross-references each callback against all drafted chapter files.

Produces three status buckets:
- ``satisfied``          — callback appears in at least one chapter, no overdue deadline
- ``deferred``           — callback never appeared, or appeared then went silent
                           (without a must-not-forget marker)
- ``potentially_dropped`` — overdue expected-return deadline, OR
                            must-not-forget callback silent for >10 chapters
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

_CALLBACKS_SECTION_RE = re.compile(
    r"<!-- CALLBACKS:START -->(.*?)<!-- CALLBACKS:END -->",
    re.DOTALL,
)
_BOLD_NAME_RE = re.compile(r"\*\*([^*]+)\*\*")
_EXPECTED_RETURN_RE = re.compile(r"expected\s+return\s+by\s+Ch\s+(\d+)", re.IGNORECASE)
_MUST_NOT_FORGET_RE = re.compile(r"_\(must not be forgotten\)_", re.IGNORECASE)
_ADDED_DATE_RE = re.compile(r"\s*_\(added \d{4}-\d{2}-\d{2}\)_")

_STOPWORDS = frozenset(
    [
        "the",
        "a",
        "an",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "and",
        "or",
        "but",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "not",
        "no",
        "so",
        "his",
        "her",
        "its",
        "their",
        "our",
        "your",
        "my",
        "by",
        "as",
        "from",
        "that",
        "this",
        "these",
        "those",
        "which",
        "who",
    ]
)

# Chapters silent for longer than this threshold trigger deferred/dropped
_SILENCE_THRESHOLD = 10


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CallbackEntry:
    name: str
    search_terms: list[str]
    expected_return_ch: int | None = None
    must_not_forget: bool = False
    raw_line: str = ""
    # False for entries that only exist as legacy CLAUDE.md markers, with no
    # corresponding book_rules DB row. get_chapter_writing_brief/get_review_brief
    # only ever read the DB (tools/db/brief_helpers.py) — so a legacy-marker-only
    # entry is data the chapter-writer never had a chance to service. verify_callbacks()
    # caps such entries at WARN (deferred), never FAIL (potentially_dropped), so a
    # pre-migration book can't get its export silently blocked over a callback the
    # writer was never shown.
    from_db: bool = True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_MAX_NAME_WORDS_FOR_TERM_SPLIT = 6


def _extract_search_terms(name: str) -> list[str]:
    """Derive search terms from a callback name.

    Returns the full name plus any significant individual words (≥3 chars,
    non-stopword) so both exact-phrase and partial matching work.

    If ``name`` looks like a full sentence rather than a short label (more
    than ``_MAX_NAME_WORDS_FOR_TERM_SPLIT`` words — a free-form DB entry
    written as prose rather than a short callback name), only the full
    phrase is used as a search term. Splitting a sentence into individual
    words produces common words (e.g. "soll", "Kapitel") that match
    unrelated prose and report false "satisfied" callbacks.
    """
    terms: list[str] = []
    name_clean = name.strip()
    if len(name_clean) >= 3:
        terms.append(name_clean)
    words = re.findall(r"[a-zA-Z'À-ɏ]+", name_clean)
    if len(words) > _MAX_NAME_WORDS_FOR_TERM_SPLIT:
        return terms
    for word in words:
        w = word.lower().strip("'")
        if len(w) >= 3 and w not in _STOPWORDS and word not in terms:
            terms.append(word)
    return terms


def _parse_callback_body(
    body: str, *, has_bullet_prefix: bool, raw_line: str, from_db: bool = True
) -> CallbackEntry | None:
    """Parse one callback's annotation text into a ``CallbackEntry``.

    Shared by both callback sources: a ``- `` bullet line from a legacy
    CLAUDE.md marker block (``has_bullet_prefix=True``) and a raw
    ``book_rules`` DB row text (``has_bullet_prefix=False`` — DB rows store
    the annotation text directly, with no leading bullet marker).
    """
    line_clean = _ADDED_DATE_RE.sub("", body.strip()).strip()

    bold_match = _BOLD_NAME_RE.search(line_clean)
    if bold_match:
        name = bold_match.group(1).strip()
    else:
        source_text = line_clean[2:].strip() if has_bullet_prefix else line_clean
        # Name comes from the first line only — DB rows can be multi-line
        # free text (continuation lines joined with "\n" by the migration
        # script), and without this the em-dash strip below can't reach
        # across the newline, leaving the whole blob as the "name".
        first_line = source_text.splitlines()[0] if source_text else ""
        name_text = _EXPECTED_RETURN_RE.sub("", first_line)
        name_text = _MUST_NOT_FORGET_RE.sub("", name_text)
        name_text = re.sub(r"\s*—\s*.*$", "", name_text)
        name = name_text.strip().rstrip(".")

    if not name:
        return None

    expected_ch: int | None = None
    exp_match = _EXPECTED_RETURN_RE.search(line_clean)
    if exp_match:
        expected_ch = int(exp_match.group(1))

    must_forget = bool(_MUST_NOT_FORGET_RE.search(line_clean))

    return CallbackEntry(
        name=name,
        search_terms=_extract_search_terms(name),
        expected_return_ch=expected_ch,
        must_not_forget=must_forget,
        raw_line=raw_line,
        from_db=from_db,
    )


def parse_callback_register(claudemd_text: str) -> list[CallbackEntry]:
    """Parse callback entries from a book's CLAUDE.md content.

    **Legacy path** — reads the ``<!-- CALLBACKS:START/END -->`` marker
    block, which ``append_book_callback()`` no longer writes to after the
    Phase 4 book_rules-DB migration (Issue #282). Kept for the one-time
    ``scripts/migrate_book_rules.py`` import path and for any pre-migration
    CLAUDE.md still carrying populated markers. Current callback data comes
    from ``_read_book_callbacks()`` below — see ``verify_callbacks()``.

    Returns an empty list if the ``## Callback Register`` section is absent
    or contains no bullet entries.
    """
    match = _CALLBACKS_SECTION_RE.search(claudemd_text)
    if not match:
        return []

    section = match.group(1)
    entries: list[CallbackEntry] = []

    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line.startswith("- "):
            continue
        entry = _parse_callback_body(line, has_bullet_prefix=True, raw_line=raw_line, from_db=False)
        if entry is not None:
            entries.append(entry)

    return entries


def _read_book_callbacks(book_path: Path) -> tuple[list[CallbackEntry], bool]:
    """Return (parsed callback entries, unreadable) for a book — reads the
    book_rules DB (sole source since the Phase 4 migration, Issue #282),
    mirroring ``tools/analysis/manuscript/rules.py``'s ``_read_book_rules()``.

    Returns ``([], False)`` when the book genuinely has no callbacks
    registered. Returns ``([], True)`` when the DB couldn't be read for an
    unexpected reason (sqlite corruption, permissions, ...) — the caller
    must not treat that the same as "zero callbacks, all accounted for"
    (Issue #584).

    Raises :class:`~tools.db.connection.BookNotLinkedToSeriesError` (Issue
    #579) rather than swallowing it into the generic ``True`` above — the
    caller (:func:`verify_callbacks`) catches it specifically to build an
    actionable reason from the exception's own message, same pattern as
    ``_read_book_rules()``/``_scan_book_rules()``.
    """
    from tools.db.connection import BookNotLinkedToSeriesError

    try:
        from tools.db.book_rules import list_rules as _db_list_rules
        from tools.db.connection import get_book_num, get_db_slug_for_book, open_canon_db

        db_slug = get_db_slug_for_book(book_path)
        book_num = get_book_num(book_path)
        conn = open_canon_db(db_slug)
        try:
            rows = _db_list_rules(conn, book_num=book_num, rule_type="callback")
        finally:
            conn.close()
    except BookNotLinkedToSeriesError:
        raise
    except Exception:
        logger.warning("callback DB read failed for %s", book_path.name, exc_info=True)
        return [], True

    entries: list[CallbackEntry] = []
    for row in rows:
        text = row["text"]
        entry = _parse_callback_body(text, has_bullet_prefix=False, raw_line=text, from_db=True)
        if entry is not None:
            entries.append(entry)
    return entries, False


def _chapter_number_from_path(chapter_dir: Path) -> int | None:
    """Extract chapter number from directory name like ``03-the-dark-night``."""
    m = re.match(r"^(\d+)", chapter_dir.name)
    return int(m.group(1)) if m else None


_term_pattern_cache: dict[str, re.Pattern[str]] = {}


def _term_pattern(term: str) -> re.Pattern[str]:
    pattern = _term_pattern_cache.get(term)
    if pattern is None:
        pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        _term_pattern_cache[term] = pattern
    return pattern


def _draft_contains_any(draft_path: Path, terms: list[str]) -> bool:
    """Return True if any search term appears as a whole word/phrase in the draft.

    Word-boundary matching, not substring — a plain ``term in text`` check
    would count "cat" as present inside "cathedral", or "red" inside
    "covered", turning short callback names into false "satisfied" results.
    """
    if not draft_path.exists():
        return False
    text = draft_path.read_text(encoding="utf-8", errors="ignore")
    return any(_term_pattern(term).search(text) for term in terms)


def _append_dropped_or_capped(entry: CallbackEntry, record: dict, dropped: list[dict], deferred: list[dict]) -> None:
    """Route a would-be ``potentially_dropped`` record — unless ``entry`` is
    legacy-marker-only, in which case it's capped at ``deferred`` (WARN, not
    FAIL) since the chapter-writer never had the DB row needed to service it.
    """
    if entry.from_db:
        dropped.append(record)
    else:
        deferred.append({**record, "registered_in_ch": None, "status": "legacy_marker_only_capped_at_warn"})


def verify_callbacks(book_path: Path, claudemd_text: str = "") -> dict:
    """Verify the callback register against all drafted chapters.

    Callback data is read from the book_rules DB (sole source of truth
    since the Phase 4 migration, Issue #282 — same source `append_book_callback()`
    writes to). ``claudemd_text``, if given, is parsed too for backward
    compatibility with any pre-migration CLAUDE.md still carrying populated
    ``<!-- CALLBACKS:START/END -->`` markers — those entries are merged in
    by name, DB entries taking precedence on a name collision. Passing an
    empty string (the default) or omitting a populated Callback Register
    section is fine; the DB read alone covers current usage.

    Legacy-marker-only entries (no corresponding DB row) can only ever reach
    ``deferred`` (WARN), never ``potentially_dropped`` (FAIL) — the writer
    briefs (``get_chapter_writing_brief``/``get_review_brief``) read the DB
    only, so a pre-migration book's marker-only callback is data the
    chapter-writer never had a chance to service, and a quality gate
    shouldn't silently block export over it.

    Args:
        book_path: Absolute path to the book project directory.
        claudemd_text: Optional contents of the book's CLAUDE.md, for the
            legacy marker-block fallback described above.

    Returns:
        dict with keys: book_slug, callbacks_checked, satisfied,
        deferred, potentially_dropped, unreadable, unreadable_reason.
        ``unreadable: True`` (Issue #584) means the DB read itself failed
        (e.g. an unlinked series book, Issue #579's
        ``BookNotLinkedToSeriesError``, whose message lands in
        ``unreadable_reason``; other causes leave it empty) — the DB-sourced
        entries are missing in that case, but this function still falls back
        to any legacy ``<!-- CALLBACKS:START -->`` markers in
        ``claudemd_text`` (pre-migration books), so ``callbacks_checked`` and
        the three buckets can still be nonzero. ``unreadable: True`` means
        "the DB portion couldn't be verified", not "nothing was checked at
        all" — callers must not read a low/zero count here as a clean bill
        of health.
    """
    from tools.db.connection import BookNotLinkedToSeriesError

    unreadable_reason = ""
    try:
        db_entries, callbacks_unreadable = _read_book_callbacks(book_path)
    except BookNotLinkedToSeriesError as exc:
        db_entries = []
        callbacks_unreadable = True
        unreadable_reason = str(exc)
    known_names = {e.name.lower() for e in db_entries}
    legacy_entries = (
        [e for e in parse_callback_register(claudemd_text) if e.name.lower() not in known_names]
        if claudemd_text
        else []
    )
    entries = db_entries + legacy_entries

    # Collect drafted chapters sorted by chapter number
    chapters_dir = book_path / "chapters"
    drafted: list[tuple[int, Path]] = []
    if chapters_dir.exists():
        for ch_dir in sorted(chapters_dir.iterdir()):
            if not ch_dir.is_dir():
                continue
            draft = ch_dir / "draft.md"
            if not draft.exists():
                continue
            ch_num = _chapter_number_from_path(ch_dir)
            if ch_num is not None:
                drafted.append((ch_num, draft))

    drafted.sort(key=lambda x: x[0])
    total_drafted = len(drafted)
    max_chapter = drafted[-1][0] if drafted else 0

    satisfied: list[dict] = []
    deferred: list[dict] = []
    potentially_dropped: list[dict] = []

    for entry in entries:
        appears_in: list[int] = [ch_num for ch_num, draft in drafted if _draft_contains_any(draft, entry.search_terms)]

        last_ch = appears_in[-1] if appears_in else None

        # Chapters of silence = gap between last appearance and current max
        chapters_silent = (max_chapter - last_ch) if last_ch is not None else max_chapter

        base: dict = {
            "name": entry.name,
            "appears_in": appears_in,
            "last_appeared_ch": last_ch,
        }
        if entry.expected_return_ch is not None:
            base["expected_return_ch"] = entry.expected_return_ch

        # Overdue: expected_return_ch has passed and callback never appeared
        # in or after that chapter
        is_overdue = (
            entry.expected_return_ch is not None
            and max_chapter >= entry.expected_return_ch
            and not any(ch >= entry.expected_return_ch for ch in appears_in)
        )

        if is_overdue:
            warning = (
                f"expected return by Ch {entry.expected_return_ch}"
                f" — {'never appeared' if not appears_in else f'last seen Ch {last_ch}, deadline passed'}"
            )
            _append_dropped_or_capped(
                entry,
                {**base, "chapters_since": chapters_silent, "warning": warning},
                potentially_dropped,
                deferred,
            )
        elif not appears_in:
            # Never appeared at all
            deferred.append(
                {
                    **base,
                    "registered_in_ch": None,
                    "chapters_since": total_drafted,
                    "status": "pending",
                }
            )
        elif chapters_silent > _SILENCE_THRESHOLD and entry.must_not_forget:
            warning = f"register entry says 'must not be forgotten' — {chapters_silent} chapters of silence"
            _append_dropped_or_capped(
                entry,
                {**base, "chapters_since": chapters_silent, "warning": warning},
                potentially_dropped,
                deferred,
            )
        elif chapters_silent > _SILENCE_THRESHOLD:
            deferred.append(
                {
                    **base,
                    "registered_in_ch": None,
                    "chapters_since": chapters_silent,
                    "status": "long_silence",
                }
            )
        else:
            satisfied.append(base)

    return {
        "book_slug": book_path.name,
        "callbacks_checked": len(entries),
        "satisfied": satisfied,
        "deferred": deferred,
        "potentially_dropped": potentially_dropped,
        "unreadable": callbacks_unreadable,
        "unreadable_reason": unreadable_reason,
    }
