#!/usr/bin/env python3
"""PostToolUse hook: Validate character files after Write/Edit operations.

Checks that character files have required sections and valid frontmatter.
"""

import os
import re
import sys
from pathlib import Path

import yaml

REQUIRED_FRONTMATTER = ["name", "role", "status"]
REQUIRED_SECTIONS = ["Want vs. Need", "Fatal Flaw", "The Ghost", "Motivation Chain"]


def validate_character(file_path: str) -> list[str]:
    """Validate a character file and return list of issues."""
    path = Path(file_path)
    issues: list[str] = []

    if not path.exists():
        return []

    # Only validate character files (in characters/ directories)
    if "/characters/" not in str(path) or not path.suffix == ".md":
        return []

    # Skip INDEX.md
    if path.name == "INDEX.md":
        return []

    text = path.read_text(encoding="utf-8")

    # Check frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not fm_match:
        issues.append(f"WARN: {path.name} — Missing YAML frontmatter")
        return issues

    try:
        meta = yaml.safe_load(fm_match.group(1)) or {}
    except yaml.YAMLError:
        issues.append(f"FAIL: {path.name} — Invalid YAML frontmatter")
        return issues

    # Required frontmatter fields
    for field in REQUIRED_FRONTMATTER:
        if field not in meta:
            issues.append(f"WARN: {path.name} — Missing frontmatter field: {field}")

    # Check role is valid
    valid_roles = {"protagonist", "antagonist", "supporting", "minor"}
    role = meta.get("role", "").lower()
    if role and role not in valid_roles:
        issues.append(f"WARN: {path.name} — Unknown role '{role}'. Valid: {', '.join(sorted(valid_roles))}")

    # For non-minor characters, check required sections
    if role != "minor":
        for section in REQUIRED_SECTIONS:
            if f"## {section}" not in text:
                issues.append(f"WARN: {path.name} — Missing section: ## {section}")

    return issues


def main() -> None:
    """Entry point for PostToolUse hook."""
    file_path = os.environ.get("CLAUDE_TOOL_ARG_FILE_PATH", "")
    if not file_path:
        file_path = os.environ.get("CLAUDE_FILE_PATH", "")
    if not file_path:
        sys.exit(0)

    issues = validate_character(file_path)

    if issues:
        print("\n".join(issues))
    sys.exit(0)


if __name__ == "__main__":
    main()
