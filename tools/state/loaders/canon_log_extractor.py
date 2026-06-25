"""MD extraction utilities for canon-log.md and people-log.md.

Used exclusively by the migration script (scripts/migrate_canon_log_to_db.py)
to extract facts from Markdown logs and import them into the canon_facts DB.

These functions are preserved from the chapter-writing pipeline (Issue #161)
as migration infrastructure.  They are NOT used by build_canon_brief() which
reads from the DB exclusively (Issue #297).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Regexes (previously in canon_brief.py)
# ---------------------------------------------------------------------------

# Top-level chapter section: ## Chapter 14 — The Fight
CHAPTER_SECTION_RE = re.compile(
    r"^##\s+Chapter\s+(?P<num>\d{1,3})\b[^\n]*$",
    re.MULTILINE,
)

# Sub-section header: ### Theo: skills  or  ### Setting: world rules
SUBSECTION_RE = re.compile(
    r"^###\s+(?P<subject>[^:\n]+):\s*(?P<topic>[^\n]+)$",
    re.MULTILINE,
)

# CHANGED marker inside a bullet point:
# - **CHANGED**: old fact → new fact (revision_impact: 15-aftermath, 17-the-school)
# new-value uses .+? (not [^(\n]+?) so parentheticals in the new value are allowed —
# only a literal "(revision_impact:..." tail is stripped as the impacts clause.
CHANGED_RE = re.compile(
    r"^\s*[-*]\s*\*\*CHANGED\*\*\s*:\s*(?P<old>[^→\n]+?)\s*→\s*(?P<new>.+?)"
    r"(?:\s*\(revision_impact\s*:\s*(?P<impacts>[^)]+)\))?\s*$",
    re.MULTILINE,
)

# Bullet point: "- Some fact."
BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<text>[^\n]+)", re.MULTILINE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_log_path(book_root: Path, book_category: str) -> Path:
    """Return the canonical log path for a given book category."""
    if book_category == "memoir":
        return book_root / "plot" / "people-log.md"
    return book_root / "plot" / "canon-log.md"


def extract_all_facts(book_root: Path, book_category: str = "fiction") -> dict[str, Any]:
    """Extract ALL facts from canon-log.md (or people-log.md for memoir).

    Unlike build_canon_brief(), no scope window is applied — every chapter's
    facts are returned, suitable for a one-time migration into the DB.

    Returns:
        {
          "current_facts":  [{chapter_num, subject, fact, domain}, ...],
          "changed_facts":  [{chapter_num, subject, fact, old_value,
                              revision_impacts (list[str])}, ...],
          "extraction_method": "section_regex" | "heuristic" | "none",
          "warnings": [str, ...],
        }
    """
    log_path = resolve_log_path(book_root, book_category)
    if not log_path.is_file():
        return {
            "current_facts": [], "changed_facts": [],
            "extraction_method": "none",
            "warnings": [f"{log_path.name} not found"],
        }

    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "current_facts": [], "changed_facts": [],
            "extraction_method": "none",
            "warnings": [f"could not read {log_path.name}: {exc}"],
        }

    if not text.strip():
        return {
            "current_facts": [], "changed_facts": [],
            "extraction_method": "none",
            "warnings": [f"{log_path.name} is empty"],
        }

    sections = list(CHAPTER_SECTION_RE.finditer(text))
    if sections:
        return _extract_structured_all(text, sections)
    return _extract_heuristic_all(text)


# ---------------------------------------------------------------------------
# Structured extraction (section_regex) — no scope filtering
# ---------------------------------------------------------------------------


def _extract_structured_all(
    text: str,
    sections: list[re.Match[str]],
) -> dict[str, Any]:
    """Extract all facts from a structured (## Chapter NN) log."""
    current_facts: list[dict[str, Any]] = []
    changed_facts: list[dict[str, Any]] = []

    for i, sec in enumerate(sections):
        sec_num = int(sec.group("num"))
        body_start = sec.end()
        body_end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        body = text[body_start:body_end]

        # CHANGED entries — always include
        for m in CHANGED_RE.finditer(body):
            impacts_raw = (m.group("impacts") or "").strip()
            impacts = [s.strip() for s in impacts_raw.split(",") if s.strip()] if impacts_raw else []
            subject = _subject_before(body, m.start())
            changed_facts.append({
                "chapter_num": sec_num,
                "subject": subject,
                "fact": m.group("new").strip(),
                "old_value": m.group("old").strip(),
                "revision_impacts": impacts,
            })

        # Current facts — parse subsections for subject/domain granularity
        subsections = list(SUBSECTION_RE.finditer(body))
        if subsections:
            for j, sub in enumerate(subsections):
                sub_start = sub.end()
                sub_end = subsections[j + 1].start() if j + 1 < len(subsections) else len(body)
                sub_body = body[sub_start:sub_end]
                subject = sub.group("subject").strip()
                domain = sub.group("topic").strip()
                for bm in BULLET_RE.finditer(sub_body):
                    line = bm.group("text").strip()
                    if "**CHANGED**" in line:
                        continue
                    current_facts.append({
                        "chapter_num": sec_num,
                        "subject": subject,
                        "fact": line,
                        "domain": domain,
                    })
        else:
            # No subsections — generic subject
            for bm in BULLET_RE.finditer(body):
                line = bm.group("text").strip()
                if "**CHANGED**" in line:
                    continue
                current_facts.append({
                    "chapter_num": sec_num,
                    "subject": "general",
                    "fact": line,
                    "domain": "",
                })

    return {
        "current_facts": current_facts,
        "changed_facts": changed_facts,
        "extraction_method": "section_regex",
        "warnings": [],
    }


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------


def _extract_heuristic_all(text: str) -> dict[str, Any]:
    """Extract facts from a log without ## Chapter NN section headers."""
    current_facts: list[dict[str, Any]] = []
    changed_facts: list[dict[str, Any]] = []

    for m in CHANGED_RE.finditer(text):
        impacts_raw = (m.group("impacts") or "").strip()
        impacts = [s.strip() for s in impacts_raw.split(",") if s.strip()] if impacts_raw else []
        changed_facts.append({
            "chapter_num": 0,
            "subject": "general",
            "fact": m.group("new").strip(),
            "old_value": m.group("old").strip(),
            "revision_impacts": impacts,
        })

    for bm in BULLET_RE.finditer(text):
        line = bm.group("text").strip()
        if "**CHANGED**" in line or not line:
            continue
        current_facts.append({
            "chapter_num": 0,
            "subject": "general",
            "fact": line,
            "domain": "",
        })

    return {
        "current_facts": current_facts,
        "changed_facts": changed_facts,
        "extraction_method": "heuristic",
        "warnings": [
            "Log has no ## Chapter NN section headers — heuristic extraction used. "
            "chapter_num will be 0 for all imported facts."
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _subject_before(body: str, pos: int) -> str:
    """Find the nearest preceding ### Subject: topic header."""
    matches = list(SUBSECTION_RE.finditer(body[:pos]))
    return matches[-1].group("subject").strip() if matches else "unknown"


__all__ = [
    "extract_all_facts",
    "resolve_log_path",
    "CHAPTER_SECTION_RE",
    "CHANGED_RE",
    "BULLET_RE",
    "SUBSECTION_RE",
    "_subject_before",
    "_extract_structured_all",
    "_extract_heuristic_all",
]
