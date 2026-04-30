"""Edit existing rules in a book's CLAUDE.md.

Issue #145 — companion to ``append_rule`` in ``manager.py``. Operates only on
the bullets between ``<!-- RULES:START -->`` and ``<!-- RULES:END -->``;
any static rules above the marker block are intentionally invisible to the
editor (they're template boilerplate, not user-managed entries).

The module exposes:

- ``list_rules(config, book_slug)`` — returns ``ParsedRule`` objects with
  index, title, raw_text, and pattern-extraction flags.
- ``update_rule(config, book_slug, *, rule_index, rule_match, new_text,
  delete, validate)`` — replaces or removes a rule. Identifier resolution
  prefers ``rule_match`` (against bold title, falling back to body
  substring); ``rule_index`` is the unambiguous fallback for refactor
  scripts. When both are given they must agree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from tools.analysis.manuscript.rules import _extract_patterns_from_rule
from tools.claudemd.manager import resolve_claudemd_path
from tools.claudemd.parser import SECTION_MARKERS

START_MARKER, END_MARKER = SECTION_MARKERS["rule"]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RulesError(Exception):
    """Base class for rule-editor errors."""


class MarkersNotFoundError(RulesError):
    """The CLAUDE.md is missing the RULES START/END markers."""


class RuleNotFoundError(RulesError):
    """The requested rule does not exist (signaled via ``found: False``)."""


class AmbiguousMatchError(RulesError):
    """``rule_match`` resolved to more than one rule."""


class DisagreeingResolutionError(RulesError):
    """``rule_index`` and ``rule_match`` resolved to different rules."""


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class ParsedRule:
    index: int
    title: str
    raw_text: str
    has_regex: bool = False
    has_literals: bool = False
    extracted_patterns: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


_TITLE_RE = re.compile(r"^\*\*(?P<title>[^*]+)\*\*")
_REGEX_HINT_CHARS = set("|()[]\\^$?+*{}")
_BACKTICK_CONTENT_RE = re.compile(r"`([^`\n]+)`")


def _extract_block(content: str) -> tuple[str, int, int]:
    """Return ``(block_text, start_offset, end_offset)`` for the inner
    RULES block (between, but excluding, the marker lines).

    Raises ``MarkersNotFoundError`` when either marker is missing.
    """
    start = content.find(START_MARKER)
    end = content.find(END_MARKER)
    if start == -1 or end == -1 or end <= start:
        raise MarkersNotFoundError(
            f"RULES markers missing or malformed (looking for "
            f"{START_MARKER!r} and {END_MARKER!r})"
        )
    inner_start = start + len(START_MARKER)
    # Skip a single trailing newline after the start marker so the inner
    # block doesn't accidentally include it.
    if content[inner_start : inner_start + 1] == "\n":
        inner_start += 1
    return content[inner_start:end], inner_start, end


def _parse_bullets(block_text: str) -> list[str]:
    """Split a RULES block body into bullet bodies.

    A bullet starts at a line beginning with ``- ``. Continuation lines
    (indented or non-list lines) are folded into the previous bullet.
    Comment lines (``<!-- ... -->``) and blank lines act as separators.
    Returns the bullet *bodies* (without the leading ``- ``).
    """
    bullets: list[list[str]] = []
    current: list[str] | None = None

    for raw_line in block_text.splitlines():
        line = raw_line.rstrip("\n")
        if line.lstrip().startswith("<!--"):
            if current is not None:
                bullets.append(current)
                current = None
            continue
        if not line.strip():
            if current is not None:
                bullets.append(current)
                current = None
            continue
        if line.startswith("- "):
            if current is not None:
                bullets.append(current)
            current = [line[2:].rstrip()]
        else:
            if current is not None:
                current.append(line.strip())
            # Lines without a current bullet (orphans) are ignored.

    if current is not None:
        bullets.append(current)

    return [_join_bullet_lines(parts) for parts in bullets]


def _join_bullet_lines(parts: list[str]) -> str:
    """Join multi-line bullet parts with single spaces (preserves text)."""
    return " ".join(p for p in parts if p)


def _build_parsed_rule(index: int, raw_text: str) -> ParsedRule:
    title = _rule_title(raw_text)
    patterns = _extract_patterns_from_rule(raw_text)
    has_regex = False
    has_literals = False
    extracted: list[dict[str, Any]] = []
    for label, compiled in patterns:
        # Heuristic: the extractor escaped literal substrings. If the
        # compiled pattern equals the escape of its label, it's a literal.
        is_regex = compiled.pattern != re.escape(label)
        if is_regex:
            has_regex = True
        else:
            has_literals = True
        extracted.append(
            {"label": label, "pattern": compiled.pattern, "is_regex": is_regex}
        )
    # An additional check: explicit regex hint chars in any backtick body.
    for m in _BACKTICK_CONTENT_RE.finditer(raw_text):
        inner = m.group(1).strip()
        if any(c in _REGEX_HINT_CHARS for c in inner):
            has_regex = True
    return ParsedRule(
        index=index,
        title=title,
        raw_text=raw_text,
        has_regex=has_regex,
        has_literals=has_literals,
        extracted_patterns=extracted,
    )


def _rule_title(raw_text: str, max_len: int = 80) -> str:
    bold = _TITLE_RE.match(raw_text)
    if bold:
        return bold.group("title").strip()
    title = re.sub(r"\s+", " ", raw_text).strip()
    if len(title) > max_len:
        title = title[: max_len - 1].rstrip() + "…"
    return title


# ---------------------------------------------------------------------------
# Public: list
# ---------------------------------------------------------------------------


def list_rules(config: dict[str, Any], book_slug: str) -> list[ParsedRule]:
    """Return the parsed rules from the RULES block in a book's CLAUDE.md.

    Raises ``MarkersNotFoundError`` if the markers are missing.
    """
    path = resolve_claudemd_path(config, book_slug)
    if not path.exists():
        raise FileNotFoundError(f"CLAUDE.md not found for book '{book_slug}'")
    content = path.read_text(encoding="utf-8")
    block_text, _, _ = _extract_block(content)
    bodies = _parse_bullets(block_text)
    return [_build_parsed_rule(i, body) for i, body in enumerate(bodies)]


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
    """Replace or remove a single rule in the book's RULES block.

    Returns a result dict; on a ``found: False`` outcome the file is left
    unchanged.

    Validation:
    - At least one of ``rule_index`` or ``rule_match`` must be provided.
    - ``delete=True`` and ``new_text`` are mutually exclusive.
    - When neither delete nor new_text is given, ``ValueError`` is raised.
    - ``new_text`` must be non-empty after ``strip()``.
    - ``rule_index`` must be ``>= 0``.
    """
    _validate_args(rule_index, rule_match, new_text, delete)

    path = resolve_claudemd_path(config, book_slug)
    if not path.exists():
        raise FileNotFoundError(f"CLAUDE.md not found for book '{book_slug}'")
    content = path.read_text(encoding="utf-8")
    block_text, inner_start, inner_end = _extract_block(content)
    bodies = _parse_bullets(block_text)
    rules = [_build_parsed_rule(i, b) for i, b in enumerate(bodies)]

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

    old_text = bodies[target_index]

    if delete:
        new_bodies = bodies[:target_index] + bodies[target_index + 1 :]
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
        new_bodies = list(bodies)
        new_bodies[target_index] = cleaned
        result_new_text = cleaned

    new_block = _serialize_block(new_bodies)
    new_content = content[:inner_start] + new_block + content[inner_end:]
    path.write_text(new_content, encoding="utf-8")

    return {
        "found": True,
        "changed": True,
        "rule_index": target_index,
        "old_text": old_text,
        "new_text": result_new_text,
        "warnings": _maybe_lint(result_new_text, validate) if not delete else [],
        "extracted_patterns": _extracted_patterns_for(result_new_text)
        if not delete
        else [],
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
    """Resolve to a single rule index, or ``None`` if not found.

    Raises ``AmbiguousMatchError`` or ``DisagreeingResolutionError``.
    """
    by_index = None
    by_match = None

    if rule_index is not None:
        if 0 <= rule_index < len(rules):
            by_index = rule_index
        # Out-of-range index -> resolve to None (handled by caller).

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

    title_hits = [
        r.index for r in rules if needle_lower in r.title.lower()
    ]
    if title_hits:
        return title_hits

    body_hits = [
        r.index for r in rules if needle_lower in r.raw_text.lower()
    ]
    return body_hits


def _serialize_block(bodies: list[str]) -> str:
    """Render the inner block text given a list of bullet bodies.

    Always starts with a newline and ends with a newline so the marker line
    that follows is on its own line. An empty list collapses to a single
    blank line so the markers stay adjacent.
    """
    if not bodies:
        return ""
    return "\n".join(f"- {b}" for b in bodies) + "\n"


def _maybe_lint(rule_text: str, validate: bool) -> list[dict[str, Any]]:
    if not validate or not rule_text:
        return []
    # Imported lazily so the editor doesn't hard-depend on the lint module.
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
