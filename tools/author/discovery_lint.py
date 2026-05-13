"""Section-aware lint for author-profile ``## Writing Discoveries`` writes
(Issue #218).

Mirrors :func:`tools.claudemd.rules_lint.lint_rule_text` but applies the
inverted semantics of author Don'ts (italics with a ban cue ARE the
canonical encoding of bannable phrases) and the title-fallback semantics
of Recurring Tics (bold title may carry the scannable phrase or fall back
to body extraction / title text).

Section-specific behavior:

- ``donts`` — four lint codes mirror the book-rule lint:
  ``mixed_positive_negative_italics`` (new — italics on both sides of a
  recommendation marker), ``mixed_positive_negative_quotes`` (reused),
  ``scanner_extracts_nothing`` (reused), ``bracket_placeholder`` (reused).
  ``extracted_patterns`` is the output of
  :func:`tools.analysis.manuscript.rules._extract_patterns_from_author_dont`
  so the displayed list matches what the scanner will actually use.
- ``recurring_tics`` — ``bold_title_unscannable`` (new — non-English title
  with no body pattern) and ``bracket_placeholder``. ``extracted_patterns``
  mirrors the Recurring-Tic loader's title → body → title-text fallback
  cascade.
- ``style_principles`` — only ``bracket_placeholder``. Style Principles
  are intentionally not machine-scanned; the lint must not warn about
  scanner gaps. ``extracted_patterns`` is always empty.
"""

from __future__ import annotations

import re
from typing import Any

from tools.analysis.manuscript.rules import (
    _BAN_CUE_RE,
    _ITALIC_CONTENT_RE,
    _RECOMMENDATION_MARKER_RE,
    _extract_patterns_from_author_dont,
)
from tools.banlist_loader import (
    _build_discovery_pattern,
    _extract_patterns_from_tic_body,
    _extract_phrases_from_bold_title,
    _strip_parenthetical,
    _title_inner_quotes,
)

# ---------------------------------------------------------------------------
# Lint codes
# ---------------------------------------------------------------------------

LINT_BRACKET_PLACEHOLDER = "bracket_placeholder"
LINT_MIXED_POSITIVE_NEGATIVE_ITALICS = "mixed_positive_negative_italics"
LINT_MIXED_POSITIVE_NEGATIVE_QUOTES = "mixed_positive_negative_quotes"
LINT_SCANNER_EXTRACTS_NOTHING = "scanner_extracts_nothing"
LINT_BOLD_TITLE_UNSCANNABLE = "bold_title_unscannable"

VALID_SECTIONS: tuple[str, ...] = ("recurring_tics", "style_principles", "donts")

# ---------------------------------------------------------------------------
# Internal patterns
# ---------------------------------------------------------------------------

_BACKTICK_CONTENT_RE = re.compile(r"`([^`\n]+)`")
_QUOTED_CONTENT_RE = re.compile(r'"([^"\n]{3,})"')
_WORDLIKE_BRACKET_RE = re.compile(r"\[([a-z]{2,12})\]", re.IGNORECASE)

# Bold-title detection — same shape the loader uses.
_BOLD_TITLE_RE = re.compile(r"^-?\s*\*\*(?P<inner>[^*]+)\*\*", re.MULTILINE)
_NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def lint_author_discovery(section: str, text: str) -> dict[str, Any]:
    """Run section-appropriate lint checks on a single discovery entry.

    Args:
        section: One of ``recurring_tics``, ``style_principles``, ``donts``.
        text: The full bullet body as the harvest skill would write it,
            e.g. ``**Never use rooms** — *The room received it.*``.

    Returns:
        ``{"warnings": [...], "extracted_patterns": [...]}`` matching the
        contract of :func:`tools.claudemd.rules_lint.lint_rule_text`. Each
        warning has shape ``{"code": str, "message": str, "hint": str}``;
        each extracted pattern has shape
        ``{"label": str, "pattern": str, "is_regex": bool}``.

    Raises:
        ValueError: ``section`` is not in :data:`VALID_SECTIONS`.
    """
    if section not in VALID_SECTIONS:
        raise ValueError(f"Invalid section: {section!r}. Valid: {VALID_SECTIONS}")

    if section == "donts":
        return _lint_donts(text)
    if section == "recurring_tics":
        return _lint_recurring_tics(text)
    return _lint_style_principles(text)


