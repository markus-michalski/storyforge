#!/usr/bin/env python3
"""PostToolUse hook: Validate chapter files after Write/Edit operations.

Checks that chapter drafts don't contain AI-tell vocabulary and have proper structure.
Runs automatically after any file write/edit that matches chapter file patterns.
"""

import os
import re
import sys
from pathlib import Path

# AI-tell words that must NEVER appear in fiction prose
AI_TELL_WORDS = [
    "delve", "tapestry", "nuanced", "vibrant", "embark", "resonate",
    "pivotal", "multifaceted", "realm", "testament", "intricate",
    "myriad", "unprecedented", "foster", "beacon", "juxtaposition",
    "paradigm", "synergy", "interplay", "ever-evolving", "navigate",
    "uncover", "aforementioned", "groundbreaking", "spearhead",
    "leverage", "underpin", "underscore", "overarching", "holistic",
    "robust", "streamline", "cutting-edge", "utilize", "facilitate",
    "endeavor", "comprehensive", "furthermore", "moreover",
    "bustling", "piercing", "riveting", "captivating", "mesmerizing",
]


def validate_chapter(file_path: str) -> list[str]:
    """Validate a chapter draft file and return list of issues."""
    path = Path(file_path)
    issues: list[str] = []

    if not path.exists():
        return []

    # Only validate draft.md files in chapters/ directories
    if "/chapters/" not in str(path):
        return []

    # Only check draft.md files (not README.md outlines)
    if path.name != "draft.md":
        return []

    text = path.read_text(encoding="utf-8")

    # Skip near-empty drafts (just a header)
    if len(text.split()) < 50:
        return []

    # Scan for AI-tell words
    text_lower = text.lower()
    for word in AI_TELL_WORDS:
        pattern = rf'\b{re.escape(word)}\b'
        matches = list(re.finditer(pattern, text_lower))
        if matches:
            # Find line number for first occurrence
            line_num = text[:matches[0].start()].count('\n') + 1
            issues.append(
                f"WARN: AI-tell word '{word}' found in {path.name} "
                f"(line {line_num}, {len(matches)} occurrence{'s' if len(matches) > 1 else ''})"
            )

    # Check sentence length variance (AI detection metric)
    # Remove markdown headers and frontmatter
    prose = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
    prose = re.sub(r"^#+\s+.*$", "", prose, flags=re.MULTILINE)
    sentences = re.split(r'(?<=[.!?])\s+', prose.strip())
    sentences = [s for s in sentences if len(s.split()) > 0]

    if len(sentences) > 10:
        lengths = [len(s.split()) for s in sentences]
        mean = sum(lengths) / len(lengths)
        variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
        std_dev = variance ** 0.5

        if std_dev < 4:
            issues.append(
                f"WARN: Low sentence length variance (std_dev={std_dev:.1f}) — "
                f"text may sound AI-generated. Vary sentence lengths more."
            )

    return issues


def main() -> None:
    """Entry point for PostToolUse hook."""
    # Get the file that was just written/edited
    file_path = os.environ.get("CLAUDE_TOOL_ARG_FILE_PATH", "")
    if not file_path:
        # Try new_string path for Edit tool
        file_path = os.environ.get("CLAUDE_FILE_PATH", "")
    if not file_path:
        sys.exit(0)

    issues = validate_chapter(file_path)

    if issues:
        # Output issues as hook feedback
        print("\n".join(issues))
        # Don't block — these are warnings, not errors
        sys.exit(0)


if __name__ == "__main__":
    main()
