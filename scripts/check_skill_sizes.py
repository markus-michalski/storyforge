#!/usr/bin/env python3
"""Report skill file sizes and flag entries over the bloat budget thresholds.

Thresholds (from CONTRIBUTING.md § Skill-bloat budget):
  - 25 000 characters
  - 400 lines

Info-only: this script never fails CI. It surfaces size pressure so reviewers
can make deliberate decisions before a skill crosses into attention-degradation
territory (see chapter-writer history, Epic #179).
"""

from __future__ import annotations

import sys
from pathlib import Path

CHAR_THRESHOLD = 25_000
LINE_THRESHOLD = 400

RESET = "\033[0m"
RED = "\033[31m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
BOLD = "\033[1m"


def check_skills(repo_root: Path) -> list[dict]:
    skills_dir = repo_root / "skills"
    results = []
    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        text = skill_file.read_text(encoding="utf-8")
        chars = len(text)
        lines = text.count("\n") + 1
        over_chars = chars > CHAR_THRESHOLD
        over_lines = lines > LINE_THRESHOLD
        results.append(
            {
                "name": skill_file.parent.name,
                "chars": chars,
                "lines": lines,
                "over_chars": over_chars,
                "over_lines": over_lines,
                "flagged": over_chars or over_lines,
            }
        )
    return results


def format_row(r: dict, max_name: int) -> str:
    char_str = f"{r['chars']:>7,}"
    line_str = f"{r['lines']:>5}"
    char_flag = f" {RED}> {CHAR_THRESHOLD:,}{RESET}" if r["over_chars"] else ""
    line_flag = f" {RED}> {LINE_THRESHOLD}{RESET}" if r["over_lines"] else ""
    color = RED if r["flagged"] else (YELLOW if r["chars"] > CHAR_THRESHOLD * 0.8 else GREEN)
    name = f"{color}{r['name']:<{max_name}}{RESET}"
    return f"  {name}  {char_str} chars{char_flag}  {line_str} lines{line_flag}"


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    results = check_skills(repo_root)

    flagged = [r for r in results if r["flagged"]]
    near = [r for r in results if not r["flagged"] and r["chars"] > CHAR_THRESHOLD * 0.8]

    max_name = max(len(r["name"]) for r in results) if results else 10

    print(f"\n{BOLD}Skill sizes — storyforge{RESET}\n")
    print(f"  {'Skill':<{max_name}}  {'Chars':>7}        {'Lines':>5}")
    print(f"  {'-' * (max_name + 30)}")

    for r in sorted(results, key=lambda x: x["chars"], reverse=True):
        print(format_row(r, max_name))

    print(f"\n  Thresholds: {CHAR_THRESHOLD:,} chars  |  {LINE_THRESHOLD} lines")

    if flagged:
        print(f"\n  {RED}{BOLD}Over threshold ({len(flagged)} skill(s)):{RESET}")
        for r in flagged:
            reasons = []
            if r["over_chars"]:
                reasons.append(f"{r['chars']:,} chars > {CHAR_THRESHOLD:,}")
            if r["over_lines"]:
                reasons.append(f"{r['lines']} lines > {LINE_THRESHOLD}")
            print(f"    {r['name']}: {', '.join(reasons)}")
        print(f"\n  PR must include a split-or-trim plan. See CONTRIBUTING.md § Skill-bloat budget.")

    if near:
        print(f"\n  {YELLOW}Approaching threshold (> 80%) ({len(near)} skill(s)):{RESET}")
        for r in near:
            pct = int(r["chars"] / CHAR_THRESHOLD * 100)
            print(f"    {r['name']}: {r['chars']:,} chars ({pct}% of limit)")

    if not flagged and not near:
        print(f"\n  {GREEN}All skills within budget.{RESET}")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
