"""Write Writing Discoveries to ``profile.md`` and clean up book CLAUDE.md (Issue #151).

Two write paths:

- ``write_discovery`` — append/extend an entry under ``## Writing Discoveries``
  → ``### {Recurring Tics | Style Principles | Don'ts}``. Idempotent: if the
  entry text already exists, append an additional origin tag instead of
  duplicating the bullet. This implements the "second-origin-tag-on-recurrence"
  rule from Issue #151.

- ``remove_book_rule_after_promotion`` — once a rule has been promoted to the
  author profile, the user can choose to remove it from the book CLAUDE.md
  (``mode="remove"``) or leave it with a "promoted to author profile" annotation
  (``mode="annotate"``).

The discovery_writer does NOT handle banned-phrase promotions — those go via
``tools.rule_writer.write_author_rule`` which already writes to ``vocabulary.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from tools.claudemd.rules_editor import (
    MarkersNotFoundError,
    _extract_block,
    _parse_bullets,
    _serialize_block,
)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


VALID_SECTIONS: tuple[str, ...] = ("recurring_tics", "style_principles", "donts")

_SECTION_HEADERS: dict[str, str] = {
    "recurring_tics": "### Recurring Tics",
    "style_principles": "### Style Principles",
    "donts": "### Don'ts (beyond banned phrases)",
}

# Placeholder bullet used in fresh templates. Removed when the first real
# entry lands so the section doesn't carry "_Frei._" alongside real content.
_PLACEHOLDER_RE = re.compile(r"^_(?:frei|free|empty|tba|tbd)\.?_\s*$", re.IGNORECASE)

# Origin tag written by `write_discovery`. Format kept identical to the
# parser in `tools/state/parsers.py` so the round-trip is lossless.
_ORIGIN_TAG_RE = re.compile(
    r"_\(\s*emerged\s+from\s+(?P<book>[a-z0-9][a-z0-9_-]*)\s*,\s*(?P<date>\d{4}-\d{2})\s*\)_",
    re.IGNORECASE,
)


class SectionMissing(Exception):
    """Raised when the profile lacks a ``## Writing Discoveries`` section.

    The skill catches this and offers to migrate the profile (insert the
    template section) before retrying.
    """


@dataclass
class WriteResult:
    written: bool
    path: Path
    message: str


@dataclass
class AlreadyPresent:
    """Idempotent no-op result. The discovery + this exact origin tag are
    already in the profile."""

    written: bool
    path: Path
    message: str


@dataclass
class RemovalResult:
    removed: bool
    annotated: bool
    path: Path
    message: str


# ---------------------------------------------------------------------------
# write_discovery
# ---------------------------------------------------------------------------


_DISCOVERIES_SECTION_RE = re.compile(
    r"^##\s+Writing\s+Discoveries\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def write_discovery(
    *,
    profile_path: Path,
    section: str,
    text: str,
    book_slug: str,
    year_month: str,
) -> WriteResult | AlreadyPresent:
    """Append a discovery to ``profile.md`` under the matching sub-section.

    Args:
        profile_path: Path to the author's ``profile.md``.
        section: One of ``recurring_tics``, ``style_principles``, ``donts``.
        text: Entry body, e.g. ``**"math" as analytical metaphor** — cut on sight.``.
            The origin tag is appended automatically.
        book_slug: Book the discovery emerged from (used in the origin tag).
        year_month: ``YYYY-MM`` date stamp (used in the origin tag).

    Returns either ``WriteResult(written=True)`` on a real change, or
    ``AlreadyPresent`` when the entry plus the *same* origin tag already exist
    (true idempotent). When the same entry text exists but with a different
    origin, the new origin tag is appended to the existing bullet — counted
    as ``written=True`` because the new tag IS new information.

    Raises:
        ValueError: ``section`` is not in ``VALID_SECTIONS``.
        SectionMissing: ``profile.md`` has no ``## Writing Discoveries`` section.
        FileNotFoundError: ``profile.md`` does not exist.
    """
    if section not in VALID_SECTIONS:
        raise ValueError(f"Invalid section: {section}. Valid: {VALID_SECTIONS}")

    if not profile_path.is_file():
        raise FileNotFoundError(f"Profile not found: {profile_path}")

    content = profile_path.read_text(encoding="utf-8")
    if not _DISCOVERIES_SECTION_RE.search(content):
        raise SectionMissing(
            f"profile.md has no '## Writing Discoveries' section. "
            f"Add the template scaffold first: {profile_path}"
        )

    new_origin_tag = _format_origin_tag(book_slug, year_month)
    sub_heading = _SECTION_HEADERS[section]

    # Locate the sub-section. If missing, create it inside the Writing
    # Discoveries section.
    sub_section_match = re.search(
        rf"^{re.escape(sub_heading)}\s*$",
        content,
        re.MULTILINE,
    )
    if sub_section_match is None:
        content = _create_subsection(content, sub_heading)
        sub_section_match = re.search(
            rf"^{re.escape(sub_heading)}\s*$",
            content,
            re.MULTILINE,
        )
        assert sub_section_match is not None  # we just inserted it

    # Slice out the sub-section body up to the next H3 / H2 / EOF.
    sub_start = sub_section_match.end()
    next_header = re.search(r"^##\s|^###\s", content[sub_start:], re.MULTILINE)
    sub_end = sub_start + next_header.start() if next_header else len(content)
    sub_body = content[sub_start:sub_end]

    normalized_text = _normalize_entry_text(text)

    # Walk existing bullets in the sub-section. If we find a bullet whose
    # core text matches the candidate, either skip (origin tag already there)
    # or append the new origin tag.
    bullet_match, body_text, body_origins = _find_matching_bullet(sub_body, normalized_text)
    if bullet_match is not None:
        if any(_origin_matches(o, book_slug, year_month) for o in body_origins):
            return AlreadyPresent(
                written=False,
                path=profile_path,
                message=f"Discovery already present with this origin: {profile_path}",
            )
        # Append new origin tag to the existing bullet.
        new_bullet = bullet_match.group(0).rstrip() + f" {new_origin_tag}\n"
        new_sub_body = sub_body[: bullet_match.start()] + new_bullet + sub_body[bullet_match.end() :]
    else:
        # Append new bullet. Strip placeholder if present.
        new_sub_body = _strip_placeholder(sub_body)
        bullet = f"- {text.strip()} {new_origin_tag}"
        if not new_sub_body.endswith("\n"):
            new_sub_body += "\n"
        new_sub_body += bullet + "\n"

    new_content = content[:sub_start] + new_sub_body + content[sub_end:]
    profile_path.write_text(new_content, encoding="utf-8")
    return WriteResult(
        written=True,
        path=profile_path,
        message=f"Discovery written to {profile_path}",
    )


def _format_origin_tag(book_slug: str, year_month: str) -> str:
    return f"_(emerged from {book_slug}, {year_month})_"


def _origin_matches(origin: dict[str, str], book_slug: str, year_month: str) -> bool:
    return origin["book"].lower() == book_slug.lower() and origin["date"] == year_month


def _normalize_entry_text(text: str) -> str:
    """Normalize entry text for duplicate detection.

    Strips origin tags, collapses whitespace, lowercases. Keeps the bold
    title intact so `**math**` matches `**math**`.
    """
    cleaned = _ORIGIN_TAG_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def _find_matching_bullet(
    sub_body: str,
    normalized_target: str,
) -> tuple[re.Match[str] | None, str, list[dict[str, str]]]:
    """Find a bullet in ``sub_body`` whose normalized text matches the target.

    Returns ``(match, body_text, origins)`` or ``(None, "", [])``.
    """
    bullet_re = re.compile(r"^-\s+(?P<body>.+?)\n", re.MULTILINE)
    for match in bullet_re.finditer(sub_body):
        body = match.group("body")
        normalized_existing = _normalize_entry_text(body)
        if normalized_existing == normalized_target:
            origins = [
                {"book": m.group("book"), "date": m.group("date")}
                for m in _ORIGIN_TAG_RE.finditer(body)
            ]
            return match, body, origins
    return None, "", []


def _strip_placeholder(sub_body: str) -> str:
    """Remove a `_Frei._` (or similar) placeholder line from the sub-section."""
    lines = sub_body.splitlines(keepends=True)
    filtered = [ln for ln in lines if not _PLACEHOLDER_RE.match(ln.strip())]
    out = "".join(filtered)
    # Collapse 3+ consecutive newlines that may result.
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def _create_subsection(content: str, sub_heading: str) -> str:
    """Insert a missing sub-heading at the end of the Writing Discoveries section."""
    section_match = _DISCOVERIES_SECTION_RE.search(content)
    if section_match is None:
        # Caller must already have checked this — defensive guard.
        raise SectionMissing("Writing Discoveries section missing")

    # Find end of Writing Discoveries section (next ## or EOF).
    after_section = content[section_match.end():]
    next_h2 = re.search(r"^##\s", after_section, re.MULTILINE)
    insertion_point = section_match.end() + (next_h2.start() if next_h2 else len(after_section))

    insertion = f"\n{sub_heading}\n\n"
    return content[:insertion_point].rstrip() + "\n\n" + insertion + content[insertion_point:].lstrip()


# ---------------------------------------------------------------------------
# remove_book_rule_after_promotion
# ---------------------------------------------------------------------------


def remove_book_rule_after_promotion(
    *,
    claudemd_path: Path,
    rule_index: int,
    mode: str = "remove",
) -> RemovalResult:
    """Remove or annotate a rule in a book's CLAUDE.md after promotion.

    Args:
        claudemd_path: Path to the book's ``CLAUDE.md``.
        rule_index: 0-based index in the RULES block.
        mode: ``"remove"`` deletes the bullet; ``"annotate"`` keeps it and
            appends ``_(promoted to author profile, YYYY-MM-DD)_``.

    Returns ``RemovalResult`` describing the action.

    Raises:
        FileNotFoundError: ``CLAUDE.md`` does not exist.
        ValueError: ``mode`` is invalid or ``rule_index`` is out of range.
        MarkersNotFoundError: RULES block markers missing.
    """
    if mode not in {"remove", "annotate"}:
        raise ValueError(f"Invalid mode: {mode}. Valid: 'remove' | 'annotate'")
    if not claudemd_path.is_file():
        raise FileNotFoundError(f"CLAUDE.md not found: {claudemd_path}")

    content = claudemd_path.read_text(encoding="utf-8")
    block_text, inner_start, inner_end = _extract_block(content)
    bodies = _parse_bullets(block_text)

    if not 0 <= rule_index < len(bodies):
        raise ValueError(
            f"rule_index {rule_index} out of range (have {len(bodies)} rules)"
        )

    if mode == "remove":
        new_bodies = bodies[:rule_index] + bodies[rule_index + 1 :]
        new_block = _serialize_block(new_bodies)
        new_content = content[:inner_start] + new_block + content[inner_end:]
        claudemd_path.write_text(new_content, encoding="utf-8")
        return RemovalResult(
            removed=True,
            annotated=False,
            path=claudemd_path,
            message=f"Rule {rule_index} removed from {claudemd_path}",
        )

    # annotate
    today_iso = date.today().isoformat()
    note = f"_(promoted to author profile, {today_iso})_"
    new_bodies = list(bodies)
    new_bodies[rule_index] = f"{bodies[rule_index].rstrip()} {note}"
    new_block = _serialize_block(new_bodies)
    new_content = content[:inner_start] + new_block + content[inner_end:]
    claudemd_path.write_text(new_content, encoding="utf-8")
    return RemovalResult(
        removed=False,
        annotated=True,
        path=claudemd_path,
        message=f"Rule {rule_index} annotated as promoted in {claudemd_path}",
    )


__all__ = [
    "AlreadyPresent",
    "MarkersNotFoundError",
    "RemovalResult",
    "SectionMissing",
    "VALID_SECTIONS",
    "WriteResult",
    "remove_book_rule_after_promotion",
    "write_discovery",
]
