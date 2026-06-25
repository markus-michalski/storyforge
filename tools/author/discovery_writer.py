"""Post-promotion cleanup helpers for author-profile and book CLAUDE.md.

``remove_book_rule_after_promotion`` — once a rule has been promoted to the
author profile, the user can choose to remove it from the book CLAUDE.md
(``mode="remove"``) or leave it with a "promoted to author profile" annotation
(``mode="annotate"``).

Writing Discoveries are now persisted to the ``author_discoveries`` SQLite table
via ``write_author_discovery`` in the MCP router (Issue #281). The old
``write_discovery`` Markdown write path was removed in Phase 5 (#283).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from tools.claudemd.rules_editor import MarkersNotFoundError

# ---------------------------------------------------------------------------
# CLAUDE.md RULES-block helpers
# ---------------------------------------------------------------------------

_RULES_START = "<!-- RULES:START -->"
_RULES_END = "<!-- RULES:END -->"


def _extract_block(content: str) -> tuple[str, int, int]:
    """Return (inner_text, inner_start, inner_end) for the RULES block."""
    start = content.find(_RULES_START)
    end = content.find(_RULES_END)
    if start == -1 or end == -1:
        raise MarkersNotFoundError("RULES:START/END markers not found in CLAUDE.md")
    inner_start = start + len(_RULES_START)
    inner_end = end
    return content[inner_start:inner_end], inner_start, inner_end


def _parse_bullets(block_text: str) -> list[str]:
    """Parse bullet items from a RULES block into a list of body strings."""
    bullets: list[str] = []
    current: list[str] = []
    for line in block_text.splitlines():
        if line.startswith("- "):
            if current:
                bullets.append("\n".join(current))
            current = [line[2:]]
        elif line.startswith("  ") and current:
            current.append(line[2:])
    if current:
        bullets.append("\n".join(current))
    return bullets


def _serialize_block(bodies: list[str]) -> str:
    """Serialize rule body strings back to a RULES block inner text."""
    if not bodies:
        return "\n"
    lines: list[str] = []
    for body in bodies:
        body_lines = body.split("\n")
        lines.append(f"- {body_lines[0]}")
        for cont in body_lines[1:]:
            lines.append(f"  {cont}")
    return "\n" + "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

VALID_SECTIONS: tuple[str, ...] = ("recurring_tics", "style_principles", "donts")


@dataclass
class RemovalResult:
    removed: bool
    annotated: bool
    path: Path
    message: str


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
    "MarkersNotFoundError",
    "RemovalResult",
    "VALID_SECTIONS",
    "remove_book_rule_after_promotion",
]