# ---------------------------------------------------------------------------
# Don'ts
# ---------------------------------------------------------------------------


def _lint_donts(text: str) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    has_ban_cue = bool(_BAN_CUE_RE.search(text))

    warnings.extend(_check_bracket_placeholders(text))

    if has_ban_cue:
        # Multiple italic phrases AND a recommendation marker: after #217 the
        # post-marker italics silently do NOT extract. Flag the asymmetry so
        # the user can verify which italics were meant as bans.
        italics = [m.group(1) for m in _ITALIC_CONTENT_RE.finditer(text)]
        marker = _RECOMMENDATION_MARKER_RE.search(
            _ITALIC_CONTENT_RE.sub(lambda m: " " * len(m.group(0)), text)
        )
        if len(italics) >= 2 and marker is not None:
            # Confirm at least one italic on each side of the marker so the
            # warning is actually meaningful (not just two italics that all
            # land before the marker).
            italic_positions = [m.start() for m in _ITALIC_CONTENT_RE.finditer(text)]
            before = sum(1 for p in italic_positions if p < marker.start())
            after = len(italic_positions) - before
            if before >= 1 and after >= 1:
                warnings.append(
                    {
                        "code": LINT_MIXED_POSITIVE_NEGATIVE_ITALICS,
                        "message": (
                            "Italic phrases on both sides of a recommendation "
                            "marker. Italics after the marker silently do "
                            "NOT extract as banned patterns — only italics "
                            "before the marker scan."
                        ),
                        "hint": (
                            "Verify the post-marker italics are recommendations, "
                            "not additional bans. If they ARE bans, move them "
                            "before the marker or use backticks (`...`) which "
                            "extract regardless of position."
                        ),
                    }
                )

        quoted = _QUOTED_CONTENT_RE.findall(text)
        if len(quoted) >= 2:
            warnings.append(
                {
                    "code": LINT_MIXED_POSITIVE_NEGATIVE_QUOTES,
                    "message": (
                        "Multiple double-quoted phrases combined with a ban "
                        "cue: every quoted phrase before any recommendation "
                        "marker is extracted as a banned pattern."
                    ),
                    "hint": (
                        "If one of these is a positive rewrite example, move "
                        "it after a recommendation marker (Render / Instead: "
                        "/ →) or upgrade banned phrases to backticks (`...`)."
                    ),
                }
            )

    extracted = _extracted_patterns_from_donts(text)

    if has_ban_cue and not extracted:
        warnings.append(
            {
                "code": LINT_SCANNER_EXTRACTS_NOTHING,
                "message": (
                    "Bullet has a ban cue but no extractable pattern — the "
                    "scanner will see nothing and the Don't won't enforce."
                ),
                "hint": (
                    "Add the banned phrase in italics (*phrase.*), double-"
                    "quotes (\"phrase\"), or — for explicit regex — backticks "
                    "(`\\bphrase\\b`) so the scanner can extract it."
                ),
            }
        )

    return {"warnings": warnings, "extracted_patterns": extracted}


