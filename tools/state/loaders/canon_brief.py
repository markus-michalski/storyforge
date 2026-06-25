"""Canon-log projector for the chapter-writing brief (Issue #161).

Replaces the direct ``Read('plot/canon-log.md')`` in ``chapter-writer`` Step 1
with a deterministic projector that returns only the facts relevant to the
chapter being written — bounded by the last N review-or-later chapters — plus
all CHANGED entries (which can affect any downstream chapter regardless of age).

For memoir books the same projector reads ``plot/people-log.md``.

Extraction priority:

1. **section_regex** — ``## Chapter NN`` section headers are parsed
   deterministically.  Sub-section subjects (``### Subject: topic``) are
   used for the POV-relevant filter.  ``**CHANGED**`` markers inside any
   section are pulled into ``changed_facts``.
2. **heuristic** — Legacy logs without section headers: the log is split on
   a best-effort "chapter boundary" heuristic (any line that starts with
   ``##`` or a chapter-number indicator) and bullet points are extracted.
   ``warnings`` flag that the extractions are imprecise.
3. **none** — File missing or empty; ``warnings`` tell the skill to surface
   the gap rather than invent facts.

Schema returned
---------------
::

    {
      "current_facts": [
        {"fact": "...", "chapter": "01-title", "source": "chapter:01-title:canon-log:Theo:locations"}
      ],
      "changed_facts": [
        {
          "old": "...", "new": "...",
          "chapter": "14-the-fight",
          "source": "chapter:14-the-fight:canon-log:CHANGED:Theo:skills",
          "revision_impact": ["15-aftermath", "17-the-school"]
        }
      ],
      "pov_relevant_facts": [...],   # subset of current_facts filtered on POV name
      "scanned_chapters": [1, 8, 14],
      "as_of": "26-the-basement",
      "extraction_method": "section_regex" | "heuristic" | "none",
      "warnings": []
    }
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from tools.db.canon_facts import query_facts
from tools.db.connection import get_book_num, get_db_slug_for_book, open_canon_db
from tools.state.parsers import _chapter_rank, parse_chapter_readme


# ---------------------------------------------------------------------------
# Regexes
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
CHANGED_RE = re.compile(
    r"^\s*[-*]\s*\*\*CHANGED\*\*\s*:\s*(?P<old>[^→\n]+?)\s*→\s*(?P<new>[^(\n]+?)"
    r"(?:\s*\(revision_impact\s*:\s*(?P<impacts>[^)]+)\))?\s*$",
    re.MULTILINE,
)

# Bullet point: "- Some fact."
BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<text>[^\n]+)", re.MULTILINE)

# Heuristic chapter boundary — lines that look like a chapter header
HEURISTIC_BOUNDARY_RE = re.compile(
    r"^#{1,3}\s+(?:Chapter\s+\d+|Ch\s+\d+|\d+[.)\-]\s)",
    re.MULTILINE | re.IGNORECASE,
)

_REVIEW_RANK_THRESHOLD = 2
_CHAPTER_DIR_RE = re.compile(r"^(?P<num>\d{1,3})-")
_DEFAULT_SCOPE = 8


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _load_db_facts(
    book_root: Path,
    current_num: int,
    scope_chapters: int,
) -> dict[str, list[dict[str, Any]]]:
    """Query canon_facts table and return facts in the brief schema.

    Returns ``{"current": [...], "changed": [...]}`` — empty lists on any
    DB error so the caller can continue with the Markdown path.

    current_facts are bounded by the scope window (lower bound:
    ``current_num - scope_chapters``).  changed facts (is_revision=True)
    are always included regardless of scope, mirroring the MD CHANGED rule.
    """
    if not (book_root / "README.md").is_file():
        return {"current": [], "changed": []}

    try:
        book_num = get_book_num(book_root)
        db_slug = get_db_slug_for_book(book_root)
        conn = open_canon_db(db_slug)
        try:
            rows = query_facts(
                conn, book_num=book_num, up_to_chapter=max(0, current_num - 1)
            )
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return {"current": [], "changed": []}

    scope_min = max(1, current_num - scope_chapters) if scope_chapters > 0 else 1
    current: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []

    for row in rows:
        ch_num = row["chapter_num"]
        subject = row.get("subject", "")
        fact = row["fact"]
        domain = row.get("domain", "")

        if row["is_revision"]:
            raw = row.get("revision_impacts") or ""
            try:
                impacts = json.loads(raw) if raw else []
            except (ValueError, TypeError):
                impacts = []
            changed.append({
                "old": row.get("old_value") or "",
                "new": fact,
                "chapter": str(ch_num),
                "source": f"chapter:{ch_num}:db:CHANGED:{subject}",
                "revision_impact": impacts,
            })
        elif ch_num >= scope_min:
            source = f"chapter:{ch_num}:db:{subject}"
            if domain:
                source = f"{source}:{domain}"
            current.append({
                "fact": fact,
                "chapter": str(ch_num),
                "source": source,
            })

    return {"current": current, "changed": changed}


def build_canon_brief(
    book_root: Path,
    chapter_slug: str,
    pov_character: str = "",
    *,
    book_category: str = "fiction",
    scope_chapters: int = _DEFAULT_SCOPE,
) -> dict[str, Any]:
    """Project canon facts into a bounded, structured brief.

    Queries the ``canon_facts`` SQLite table first (Issue #291), then reads
    the Markdown log as a supplementary archive.  Both sources are merged
    so that facts added via ``add_canon_fact()`` are visible to the
    chapter-writer alongside historical facts stored in the log file.

    Args:
        book_root: Project root containing ``plot/``.
        chapter_slug: Chapter being written — defines the scope window.
        pov_character: Display name of the POV character for ``pov_relevant_facts``.
        book_category: ``"fiction"`` (reads ``canon-log.md``) or ``"memoir"``
            (reads ``people-log.md``).
        scope_chapters: How many review-or-later chapters before the current
            one to include in ``current_facts``.

    Returns:
        Structured canon brief dict.
    """
    current_num = _chapter_number(chapter_slug)
    pov_name_lower = pov_character.lower().strip() if pov_character else ""

    # --- Step 1: DB path ---
    db_result = _load_db_facts(book_root, current_num, scope_chapters)
    has_db = bool(db_result["current"] or db_result["changed"])

    # --- Step 2: Markdown path ---
    log_path = _resolve_log_path(book_root, book_category)
    log_name = "people-log.md" if book_category == "memoir" else "canon-log.md"

    md_current: list[dict[str, Any]] = []
    md_changed: list[dict[str, Any]] = []
    scanned_chapters: list[int] = []
    as_of: str | None = None
    md_extraction: str = "none"
    warnings: list[str] = []

    if not log_path.is_file():
        if not has_db:
            return _empty(f"{log_name} not found")
        md_extraction = "none"
    else:
        try:
            text = log_path.read_text(encoding="utf-8")
        except OSError as exc:
            if not has_db:
                return _empty(f"could not read log: {exc}")
            text = ""

        if not text.strip():
            if not has_db:
                return _empty("log file is empty")
        else:
            chapters_dir = book_root / "chapters"
            scope_nums = _scope_chapter_numbers(chapters_dir, current_num, scope_chapters)
            sections = list(CHAPTER_SECTION_RE.finditer(text))

            if sections:
                md_out = _extract_structured(
                    text, sections, scope_nums, current_num, pov_character
                )
            else:
                md_out = _extract_heuristic(text, pov_character)

            md_current = md_out["current_facts"]
            md_changed = md_out["changed_facts"]
            scanned_chapters = md_out["scanned_chapters"]
            as_of = md_out["as_of"]
            warnings = md_out["warnings"]
            md_extraction = md_out["extraction_method"]

    # --- Step 3: Merge ---
    current_facts = db_result["current"] + md_current
    changed_facts = db_result["changed"] + md_changed
    pov_facts = _filter_pov(current_facts, pov_name_lower)

    if md_extraction == "none":
        extraction_method = "db" if has_db else "none"
    elif has_db:
        extraction_method = f"db+{md_extraction}"
    else:
        extraction_method = md_extraction

    # Ensure pov_character warning is present exactly once when needed
    if not pov_name_lower and not any("pov_character" in w for w in warnings):
        warnings = warnings + _pov_warnings(pov_name_lower)

    return {
        "current_facts": current_facts,
        "changed_facts": changed_facts,
        "pov_relevant_facts": pov_facts,
        "scanned_chapters": scanned_chapters,
        "as_of": as_of,
        "extraction_method": extraction_method,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Structured extraction (section_regex)
# ---------------------------------------------------------------------------


def _extract_structured(
    text: str,
    sections: list[re.Match[str]],
    scope_nums: set[int],
    current_num: int,
    pov_character: str,
) -> dict[str, Any]:
    current_facts: list[dict[str, Any]] = []
    changed_facts: list[dict[str, Any]] = []
    scanned: list[int] = []

    pov_name_lower = pov_character.lower().strip() if pov_character else ""

    for i, sec in enumerate(sections):
        sec_num = int(sec.group("num"))
        if sec_num >= current_num:
            continue  # Never include facts from the current or future chapter

        # Body runs until the next section or EOF.
        body_start = sec.end()
        body_end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        body = text[body_start:body_end]

        # Always collect CHANGED entries regardless of scope.
        for m in CHANGED_RE.finditer(body):
            impacts_raw = (m.group("impacts") or "").strip()
            impacts = [s.strip() for s in impacts_raw.split(",") if s.strip()] if impacts_raw else []
            # Infer subject from enclosing subsection header when possible.
            subject = _subject_before(body, m.start())
            changed_facts.append(
                {
                    "old": m.group("old").strip(),
                    "new": m.group("new").strip(),
                    "chapter": _slug_from_sec(sec),
                    "source": f"chapter:{_slug_from_sec(sec)}:canon-log:CHANGED:{subject}",
                    "revision_impact": impacts,
                }
            )

        # current_facts are bounded by scope.
        if sec_num not in scope_nums:
            continue
        scanned.append(sec_num)

        # Parse subsections for granular source pointers.
        subsections = list(SUBSECTION_RE.finditer(body))
        if subsections:
            for j, sub in enumerate(subsections):
                sub_body_start = sub.end()
                sub_body_end = subsections[j + 1].start() if j + 1 < len(subsections) else len(body)
                sub_body = body[sub_body_start:sub_body_end]
                subject = sub.group("subject").strip()
                topic = sub.group("topic").strip()
                for bm in BULLET_RE.finditer(sub_body):
                    line = bm.group("text").strip()
                    if "**CHANGED**" in line:
                        continue  # Already captured above
                    source = f"chapter:{_slug_from_sec(sec)}:canon-log:{subject}:{topic}"
                    current_facts.append(
                        {"fact": line, "chapter": _slug_from_sec(sec), "source": source}
                    )
        else:
            # No subsections — collect all non-CHANGED bullets with a generic source.
            for bm in BULLET_RE.finditer(body):
                line = bm.group("text").strip()
                if "**CHANGED**" in line:
                    continue
                source = f"chapter:{_slug_from_sec(sec)}:canon-log"
                current_facts.append(
                    {"fact": line, "chapter": _slug_from_sec(sec), "source": source}
                )

    pov_facts = _filter_pov(current_facts, pov_name_lower)
    as_of = _as_of(scanned)

    return {
        "current_facts": current_facts,
        "changed_facts": changed_facts,
        "pov_relevant_facts": pov_facts,
        "scanned_chapters": sorted(scanned),
        "as_of": as_of,
        "extraction_method": "section_regex",
        "warnings": _pov_warnings(pov_name_lower),
    }


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------


def _extract_heuristic(text: str, pov_character: str) -> dict[str, Any]:
    pov_name_lower = pov_character.lower().strip() if pov_character else ""
    facts: list[dict[str, Any]] = []
    changed_facts: list[dict[str, Any]] = []

    for m in CHANGED_RE.finditer(text):
        impacts_raw = (m.group("impacts") or "").strip()
        impacts = [s.strip() for s in impacts_raw.split(",") if s.strip()] if impacts_raw else []
        changed_facts.append(
            {
                "old": m.group("old").strip(),
                "new": m.group("new").strip(),
                "chapter": None,
                "source": "canon-log:CHANGED:heuristic",
                "revision_impact": impacts,
            }
        )

    for bm in BULLET_RE.finditer(text):
        line = bm.group("text").strip()
        if "**CHANGED**" in line or not line:
            continue
        facts.append({"fact": line, "chapter": None, "source": "canon-log:heuristic"})

    pov_facts = _filter_pov(facts, pov_name_lower)

    warnings = [
        "canon-log.md has no ## Chapter NN section headers — extraction is imprecise. "
        "Migrate to the section convention in templates/canon-log.md for reliable results."
    ]
    warnings.extend(_pov_warnings(pov_name_lower))

    return {
        "current_facts": facts,
        "changed_facts": changed_facts,
        "pov_relevant_facts": pov_facts,
        "scanned_chapters": [],
        "as_of": None,
        "extraction_method": "heuristic",
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_log_path(book_root: Path, book_category: str) -> Path:
    if book_category == "memoir":
        return book_root / "plot" / "people-log.md"
    return book_root / "plot" / "canon-log.md"


def _chapter_number(chapter_slug: str) -> int:
    m = _CHAPTER_DIR_RE.match(chapter_slug)
    return int(m.group("num")) if m else 0


def _scope_chapter_numbers(
    chapters_dir: Path,
    current_num: int,
    scope: int,
) -> set[int]:
    """Return chapter numbers of the last ``scope`` review-or-later chapters
    strictly before ``current_num``."""
    if not chapters_dir.is_dir():
        return set()
    candidates: list[tuple[int, Path]] = []
    for entry in chapters_dir.iterdir():
        if not entry.is_dir():
            continue
        m = _CHAPTER_DIR_RE.match(entry.name)
        if not m:
            continue
        num = int(m.group("num"))
        if num >= current_num:
            continue
        if _is_review_or_later(entry):
            candidates.append((num, entry))
    candidates.sort(key=lambda p: p[0])
    return {num for num, _ in candidates[-scope:]}


def _is_review_or_later(chapter_dir: Path) -> bool:
    readme = chapter_dir / "README.md"
    if not readme.is_file():
        return False
    try:
        meta = parse_chapter_readme(readme)
    except Exception:  # pylint: disable=broad-except
        return False
    return _chapter_rank(str(meta.get("status", "Outline"))) >= _REVIEW_RANK_THRESHOLD


def _slug_from_sec(sec: re.Match[str]) -> str:
    """Extract a display-slug from the section header line."""
    line = sec.group(0)
    # "## Chapter 14 — The Fight" → "14-the-fight"
    num = sec.group("num")
    # Remove leading "## Chapter NN" and optional " — "
    title_part = re.sub(r"^##\s+Chapter\s+\d+\s*[—\-–]?\s*", "", line).strip()
    if title_part:
        slug_title = re.sub(r"[^a-z0-9]+", "-", title_part.lower()).strip("-")
        return f"{int(num):02d}-{slug_title}"
    return f"{int(num):02d}"


def _subject_before(body: str, pos: int) -> str:
    """Find the nearest preceding ### Subject: topic header."""
    prefix = body[:pos]
    m = None
    for m in SUBSECTION_RE.finditer(prefix):
        pass
    return m.group("subject").strip() if m else "unknown"


def _filter_pov(facts: list[dict[str, Any]], pov_name_lower: str) -> list[dict[str, Any]]:
    if not pov_name_lower:
        return []
    # Match on each significant token (≥3 chars) with word-boundary semantics.
    # Whole-string substring match fails for "Theo Wilkons" because source
    # pointers and bullet text use first-name only ("### Theo: cognition").
    # OR-semantics: a fact qualifies when ANY token matches — intentional, because
    # canon logs reference characters by first name only, making AND too strict.
    tokens = [t for t in pov_name_lower.split() if len(t) >= 3]
    if not tokens:
        # Short single-name characters ("Bo", "Li") — fall back to substring match
        # so they aren't silently excluded.
        return [
            f for f in facts
            if pov_name_lower in f.get("source", "").lower()
            or pov_name_lower in f.get("fact", "").lower()
        ]
    patterns = [re.compile(rf"\b{re.escape(t)}\b", re.IGNORECASE) for t in tokens]
    return [
        f for f in facts
        if any(
            p.search(f.get("source", "")) or p.search(f.get("fact", ""))
            for p in patterns
        )
    ]


def _pov_warnings(pov_name_lower: str) -> list[str]:
    """Surface a warning when pov_character is missing so the skill knows
    why pov_relevant_facts is empty (Issue #165 side observation)."""
    if not pov_name_lower:
        return [
            "pov_character not set on chapter — pov_relevant_facts cannot be filtered. "
            "Add pov_character to the chapter README frontmatter."
        ]
    return []


def _as_of(scanned: list[int]) -> str | None:
    return str(max(scanned)) if scanned else None


def _empty(warning: str) -> dict[str, Any]:
    return {
        "current_facts": [],
        "changed_facts": [],
        "pov_relevant_facts": [],
        "scanned_chapters": [],
        "as_of": None,
        "extraction_method": "none",
        "warnings": [warning],
    }


__all__ = ["build_canon_brief"]
