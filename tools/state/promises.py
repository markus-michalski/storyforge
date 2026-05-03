"""Per-chapter promise persistence — Issue #150 (Plothole Checker).

A "promise" is a setup-element placed in a chapter that needs payoff
later: a locked drawer no one has opened yet, a character's claim
that will be tested, a clue that needs to land. Each chapter README
carries an optional ``## Promises`` section listing the chapter's
promises with their target chapter (or ``unfired`` for "must land
before book end, no fixed target") and a status.

Producers:
- chapter-writer skill (auto-extraction at Draft -> Review transition)
- /storyforge:backfill-promises (LLM pass over already-drafted chapters)
- author hand-edits

Consumers:
- analyze_plot_logic MCP tool (chekhov_gun detection)
- chapter-reviewer skill (continuity check)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

VALID_STATUSES: tuple[str, ...] = ("active", "satisfied", "retired")
PROMISES_HEADING = "## Promises"
PLACEHOLDER_TEXT = "_No promises this chapter._"

# Section blurb shown to the human reading the README.
SECTION_BLURB = (
    "*Setup elements placed in this chapter that need payoff later. "
    "Auto-populated at Draft → Review transition; manual edits welcome.*"
)


@dataclass(frozen=True)
class Promise:
    """A single setup-element awaiting payoff."""

    description: str
    target: str  # chapter slug, "Ch N", or "unfired"
    status: Literal["active", "satisfied", "retired"] = "active"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_promises_section(readme_text: str) -> list[Promise]:
    """Extract the promise list from a chapter README's ``## Promises``
    section.

    Returns an empty list when the section is missing, empty, or
    contains only the placeholder.
    """
    section = _extract_section(readme_text, PROMISES_HEADING)
    if not section:
        return []

    promises: list[Promise] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|---"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 3:
            continue
        # Skip header row.
        if cells[0].lower() == "promise" and cells[1].lower() == "target":
            continue
        description, target, status = cells[0], cells[1], cells[2].lower()
        if not description or not target:
            continue
        if status not in VALID_STATUSES:
            continue
        promises.append(Promise(description=description, target=target, status=status))
    return promises


def _extract_section(text: str, heading: str) -> str:
    """Return body of a markdown section between ``heading`` and the
    next ``## `` heading (or end of file).
    """
    # Anchor to start-of-line; `re.MULTILINE` so ^ matches after newline.
    pattern = re.compile(
        rf"^{re.escape(heading)}\s*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1) if match else ""


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_promises_section(promises: list[Promise]) -> str:
    """Render the full ``## Promises`` section as markdown.

    Empty list -> placeholder section indicating the extractor ran
    and found nothing (distinct from "section absent").
    """
    if not promises:
        return f"{PROMISES_HEADING}\n\n{SECTION_BLURB}\n\n{PLACEHOLDER_TEXT}\n"

    lines = [
        PROMISES_HEADING,
        "",
        SECTION_BLURB,
        "",
        "| Promise | Target | Status |",
        "|---------|--------|--------|",
    ]
    for p in promises:
        lines.append(f"| {p.description} | {p.target} | {p.status} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Upsert (write/merge)
# ---------------------------------------------------------------------------


def upsert_promises(readme_path: Path, new_promises: list[Promise]) -> dict:
    """Merge ``new_promises`` into the chapter README's Promises section.

    Merge semantics:
    - Same description + same target -> update status if changed
      ("updated"), else no-op ("unchanged").
    - New description -> append ("added").
    - Existing promises not mentioned in ``new_promises`` are kept
      as-is. To remove a promise, set its status to ``retired`` or
      hand-edit the README.

    Returns a dict with counts: ``added``, ``updated``, ``unchanged``.
    """
    _validate_promises(new_promises)

    text = readme_path.read_text(encoding="utf-8")
    existing = parse_promises_section(text)

    merged, counts = _merge_promises(existing, new_promises)
    new_section = render_promises_section(merged)

    updated_text = _replace_or_insert_section(text, PROMISES_HEADING, new_section)

    if updated_text != text:
        readme_path.write_text(updated_text, encoding="utf-8")
    return counts


def _validate_promises(promises: list[Promise]) -> None:
    for p in promises:
        if p.status not in VALID_STATUSES:
            raise ValueError(f"Invalid promise status {p.status!r} — must be one of {VALID_STATUSES}")
        if not p.description.strip():
            raise ValueError("Promise description must not be empty.")


def _merge_promises(existing: list[Promise], incoming: list[Promise]) -> tuple[list[Promise], dict]:
    """Merge incoming into existing using (description, target) as key.

    Existing-only entries are preserved. Incoming entries are matched
    by description+target; status changes update, identical entries
    are unchanged, new entries append.
    """
    counts = {"added": 0, "updated": 0, "unchanged": 0}
    by_key: dict[tuple[str, str], Promise] = {(p.description, p.target): p for p in existing}

    for new in incoming:
        key = (new.description, new.target)
        if key in by_key:
            old = by_key[key]
            if old.status == new.status:
                counts["unchanged"] += 1
            else:
                by_key[key] = new
                counts["updated"] += 1
        else:
            by_key[key] = new
            counts["added"] += 1

    # Preserve original ordering: existing first (in original order), then new entries.
    seen: set[tuple[str, str]] = set()
    merged: list[Promise] = []
    for p in existing:
        key = (p.description, p.target)
        merged.append(by_key[key])
        seen.add(key)
    for p in incoming:
        key = (p.description, p.target)
        if key not in seen:
            merged.append(by_key[key])
            seen.add(key)
    return merged, counts


def collect_book_promises(book_path: Path) -> list[dict]:
    """Walk all chapter READMEs in a book and return every promise with
    its source chapter slug attached.

    Returns a list of dicts:
        {
            "source_chapter": "05-the-meeting",
            "promise": Promise(...),
        }

    Used by analyze_plot_logic to build the promise index for
    chekhov_gun detection. Chapters without a Promises section
    contribute zero entries.
    """
    chapters_dir = book_path / "chapters"
    if not chapters_dir.is_dir():
        return []

    out: list[dict] = []
    for ch_dir in sorted(p for p in chapters_dir.iterdir() if p.is_dir()):
        readme = ch_dir / "README.md"
        if not readme.exists():
            continue
        try:
            text = readme.read_text(encoding="utf-8")
        except OSError:
            continue
        for promise in parse_promises_section(text):
            out.append({"source_chapter": ch_dir.name, "promise": promise})
    return out


def _replace_or_insert_section(text: str, heading: str, new_section: str) -> str:
    """Replace existing section or insert before ``## Notes`` (or at end)."""
    pattern = re.compile(
        rf"^{re.escape(heading)}\s*\n.*?(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    if pattern.search(text):
        return pattern.sub(new_section.rstrip() + "\n\n", text, count=1)

    # Insert before ## Notes if present, else append at end.
    notes_pattern = re.compile(r"^## Notes\s*$", re.MULTILINE)
    notes_match = notes_pattern.search(text)
    if notes_match:
        insert_at = notes_match.start()
        return text[:insert_at] + new_section.rstrip() + "\n\n" + text[insert_at:]

    if not text.endswith("\n"):
        text += "\n"
    if not text.endswith("\n\n"):
        text += "\n"
    return text + new_section
