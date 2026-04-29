"""Write banned-phrase rules to book, author, or global scope.

Three write targets:
- ``book`` — appends a rule entry to the book's ``CLAUDE.md ## Rules`` section.
  Uses the existing ``tools.claudemd.manager.append_rule`` path (idempotent).
- ``author`` — appends a bullet to ``### Absolutely Forbidden`` in
  ``~/.storyforge/authors/{slug}/vocabulary.md``.
- ``global`` — appends a numbered entry to ``### Heavily Flagged Words and
  Phrases`` in ``reference/craft/anti-ai-patterns.md``.

All three targets include metadata so future maintainers can trace why a rule
exists: ``_(added YYYY-MM-DD — source: ...)_``.

Promotion path: ``promote_rule`` moves a phrase from book → author or author →
global scope. It writes to the target and removes the line from the source if
``remove_from_source=True`` (default True).
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from tools.claudemd.manager import append_rule as _claudemd_append_rule


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

Scope = str  # "book" | "author" | "global"

SCOPE_BOOK = "book"
SCOPE_AUTHOR = "author"
SCOPE_GLOBAL = "global"

VALID_SCOPES: tuple[Scope, ...] = (SCOPE_BOOK, SCOPE_AUTHOR, SCOPE_GLOBAL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _today() -> str:
    return date.today().isoformat()


def _metadata_tag(source_context: str) -> str:
    return f"_(added {_today()} — source: {source_context})_"


def _phrase_already_present(text: str, phrase: str) -> bool:
    """Case-insensitive substring check to detect duplicates before writing."""
    return phrase.lower() in text.lower()


# ---------------------------------------------------------------------------
# Book-scoped writer
# ---------------------------------------------------------------------------


def write_book_rule(
    phrase: str,
    reason: str,
    config: dict[str, Any],
    book_slug: str,
    source_context: str = "report-issue",
) -> tuple[bool, str]:
    """Append a banned phrase to the book's CLAUDE.md Rules section.

    Returns ``(written, message)`` where ``written`` is False when the phrase
    already existed (idempotent).

    The rule is formatted as:
        Avoid ``{phrase}`` — {reason} {metadata}
    """
    from tools.claudemd.manager import resolve_claudemd_path

    path = resolve_claudemd_path(config, book_slug)
    if path.exists() and _phrase_already_present(path.read_text(encoding="utf-8"), phrase):
        return False, f"Rule already present in book CLAUDE.md (skipped): {phrase}"

    tag = _metadata_tag(source_context)
    text = f"Avoid `{phrase}` — {reason} {tag}"
    _claudemd_append_rule(config, book_slug, text)
    return True, f"Rule written to book CLAUDE.md: {path}"


# ---------------------------------------------------------------------------
# Author-scoped writer
# ---------------------------------------------------------------------------

_ABSOLUTELY_FORBIDDEN_RE = re.compile(
    r"^###\s+Absolutely\s+Forbidden\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def _author_vocab_path(author_slug: str, storyforge_home: Path | None = None) -> Path:
    home = storyforge_home or (Path.home() / ".storyforge")
    return home / "authors" / author_slug / "vocabulary.md"


def write_author_rule(
    phrase: str,
    reason: str,
    author_slug: str,
    source_context: str = "report-issue",
    storyforge_home: Path | None = None,
) -> tuple[bool, str]:
    """Append a banned phrase to the author's vocabulary.md.

    Inserts a bullet under ``### Absolutely Forbidden``. Creates the section
    if it does not exist. Idempotent: if the phrase is already present,
    returns (False, message).

    Returns ``(written, message)``.
    """
    vocab_path = _author_vocab_path(author_slug, storyforge_home)
    if not vocab_path.is_file():
        return False, f"Author vocabulary not found: {vocab_path}"

    content = vocab_path.read_text(encoding="utf-8")
    if _phrase_already_present(content, phrase):
        return False, f"Phrase already present in author vocabulary (skipped): {phrase}"

    tag = _metadata_tag(source_context)
    bullet = f"- {phrase} {tag}"

    match = _ABSOLUTELY_FORBIDDEN_RE.search(content)
    if match:
        # Insert after the section heading, before the next content.
        insert_pos = match.end()
        # Skip blank lines immediately after the heading.
        rest = content[insert_pos:]
        leading_newlines = len(rest) - len(rest.lstrip("\n"))
        insert_pos += leading_newlines
        updated = content[:insert_pos] + "\n" + bullet + "\n" + content[insert_pos:]
    else:
        # Section not found — append a new one at the end.
        updated = content.rstrip("\n") + f"\n\n### Absolutely Forbidden\n\n{bullet}\n"

    vocab_path.write_text(updated, encoding="utf-8")
    return True, f"Rule written to author vocabulary: {vocab_path}"


# ---------------------------------------------------------------------------
# Global writer
# ---------------------------------------------------------------------------

_HEAVILY_FLAGGED_SECTION_RE = re.compile(
    r"^###\s+Heavily\s+Flagged\s+Words\s+and\s+Phrases.*$",
    re.MULTILINE | re.IGNORECASE,
)
_NEXT_SECTION_RE = re.compile(r"^##+\s+\S", re.MULTILINE)
_LAST_NUMBERED_RE = re.compile(r"^(\d+)\.", re.MULTILINE)


def write_global_rule(
    phrase: str,
    reason: str,
    plugin_root: Path,
    source_context: str = "report-issue",
) -> tuple[bool, str]:
    """Append a numbered entry to the global anti-AI patterns vocabulary section.

    Idempotent: if the phrase already appears in the section, returns (False, msg).

    Returns ``(written, message)``.
    """
    target = plugin_root / "reference" / "craft" / "anti-ai-patterns.md"
    if not target.is_file():
        return False, f"Global anti-AI patterns file not found: {target}"

    content = target.read_text(encoding="utf-8")

    section_match = _HEAVILY_FLAGGED_SECTION_RE.search(content)
    if not section_match:
        return False, "Could not locate '### Heavily Flagged Words and Phrases' section in anti-ai-patterns.md"

    section_start = section_match.end()
    section_body = content[section_start:]
    next_sec = _NEXT_SECTION_RE.search(section_body)
    if next_sec:
        section_body_text = section_body[: next_sec.start()]
    else:
        section_body_text = section_body

    if _phrase_already_present(section_body_text, phrase):
        return False, f"Phrase already present in global anti-AI patterns (skipped): {phrase}"

    # Determine next entry number.
    all_numbers = _LAST_NUMBERED_RE.findall(section_body_text)
    next_number = int(all_numbers[-1]) + 1 if all_numbers else 1

    tag = _metadata_tag(source_context)
    new_entry = f"{next_number}. **{phrase}** — {reason} {tag}"

    # Insert before the next section heading or at end of section.
    if next_sec:
        insert_at = section_start + next_sec.start()
        # Ensure a blank line before next section.
        updated = content[:insert_at].rstrip("\n") + f"\n{new_entry}\n\n" + content[insert_at:]
    else:
        # Append to the end of the file.
        updated = content.rstrip("\n") + f"\n{new_entry}\n"

    target.write_text(updated, encoding="utf-8")
    return True, f"Rule written to global anti-AI patterns: {target}"


# ---------------------------------------------------------------------------
# Promote rule
# ---------------------------------------------------------------------------


def promote_rule(
    phrase: str,
    reason: str,
    from_scope: Scope,
    to_scope: Scope,
    *,
    config: dict[str, Any] | None = None,
    book_slug: str | None = None,
    author_slug: str | None = None,
    plugin_root: Path | None = None,
    source_context: str = "promote-rule",
    storyforge_home: Path | None = None,
    remove_from_source: bool = True,
) -> tuple[bool, str]:
    """Promote a banned phrase from a lower scope to a higher scope.

    Supported promotions: book → author, author → global, book → global.

    Optionally removes the rule from the source scope after writing to the
    target (``remove_from_source=True`` by default).

    Returns ``(success, message)``.
    """
    if from_scope not in VALID_SCOPES or to_scope not in VALID_SCOPES:
        return False, f"Invalid scope. Valid values: {VALID_SCOPES}"

    scope_rank = {SCOPE_BOOK: 0, SCOPE_AUTHOR: 1, SCOPE_GLOBAL: 2}
    if scope_rank[to_scope] <= scope_rank[from_scope]:
        return False, f"Target scope '{to_scope}' must be higher than source scope '{from_scope}'"

    # Write to target scope.
    written, msg = _write_to_scope(
        phrase=phrase,
        reason=reason,
        scope=to_scope,
        config=config,
        book_slug=book_slug,
        author_slug=author_slug,
        plugin_root=plugin_root,
        source_context=source_context,
        storyforge_home=storyforge_home,
    )
    if not written and "already present" not in msg:
        return False, msg

    if remove_from_source:
        _remove_from_scope(
            phrase=phrase,
            scope=from_scope,
            config=config,
            book_slug=book_slug,
            author_slug=author_slug,
            plugin_root=plugin_root,
            storyforge_home=storyforge_home,
        )

    return True, f"Promoted '{phrase}' from {from_scope} → {to_scope}. {msg}"


def _write_to_scope(
    phrase: str,
    reason: str,
    scope: Scope,
    config: dict[str, Any] | None,
    book_slug: str | None,
    author_slug: str | None,
    plugin_root: Path | None,
    source_context: str,
    storyforge_home: Path | None,
) -> tuple[bool, str]:
    if scope == SCOPE_BOOK:
        if not config or not book_slug:
            return False, "config and book_slug required for book scope"
        return write_book_rule(phrase, reason, config, book_slug, source_context)
    elif scope == SCOPE_AUTHOR:
        if not author_slug:
            return False, "author_slug required for author scope"
        return write_author_rule(phrase, reason, author_slug, source_context, storyforge_home)
    else:
        if not plugin_root:
            return False, "plugin_root required for global scope"
        return write_global_rule(phrase, reason, plugin_root, source_context)


def _remove_from_scope(
    phrase: str,
    scope: Scope,
    config: dict[str, Any] | None,
    book_slug: str | None,
    author_slug: str | None,
    plugin_root: Path | None,
    storyforge_home: Path | None,
) -> None:
    """Remove a phrase rule from the given scope file. Best-effort, no error raised."""
    try:
        if scope == SCOPE_BOOK:
            if not config or not book_slug:
                return
            from tools.claudemd.manager import resolve_claudemd_path

            path = resolve_claudemd_path(config, book_slug)
        elif scope == SCOPE_AUTHOR:
            if not author_slug:
                return
            path = _author_vocab_path(author_slug, storyforge_home)
        else:
            if not plugin_root:
                return
            path = plugin_root / "reference" / "craft" / "anti-ai-patterns.md"

        if not path.is_file():
            return

        content = path.read_text(encoding="utf-8")
        # Remove lines that contain the phrase (case-insensitive).
        phrase_lower = phrase.lower()
        lines = content.splitlines(keepends=True)
        filtered = [line for line in lines if phrase_lower not in line.lower()]
        path.write_text("".join(filtered), encoding="utf-8")
    except Exception:
        pass
