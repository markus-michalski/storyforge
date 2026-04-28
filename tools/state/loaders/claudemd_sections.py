"""Loader for book CLAUDE.md sections (Issue #121).

Pulls bullets from ``## Rules`` and ``## Callback Register``, plus
litmus questions from a tone document. Each section parser is a small
pure function so the orchestrator (and tests) can call them in
isolation.
"""

from __future__ import annotations

import re

_RULES_SECTION_RE = re.compile(
    r"^##\s+Rules\s*$(.*?)^##\s+",
    re.MULTILINE | re.DOTALL,
)
_CALLBACKS_SECTION_RE = re.compile(
    r"^##\s+Callback Register\s*$(.*?)(?=^---\s*$|\Z)",
    re.MULTILINE | re.DOTALL,
)
_LITMUS_SECTION_RE = re.compile(
    r"^##\s+Litmus Test\s*$(.*?)(?=^##\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<body>.+?)\s*$", re.MULTILINE)
_NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+(?P<body>.+?)\s*$", re.MULTILINE)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# Same heuristic the linter hook uses: a rule that looks like a
# banned-phrase declaration is block-severity, everything else advisory.
_BAN_CUE_RE = re.compile(
    r"\b(banned|ban|avoid|never|don[’']?t\s+use|do\s+not\s+use|"
    r"limit|stop\s+using)\b",
    re.IGNORECASE,
)


def _section_bullets(text: str, regex: re.Pattern[str]) -> list[str]:
    match = regex.search(text)
    if not match:
        return []
    body = _COMMENT_RE.sub("", match.group(1))
    items: list[str] = []
    for m in _BULLET_RE.finditer(body):
        item = re.sub(r"\s+", " ", m.group("body")).strip()
        if item:
            items.append(item)
    return items


def rule_bullets(claudemd_text: str) -> list[str]:
    """Bullets from the book CLAUDE.md ``## Rules`` section."""
    return _section_bullets(claudemd_text, _RULES_SECTION_RE)


def callback_register_bullets(claudemd_text: str) -> list[str]:
    """Bullets from the book CLAUDE.md ``## Callback Register`` section."""
    return _section_bullets(claudemd_text, _CALLBACKS_SECTION_RE)


def litmus_questions(tone_text: str) -> list[str]:
    """Litmus tests are typically numbered, sometimes bulleted."""
    match = _LITMUS_SECTION_RE.search(tone_text)
    if not match:
        return []
    body = match.group(1)
    items: list[str] = []
    for regex in (_NUMBERED_RE, _BULLET_RE):
        for m in regex.finditer(body):
            item = re.sub(r"\s+", " ", m.group("body")).strip()
            if item and item not in items:
                items.append(item)
    return items


def classify_rule(rule: str) -> str:
    """Return ``"block"`` for backtick-wrapped ban-cued rules, else ``"advisory"``."""
    if "`" in rule and _BAN_CUE_RE.search(rule):
        return "block"
    return "advisory"


__all__ = [
    "callback_register_bullets",
    "classify_rule",
    "litmus_questions",
    "rule_bullets",
]
