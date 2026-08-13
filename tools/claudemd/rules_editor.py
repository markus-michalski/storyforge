"""Edit existing rules in the book_rules DB — Issue #282.

Phase 4 migration: rules, callbacks, and workflow instructions moved from
CLAUDE.md HTML-marker blocks to the book_rules SQLite table.

The module exposes:

- ``list_rules(config, book_slug)`` — returns ``ParsedRule`` objects from DB
  with index (0-based position), rule_id (DB pk), title, raw_text, and
  pattern-extraction flags.
- ``update_rule(config, book_slug, *, rule_index, rule_match, new_text,
  delete, validate)`` — replaces or removes a rule in the DB. Identifier
  resolution uses the same positional-index / title-match semantics as
  before, backed by DB ids rather than file offsets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from tools.analysis.manuscript.rules import _extract_patterns_from_rule
from tools.claudemd.manager import _open_book_db
from tools.db.book_rules import delete_rule, list_rules as _db_list_rules, update_rule_text
from tools.shared.paths import resolve_project_path


# ---------------------------------------------------------------------------
# Errors  (kept for backward compat — MarkersNotFoundError no longer raised)
# ---------------------------------------------------------------------------


class RulesError(Exception):
    """Base class for rule-editor errors."""


class MarkersNotFoundError(RulesError):
    """Kept for backward compatibility — no longer raised after Phase 4."""


class RuleNotFoundError(RulesError):
    """The requested rule does not exist (signaled via ``found: False``)."""


class AmbiguousMatchError(RulesError):
    """``rule_match`` resolved to more than one rule."""


class DisagreeingResolutionError(RulesError):
    """``rule_index`` and ``rule_match`` resolved to different rules."""


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


_TITLE_RE = re.compile(r"^\*\*(?P<title>[^*]+)\*\*")
_REGEX_HINT_CHARS = set("|()[]\\^$?+*{}")
_BACKTICK_CONTENT_RE = re.compile(r"`([^`\n]+)`")


@dataclass
class ParsedRule:
    index: int
    title: str
    raw_text: str
    rule_id: int = -1
    has_regex: bool = False
    has_literals: bool = False
    extracted_patterns: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rule_title(raw_text: str, max_len: int = 80) -> str:
    bold = _TITLE_RE.match(raw_text)
    if bold:
        return bold.group("title").strip()
    title = re.sub(r"\s+", " ", raw_text).strip()
    if len(title) > max_len:
        title = title[: max_len - 1].rstrip() + "…"
    return title


def _build_parsed_rule(index: int, db_row: dict) -> ParsedRule:
    raw_text = db_row["text"]
    title = _rule_title(raw_text)
    patterns = _extract_patterns_from_rule(raw_text)
    has_regex = False
    has_literals = False
    extracted: list[dict[str, Any]] = []
    for label, compiled in patterns:
        is_regex = compiled.pattern != re.escape(label)
        if is_regex:
            has_regex = True
        else:
            has_literals = True
        extracted.append(
            {"label": label, "pattern": compiled.pattern, "is_regex": is_regex}
        )
    for m in _BACKTICK_CONTENT_RE.finditer(raw_text):
        inner = m.group(1).strip()
        if any(c in _REGEX_HINT_CHARS for c in inner):
            has_regex = True
    return ParsedRule(
        index=index,
        title=title,
        raw_text=raw_text,
        rule_id=db_row["id"],
        has_regex=has_regex,
        has_literals=has_literals,
        extracted_patterns=extracted,
    )


# ---------------------------------------------------------------------------
# Public: list
# ---------------------------------------------------------------------------


def list_rules(config: dict[str, Any], book_slug: str) -> list[ParsedRule]:
    """Return parsed rules from the book_rules DB for this book.

    Returns an empty list when no rules exist (no error) — including books
    that exist but haven't run init_book_claudemd() yet, since rules live in
    the book_rules DB table independent of the CLAUDE.md file (Phase 4
    migration, Issue #282; graceful-degradation fix Issue #573). Raises
    FileNotFoundError only if the book project itself doesn't exist.
    """
    book_root = resolve_project_path(config, book_slug)
    if not book_root.is_dir():
        raise FileNotFoundError(f"Book '{book_slug}' not found: {book_root}")

    conn, book_num = _open_book_db(config, book_slug)
    try:
        rows = _db_list_rules(conn, book_num=book_num, rule_type="rule")
    finally:
        conn.close()

    return [_build_parsed_rule(i, row) for i, row in enumerate(rows)]


# ---------------------------------------------------------------------------
# Public: update
# ---------------------------------------------------------------------------


def update_rule(
    config: dict[str, Any],
    book_slug: str,
    *,
    rule_index: int | None = None,
    rule_match: str | None = None,
    new_text: str | None = None,
    delete: bool = False,
    validate: bool = True,
) -> dict[str, Any]:
    """Replace or remove a rule in the book_rules DB.

    Returns a result dict; on a ``found: False`` outcome the DB is unchanged.

    Does not require CLAUDE.md to exist (Issue #580) — rules live in the
    book_rules DB independent of the file (Phase 4 migration, Issue #282),
    same as ``list_rules()`` (Issue #573), which this delegates to below and
    which already raises ``FileNotFoundError`` if the book project itself
    doesn't exist. A book missing CLAUDE.md simply has no rules to find,
    same as any other book with an empty book_rules table — ``found: False``,
    not an error.

    This relies on ``get_book_num()``'s ``BookNotLinkedToSeriesError`` guard
    (Issue #579) to keep an uninitialized series book from silently
    "inheriting" a different book's rows via a ``book_num`` collision — but
    that guard only closes the ``series_number: 0`` scaffold-default window.
    Two related collision paths are NOT closed by it and affect
    ``list_rules()``/``update_rule()`` identically, guard or no guard:
    ``add_book_to_series()`` performs no uniqueness check on ``number``, so
    two books in one series can end up sharing a ``book_num`` via a
    duplicate/typo'd call; and a book with ``series`` set but no
    ``series_number`` key at all (never written) still defaults to 1,
    same as the pre-existing Issue #558 case. Both are tracked in a
    follow-up (see Issue #579's own suggested fix: key ``book_rules`` by
    ``book_slug`` directly, mirroring the ``cover_images`` fix from #558) —
    removing this guard here does not make either worse, since
    ``list_rules()`` was already equally exposed since #573 shipped.
    """
    _validate_args(rule_index, rule_match, new_text, delete)

    rules = list_rules(config, book_slug)

    target_index = _resolve_target_index(rules, rule_index, rule_match)
    if target_index is None:
        return {
            "found": False,
            "changed": False,
            "rule_index": -1,
            "old_text": "",
            "new_text": "",
            "warnings": [],
            "extracted_patterns": [],
        }

    rule = rules[target_index]
    old_text = rule.raw_text

    conn, _ = _open_book_db(config, book_slug)
    try:
        if delete:
            delete_rule(conn, rule.rule_id)
            result_new_text = ""
        else:
            assert new_text is not None
            cleaned = _normalize_new_text(new_text)
            if cleaned == old_text:
                return {
                    "found": True,
                    "changed": False,
                    "rule_index": target_index,
                    "old_text": old_text,
                    "new_text": old_text,
                    "warnings": _maybe_lint(old_text, validate),
                    "extracted_patterns": _extracted_patterns_for(old_text),
                }
            update_rule_text(conn, rule.rule_id, cleaned)
            result_new_text = cleaned
    finally:
        conn.close()

    return {
        "found": True,
        "changed": True,
        "rule_index": target_index,
        "old_text": old_text,
        "new_text": result_new_text,
        "warnings": _maybe_lint(result_new_text, validate) if not delete else [],
        "extracted_patterns": _extracted_patterns_for(result_new_text) if not delete else [],
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _validate_args(
    rule_index: int | None,
    rule_match: str | None,
    new_text: str | None,
    delete: bool,
) -> None:
    if rule_index is None and rule_match is None:
        raise ValueError("Either rule_index or rule_match must be provided")
    if rule_index is not None and rule_index < 0:
        raise ValueError("rule_index must be >= 0")
    if delete and new_text is not None:
        raise ValueError("delete=True and new_text are mutually exclusive")
    if not delete and new_text is None:
        raise ValueError("new_text is required when delete=False")
    if new_text is not None and not new_text.strip():
        raise ValueError("new_text must not be empty")


def _normalize_new_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _resolve_target_index(
    rules: list[ParsedRule],
    rule_index: int | None,
    rule_match: str | None,
) -> int | None:
    """Resolve to a single rule index, or ``None`` if not found."""
    by_index = None
    by_match = None

    if rule_index is not None:
        if 0 <= rule_index < len(rules):
            by_index = rule_index

    if rule_match is not None:
        match_indices = _match_indices(rules, rule_match)
        if len(match_indices) > 1:
            titles = [rules[i].title for i in match_indices]
            raise AmbiguousMatchError(
                f"rule_match '{rule_match}' matches {len(match_indices)} rules: "
                f"{titles}"
            )
        if match_indices:
            by_match = match_indices[0]

    if by_index is not None and by_match is not None:
        if by_index != by_match:
            raise DisagreeingResolutionError(
                f"rule_index={by_index} and rule_match='{rule_match}' "
                f"(index={by_match}) point to different rules"
            )
        return by_index
    if by_index is not None:
        return by_index
    if by_match is not None:
        return by_match
    return None


def _match_indices(rules: list[ParsedRule], needle: str) -> list[int]:
    needle_lower = needle.lower().strip()
    if not needle_lower:
        return []

    title_hits = [r.index for r in rules if needle_lower in r.title.lower()]
    if title_hits:
        return title_hits

    return [r.index for r in rules if needle_lower in r.raw_text.lower()]


def _maybe_lint(rule_text: str, validate: bool) -> list[dict[str, Any]]:
    if not validate or not rule_text:
        return []
    from tools.claudemd.rules_lint import lint_rule_text
    return lint_rule_text(rule_text)["warnings"]


def _extracted_patterns_for(rule_text: str) -> list[dict[str, Any]]:
    if not rule_text:
        return []
    from tools.claudemd.rules_lint import lint_rule_text
    return lint_rule_text(rule_text)["extracted_patterns"]


__all__ = [
    "AmbiguousMatchError",
    "DisagreeingResolutionError",
    "MarkersNotFoundError",
    "ParsedRule",
    "RuleNotFoundError",
    "RulesError",
    "list_rules",
    "update_rule",
]