def _extracted_patterns_from_donts(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for label, compiled in _extract_patterns_from_author_dont(text):
        is_regex = compiled.pattern != re.escape(label)
        out.append(
            {"label": label, "pattern": compiled.pattern, "is_regex": is_regex}
        )
    return out


# ---------------------------------------------------------------------------
# Recurring Tics
# ---------------------------------------------------------------------------


def _lint_recurring_tics(text: str) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    warnings.extend(_check_bracket_placeholders(text))

    bold = _BOLD_TITLE_RE.search(text)
    title_text = bold.group("inner").strip() if bold else ""
    bold_title = f"**{title_text}**" if title_text else ""

    title_quotes = _title_inner_quotes(bold_title) if bold_title else []
    # Body = everything after the bold title (and the dash/whitespace).
    body = text[bold.end():] if bold else text
    body_patterns = _extract_patterns_from_tic_body(body)

    has_title_quote = bool(title_quotes)
    has_body_pattern = bool(body_patterns)

    if not has_title_quote and not has_body_pattern and title_text and _NON_ASCII_RE.search(title_text):
        warnings.append(
            {
                "code": LINT_BOLD_TITLE_UNSCANNABLE,
                "message": (
                    "Bold title carries no quoted phrase, the bullet body "
                    "has no quotes or backticks, and the title text contains "
                    "non-ASCII characters — the title-text fallback will "
                    "compile a non-English rule name as the scan pattern, "
                    "which never matches English chapter prose."
                ),
                "hint": (
                    "Add a double-quoted example phrase to the bold title "
                    '(e.g. **Vague-noun "thing"**) or put the bannable '
                    "phrases in the bullet body as double-quoted phrases or "
                    "a backtick regex. Or move the rule to ### Don'ts as a "
                    "backtick-regex Don't."
                ),
            }
        )

    extracted = _extracted_patterns_from_recurring_tics(
        bold_title=bold_title,
        body=body,
        title_quotes=title_quotes,
        body_patterns=body_patterns,
    )
    return {"warnings": warnings, "extracted_patterns": extracted}


def _extracted_patterns_from_recurring_tics(
    *,
    bold_title: str,
    body: str,
    title_quotes: list[str],
    body_patterns: list[tuple[str, re.Pattern[str] | None]],
) -> list[dict[str, Any]]:
    """Mirror the title → body → title-text-fallback cascade of
    :func:`tools.banlist_loader.load_author_writing_discoveries` so the
    lint reports exactly what the loader will extract."""
    del body  # cascade is decided by the bool flags; body content reused via body_patterns
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    def _emit_compiled(label: str, compiled: re.Pattern[str]) -> None:
        cleaned = _strip_parenthetical(label).strip()
        if len(cleaned) < 2:
            return
        key = cleaned.lower()
        if key in seen:
            return
        seen.add(key)
        is_regex = compiled.pattern != re.escape(cleaned)
        out.append(
            {"label": cleaned, "pattern": compiled.pattern, "is_regex": is_regex}
        )

    if title_quotes:
        for phrase in title_quotes:
            cleaned = _strip_parenthetical(phrase).strip()
            _emit_compiled(phrase, _build_discovery_pattern(cleaned))
        return out

    if body_patterns:
        for label, compiled in body_patterns:
            if compiled is None:
                cleaned = _strip_parenthetical(label).strip()
                if len(cleaned) < 2:
                    continue
                _emit_compiled(label, _build_discovery_pattern(cleaned))
            else:
                _emit_compiled(label, compiled)
        return out

    if bold_title:
        for phrase in _extract_phrases_from_bold_title(bold_title):
            cleaned = _strip_parenthetical(phrase).strip()
            _emit_compiled(phrase, _build_discovery_pattern(cleaned))
    return out


# ---------------------------------------------------------------------------
# Style Principles
# ---------------------------------------------------------------------------


def _lint_style_principles(text: str) -> dict[str, Any]:
    """Style Principles are intentionally not machine-scanned — only flag
    bracket-placeholder typos."""
    return {
        "warnings": _check_bracket_placeholders(text),
        "extracted_patterns": [],
    }


# ---------------------------------------------------------------------------
# Shared checks
# ---------------------------------------------------------------------------


def _check_bracket_placeholders(text: str) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for m in _BACKTICK_CONTENT_RE.finditer(text):
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


__all__ = [
    "LINT_BOLD_TITLE_UNSCANNABLE",
    "LINT_BRACKET_PLACEHOLDER",
    "LINT_MIXED_POSITIVE_NEGATIVE_ITALICS",
    "LINT_MIXED_POSITIVE_NEGATIVE_QUOTES",
    "LINT_SCANNER_EXTRACTS_NOTHING",
    "VALID_SECTIONS",
    "lint_author_discovery",
]
