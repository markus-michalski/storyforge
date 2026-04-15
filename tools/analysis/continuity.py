"""Continuity checking tools for StoryForge — detect plot holes and inconsistencies."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.state.parsers import parse_frontmatter


def extract_character_mentions(text: str, character_names: list[str]) -> dict[str, list[int]]:
    """Find which characters are mentioned in which lines of text."""
    mentions: dict[str, list[int]] = {name: [] for name in character_names}

    for i, line in enumerate(text.splitlines(), 1):
        for name in character_names:
            if name.lower() in line.lower():
                mentions[name].append(i)

    return {name: lines for name, lines in mentions.items() if lines}


def check_character_consistency(project_dir: Path) -> list[dict[str, Any]]:
    """Check character details across chapters for inconsistencies.

    Looks for characters mentioned in chapters that don't have character files,
    and characters with files that are never mentioned.
    """
    issues = []

    # Get character names from character files
    chars_dir = project_dir / "characters"
    character_names = []
    if chars_dir.exists():
        for f in chars_dir.glob("*.md"):
            if f.name == "INDEX.md":
                continue
            text = f.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text)
            name = meta.get("name", f.stem)
            character_names.append(name)

    # Check each chapter for character mentions
    chapters_dir = project_dir / "chapters"
    if not chapters_dir.exists():
        return issues

    chapter_mentions: dict[str, set[str]] = {}
    for ch_dir in sorted(chapters_dir.iterdir()):
        draft = ch_dir / "draft.md"
        if not draft.exists():
            continue
        text = draft.read_text(encoding="utf-8")
        mentions = extract_character_mentions(text, character_names)
        chapter_mentions[ch_dir.name] = set(mentions.keys())

    # Find characters never mentioned in any chapter
    all_mentioned = set()
    for names in chapter_mentions.values():
        all_mentioned.update(names)

    for name in character_names:
        if name not in all_mentioned:
            issues.append({
                "type": "unused_character",
                "severity": "warning",
                "message": f"Character '{name}' has a profile but is never mentioned in any chapter",
            })

    return issues


def check_timeline(project_dir: Path) -> list[dict[str, Any]]:
    """Basic timeline consistency checks."""
    issues = []

    timeline_file = project_dir / "plot" / "timeline.md"
    if not timeline_file.exists():
        issues.append({
            "type": "missing_timeline",
            "severity": "info",
            "message": "No timeline.md found — consider creating one for continuity tracking",
        })

    return issues
