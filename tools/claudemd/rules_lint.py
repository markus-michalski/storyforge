"""Lint rules in a book's CLAUDE.md against the manuscript-checker contract.

Issue #145 — surfaces rules that the scanner will silently ignore or
misinterpret. The single-rule linter (``lint_rule_text``) is shared by
``update_book_rule(validate=True)`` and ``lint_book_rules`` so warnings
are consistent across both call paths.

Warning codes:

- ``bracket_placeholder`` — backtick-wrapped content that contains
  word-shaped ``[X]`` placeholders that look like character classes but are
  almost certainly meant as ``\\w+``-style placeholders. Common typos:
  ``[noun]``, ``[verb]``, ``[subj]``.
- ``italic_examples_with_ban_cue`` — rule has a ban cue and italics
  containing quoted phrases. Italics are ignored by the scanner; the
  examples are silently invisible.
- ``mixed_positive_negative_quotes`` — rule has a ban cue and *multiple*
  quoted phrases. The scanner extracts every quoted phrase as a banned
  pattern, so positive rewrite examples (``replace with "X"``) get
  flagged as bans too.
- ``scanner_extracts_nothing`` — rule has a ban cue but no extractable
  pattern (no backticks, no quoted phrases). The scanner sees nothing.
"""

from __future__ import annotations

import re
from typing import Any

from tools.analysis.manuscript.rules import _extract_patterns_from_rule
from tools.claudemd.rules_editor import list_rules

LINT_BRACKET_PLACEHOLDER = "bracket_placeholder"
LINT_ITALIC_EXAMPLES_WITH_BAN_CUE = "italic_examples_with_ban_cue"
LINT_MIXED_POSITIVE_NEGATIVE_QUOTES = "mixed_positive_negative_quotes"
LINT_SCANNER_EXTRACTS_NOTHING = "scanner_extracts_nothing"


_BACKTICK_CONTENT_RE = re.compile(r"`([^`\n]+)`")
_QUOTED_CONTENT_RE = re.compile(r'"([^"\n]{3,})"')
_ITALIC_QUOTED_RE = re.compile(r'\*"[^"\n]+"\*')
_BAN_CUE_RE = re.compile(
    r"\b(banned|ban|avoid|never|don[’']?t\s+use|do\s+not\s+use|limit|"
    r"no\s+\w+|stop\s+using)\b",
    re.IGNORECASE,
)
# Inside a backtick body: a [WORD] token (alphabetic, length 2-12).
# Real character classes use ranges (``[a-z]``), shorter shorthand
# (``[A-Z0-9]``), or POSIX-style. ``[noun]`` / ``[verb]`` / ``[subj]``
# are the typo pattern that motivated this lint.
_WORDLIKE_BRACKET_RE = re.compile(r"\[([a-z]{2,12})\]", re.IGNORECASE)


def lint_rule_text(rule_text: str) -> dict[str, Any]:
    """Run the four lint checks on a single rule body.

    Returns ``{"warnings": [...], "extracted_patterns": [...]}``. Each
    warning has shape ``{"code": str, "message": str, "hint": str}``.
    """
    warnings: list[dict[str, str]] = []
    has_ban_cue = bool(_BAN_CUE_RE.search(rule_text))

    warnings.extend(_check_bracket_placeholders(rule_text))

    if has_ban_cue:
        if _ITALIC_QUOTED_RE.search(rule_text):
            warnings.append(
                {
                    "code": LINT_ITALIC_EXAMPLES_WITH_BAN_CUE,
                    "message": (
                        "Italic-wrapped quoted examples are invisible to the "
                        "manuscript-checker scanner."
                    ),
                    "hint": (
                        "Wrap the banned phrases in backticks (``foo``) "
                        "instead of italics (*\"foo\"*) so the scanner "
                        "extracts them."
                    ),
                }
            )

        quoted = _QUOTED_CONTENT_RE.findall(rule_text)
        if len(quoted) >= 2:
            warnings.append(
                {
                    "code": LINT_MIXED_POSITIVE_NEGATIVE_QUOTES,
                    "message": (
                        "Multiple double-quoted phrases combined with a ban "
                        "cue: every quoted phrase is extracted as a banned "
                        "pattern, so positive rewrite examples will be "
                        "wrongly flagged as bans."
                    ),
                    "hint": (
                        "Put banned phrases in backticks and positive "
                        "examples in italics (or move them out of the rule "
                        "body)."
                    ),
                }
            )

    extracted = _extracted_patterns(rule_text)

    if has_ban_cue and not extracted:
        warnings.append(
            {
                "code": LINT_SCANNER_EXTRACTS_NOTHING,
                "message": (
                    "Rule has a ban cue but no extractable pattern — the "
                    "scanner will see nothing and the rule won't enforce."
                ),
                "hint": (
                    "Add the banned phrase in backticks (``foo``) or in "
                    "double quotes (\"foo\")."
                ),
            }
        )

    return {"warnings": warnings, "extracted_patterns": extracted}


def lint_book_rules(config: dict[str, Any], book_slug: str) -> dict[str, Any]:
    """Run ``lint_rule_text`` over every rule in a book's RULES block.

    Returns ``{"rules_total": N, "issues": [{rule_index, title, warnings,
    extracted_patterns}, ...]}``. Only rules with at least one warning
    appear in ``issues``.
    """
    rules = list_rules(config, book_slug)
    issues: list[dict[str, Any]] = []
    for rule in rules:
        result = lint_rule_text(rule.raw_text)
        if result["warnings"]:
            issues.append(
                {
                    "rule_index": rule.index,
                    "title": rule.title,
                    "warnings": result["warnings"],
                    "extracted_patterns": result["extracted_patterns"],
                }
            )
    return {"rules_total": len(rules), "issues": issues}


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _check_bracket_placeholders(rule_text: str) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for m in _BACKTICK_CONTENT_RE.finditer(rule_text):
        body = m.group(1)
        for bracket in _WORDLIKE_BRACKET_RE.finditer(body):
            placeholder = bracket.group(0)
            warnings.append(
                {
                    "code": LINT_BRACKET_PLACEHOLDER,
                    "message": (
                        f"Backtick body contains {placeholder}, which is a "
                        f"character class — the scanner reads it literally, "
                        f"not as a placeholder."
                    ),
                    "hint": (
                        "If you meant a placeholder, use \\w+ inside the "
                        "backticks; if you meant a literal character "
                        "class, the rule will only match those exact "
                        "letters."
                    ),
                }
            )
            break  # one warning per backtick body is enough
    return warnings


def _extracted_patterns(rule_text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for label, compiled in _extract_patterns_from_rule(rule_text):
        is_regex = compiled.pattern != re.escape(label)
        out.append(
            {"label": label, "pattern": compiled.pattern, "is_regex": is_regex}
        )
    return out


__all__ = [
    "LINT_BRACKET_PLACEHOLDER",
    "LINT_ITALIC_EXAMPLES_WITH_BAN_CUE",
    "LINT_MIXED_POSITIVE_NEGATIVE_QUOTES",
    "LINT_SCANNER_EXTRACTS_NOTHING",
    "lint_book_rules",
    "lint_rule_text",
]
