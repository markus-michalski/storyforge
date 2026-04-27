"""Review brief assembler — Issue #99.

Bundles the pre-computed state reads that ``chapter-reviewer`` used to
do by hand (timeline, travel matrix, canon log, tone, chapter timelines)
into a single structured JSON brief.

Design follows ``chapter_writing_brief.py`` (Issue #78):
- Each sub-component is wrapped in try/except via _Recorder.
- Output is plain dicts/lists/strings — JSON-serializable.
- No I/O outside the book root. Skill prompts consume the brief directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.analysis.timeline_validator import parse_plot_timeline
from tools.state.chapter_timeline_parser import parse_chapter_timeline_grid


# ---------------------------------------------------------------------------
# Error recorder (mirrors chapter_writing_brief._Recorder)
# ---------------------------------------------------------------------------


@dataclass
class _Recorder:
    """Collects sub-tool errors so the brief can ship with partial data."""

    errors: list[dict[str, str]]

    def run(self, component: str, fn, default):
        try:
            return fn()
        except Exception as exc:  # pylint: disable=broad-except
            self.errors.append({
                "component": component,
                "error": f"{type(exc).__name__}: {exc}",
            })
            return default


# ---------------------------------------------------------------------------
# Shared markdown table helpers (also used by continuity_brief)
# ---------------------------------------------------------------------------

_SEPARATOR_ROW_RE = re.compile(r"^\|[\s|:-]+\|\s*$")


def _split_cells(row: str) -> list[str]:
    """Split a markdown table row into trimmed cell values."""
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _is_placeholder_row(cells: list[str]) -> bool:
    """Return True if every non-empty cell looks like a template placeholder."""
    non_empty = [c for c in cells if c]
    return bool(non_empty) and all(c.startswith("*") for c in non_empty)


# ---------------------------------------------------------------------------
# Travel Matrix parser (shared with continuity_brief)
# ---------------------------------------------------------------------------

_TRAVEL_MATRIX_SECTION_RE = re.compile(
    r"##\s+Travel Matrix\b(.*?)(?=\n##\s|\Z)",
    re.DOTALL | re.IGNORECASE,
)


def _parse_travel_matrix(setting_text: str) -> list[dict[str, str]]:
    """Parse the Travel Matrix table from world/setting.md.

    Returns a list of route dicts with normalised keys derived from the
    header row (e.g. ``from``, ``to``, ``distance``, ``transport``,
    ``travel_time``, ``notes``). Placeholder rows and the template example
    row are skipped.
    """
    match = _TRAVEL_MATRIX_SECTION_RE.search(setting_text)
    if not match:
        return []

    rows: list[dict[str, str]] = []
    header: list[str] | None = None

    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if _SEPARATOR_ROW_RE.match(stripped):
            continue
        cells = _split_cells(stripped)
        if not cells:
            continue
        if header is None:
            header = [
                re.sub(r"\s+", "_", c.lower()) for c in cells
            ]
            continue
        if _is_placeholder_row(cells):
            continue
        row: dict[str, str] = {
            header[i]: cells[i] if i < len(cells) else ""
            for i in range(len(header))
        }
        rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Canon log facts parser (shared with continuity_brief)
# ---------------------------------------------------------------------------

_ESTABLISHED_FACTS_RE = re.compile(
    r"##\s+Established Facts\b(.*?)(?=\n##\s|\Z)",
    re.DOTALL | re.IGNORECASE,
)
_SUB_SECTION_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)


def _parse_canon_log_facts(canon_text: str) -> list[dict[str, str]]:
    """Parse facts from plot/canon-log.md into a flat list.

    Scans only the ``## Established Facts`` section. Each table row
    becomes a dict with keys: ``fact``, ``established_in``, ``status``,
    ``notes``, ``domain``. Placeholder rows and header rows are skipped.
    """
    match = _ESTABLISHED_FACTS_RE.search(canon_text)
    if not match:
        return []

    section_text = match.group(1)
    facts: list[dict[str, str]] = []
    current_domain = ""

    for line in section_text.splitlines():
        stripped = line.strip()
        # Track domain sub-sections (### Character Facts, etc.)
        domain_match = _SUB_SECTION_RE.match(stripped)
        if domain_match:
            current_domain = domain_match.group(1)
            continue
        if not stripped.startswith("|"):
            continue
        if _SEPARATOR_ROW_RE.match(stripped):
            continue
        cells = _split_cells(stripped)
        if not cells or not cells[0]:
            continue
        # Skip header row
        if cells[0].lower() in ("fact", "field"):
            continue
        if cells[0].startswith("*"):
            continue
        facts.append({
            "fact": cells[0],
            "established_in": cells[1] if len(cells) > 1 else "",
            "status": cells[2] if len(cells) > 2 else "ACTIVE",
            "notes": cells[3] if len(cells) > 3 else "",
            "domain": current_domain,
        })

    return facts


# ---------------------------------------------------------------------------
# Tonal rules parser (review brief only)
# ---------------------------------------------------------------------------

_BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<body>.+?)\s*$", re.MULTILINE)
_NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+(?P<body>.+?)\s*$", re.MULTILINE)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

_NON_NEG_SECTION_RE = re.compile(
    r"^##\s+Non-Negotiable Rules\s*$(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
_LITMUS_SECTION_RE = re.compile(
    r"^##\s+Litmus Test\s*$(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
_BANNED_PATTERNS_RE = re.compile(
    r"^##\s+Banned Prose Patterns.*?$(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
_TONAL_ARC_SECTION_RE = re.compile(
    r"^##\s+Tonal Arc\s*$(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)


def _bullets_from_section(text: str, section_re: re.Pattern) -> list[str]:
    match = section_re.search(text)
    if not match:
        return []
    body = _COMMENT_RE.sub("", match.group(1))
    items = []
    for m in _BULLET_RE.finditer(body):
        item = re.sub(r"\s+", " ", m.group("body")).strip()
        if item:
            items.append(item)
    return items


def _numbered_or_bullets_from_section(text: str, section_re: re.Pattern) -> list[str]:
    match = section_re.search(text)
    if not match:
        return []
    body = match.group(1)
    items: list[str] = []
    for pat in (_NUMBERED_RE, _BULLET_RE):
        for m in pat.finditer(body):
            item = re.sub(r"\s+", " ", m.group("body")).strip()
            if item and item not in items:
                items.append(item)
    return items


def _parse_tonal_arc_warning_signs(tone_text: str) -> list[str]:
    """Extract Warning Signs column values from the Tonal Arc table."""
    match = _TONAL_ARC_SECTION_RE.search(tone_text)
    if not match:
        return []

    section = match.group(1)
    header: list[str] | None = None
    warning_idx: int | None = None
    warnings: list[str] = []

    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if _SEPARATOR_ROW_RE.match(stripped):
            continue
        cells = _split_cells(stripped)
        if header is None:
            header = [c.lower() for c in cells]
            for i, h in enumerate(header):
                if "warning" in h:
                    warning_idx = i
                    break
            continue
        if warning_idx is not None and warning_idx < len(cells):
            val = cells[warning_idx].strip()
            if val and not val.startswith("*"):
                warnings.append(val)

    return warnings


def _parse_tonal_rules(tone_text: str) -> dict[str, list[str]]:
    """Parse plot/tone.md into structured tonal rule sections."""
    return {
        "non_negotiable_rules": _bullets_from_section(tone_text, _NON_NEG_SECTION_RE),
        "litmus_test": _numbered_or_bullets_from_section(tone_text, _LITMUS_SECTION_RE),
        "banned_prose_patterns": _bullets_from_section(tone_text, _BANNED_PATTERNS_RE),
        "warning_signs": _parse_tonal_arc_warning_signs(tone_text),
    }


# ---------------------------------------------------------------------------
# Book CLAUDE.md rules + callbacks (shared logic)
# ---------------------------------------------------------------------------

_RULES_SECTION_RE = re.compile(
    r"^##\s+Rules\s*$(.*?)^##\s+",
    re.MULTILINE | re.DOTALL,
)
_CALLBACKS_SECTION_RE = re.compile(
    r"^##\s+Callback Register\s*$(.*?)(?=^---\s*$|\Z)",
    re.MULTILINE | re.DOTALL,
)
_BAN_CUE_RE = re.compile(
    r"\b(banned|ban|avoid|never|don['']?t\s+use|do\s+not\s+use|"
    r"limit|stop\s+using)\b",
    re.IGNORECASE,
)


def _classify_rule(rule: str) -> str:
    if "`" in rule and _BAN_CUE_RE.search(rule):
        return "block"
    return "advisory"


def _section_bullets(text: str, section_re: re.Pattern) -> list[str]:
    match = section_re.search(text)
    if not match:
        return []
    body = _COMMENT_RE.sub("", match.group(1))
    items = []
    for m in _BULLET_RE.finditer(body):
        item = re.sub(r"\s+", " ", m.group("body")).strip()
        if item:
            items.append(item)
    return items


def _load_book_rules_and_callbacks(
    book_root: Path,
    recorder: _Recorder,
) -> tuple[list[dict[str, str]], list[str]]:
    """Extract active_rules and active_callbacks from book CLAUDE.md."""
    rules: list[dict[str, str]] = []
    callbacks: list[str] = []
    claudemd_path = book_root / "CLAUDE.md"
    if not claudemd_path.is_file():
        return rules, callbacks

    text = recorder.run(
        "claudemd.read",
        lambda: claudemd_path.read_text(encoding="utf-8"),
        "",
    )
    if not text:
        return rules, callbacks

    for rule_text in _section_bullets(text, _RULES_SECTION_RE):
        rules.append({"text": rule_text, "severity": _classify_rule(rule_text)})
    callbacks = _section_bullets(text, _CALLBACKS_SECTION_RE)
    return rules, callbacks


# ---------------------------------------------------------------------------
# Chapter directory helpers (inlined to avoid private imports)
# ---------------------------------------------------------------------------

_CHAPTER_NUM_RE = re.compile(r"^(\d{1,3})-")


def _sorted_chapter_dirs(book_root: Path) -> list[tuple[int, Path]]:
    """List all numbered chapter directories sorted by chapter number."""
    chapters_dir = book_root / "chapters"
    if not chapters_dir.is_dir():
        return []
    out: list[tuple[int, Path]] = []
    for entry in chapters_dir.iterdir():
        if not entry.is_dir():
            continue
        m = _CHAPTER_NUM_RE.match(entry.name)
        if not m:
            continue
        out.append((int(m.group(1)), entry))
    out.sort(key=lambda pair: pair[0])
    return out


def _find_previous_chapter_dir(book_root: Path, chapter_slug: str) -> Path | None:
    """Return the chapter directory that immediately precedes chapter_slug."""
    all_chapters = _sorted_chapter_dirs(book_root)
    current_num: int | None = None
    for num, path in all_chapters:
        if path.name == chapter_slug:
            current_num = num
            break
    if current_num is None:
        return None
    preceding = [p for num, p in all_chapters if num < current_num]
    return preceding[-1] if preceding else None


# ---------------------------------------------------------------------------
# Public assembler
# ---------------------------------------------------------------------------


def build_review_brief(
    *,
    book_root: Path,
    book_slug: str,
    chapter_slug: str,
) -> dict[str, Any]:
    """Assemble the chapter-review brief — Issue #99.

    Bundles timeline, travel matrix, canon log, tonal rules, and chapter
    timeline sections into a single JSON-serializable dict.
    ``chapter-reviewer`` calls this once instead of reading 6+ project-state
    files by hand.

    Args:
        book_root: Absolute path to the book project directory.
        book_slug: Book identifier.
        chapter_slug: Target chapter identifier (e.g. "22-the-night-before").

    Returns dict with:
        chapter_timeline        — start/end/scenes for the target chapter
        previous_chapter_timeline — same for the preceding chapter (or None)
        canonical_timeline_entries — parsed plot/timeline.md events
        travel_matrix           — parsed world/setting.md Travel Matrix rows
        canon_log_facts         — parsed plot/canon-log.md Established Facts
        tonal_rules             — non-negotiable rules, litmus, banned patterns
        active_rules            — book CLAUDE.md ## Rules, structured
        active_callbacks        — book CLAUDE.md ## Callback Register items
        errors                  — component → error map for graceful degrade
    """
    recorder = _Recorder(errors=[])
    chapters_dir = book_root / "chapters"
    chapter_dir = chapters_dir / chapter_slug

    # ----- chapter timeline -------------------------------------------------
    chapter_timeline = recorder.run(
        "chapter_timeline",
        lambda: _chapter_grid_or_none(chapter_dir),
        None,
    )

    # ----- previous chapter timeline ----------------------------------------
    prev_dir = recorder.run(
        "previous_chapter.find",
        lambda: _find_previous_chapter_dir(book_root, chapter_slug),
        None,
    )
    previous_chapter_timeline: dict[str, Any] | None = None
    if prev_dir is not None:
        previous_chapter_timeline = recorder.run(
            "previous_chapter_timeline",
            lambda d=prev_dir: _chapter_grid_or_none(d),
            None,
        )

    # ----- canonical timeline entries ---------------------------------------
    canonical_timeline_entries: list[dict[str, Any]] = []
    calendar = recorder.run(
        "canonical_timeline",
        lambda: parse_plot_timeline(book_root),
        None,
    )
    if calendar is not None:
        canonical_timeline_entries = [e.to_dict() for e in calendar.events]

    # ----- travel matrix ----------------------------------------------------
    travel_matrix: list[dict[str, str]] = []
    setting_path = book_root / "world" / "setting.md"
    if setting_path.is_file():
        setting_text = recorder.run(
            "setting.read",
            lambda: setting_path.read_text(encoding="utf-8"),
            "",
        )
        if setting_text:
            travel_matrix = recorder.run(
                "travel_matrix",
                lambda: _parse_travel_matrix(setting_text),
                [],
            )

    # ----- canon log facts --------------------------------------------------
    canon_log_facts: list[dict[str, str]] = []
    canon_path = book_root / "plot" / "canon-log.md"
    if canon_path.is_file():
        canon_text = recorder.run(
            "canon_log.read",
            lambda: canon_path.read_text(encoding="utf-8"),
            "",
        )
        if canon_text:
            canon_log_facts = recorder.run(
                "canon_log_facts",
                lambda: _parse_canon_log_facts(canon_text),
                [],
            )

    # ----- tonal rules ------------------------------------------------------
    tonal_rules: dict[str, list[str]] = {}
    tone_path = book_root / "plot" / "tone.md"
    if tone_path.is_file():
        tone_text = recorder.run(
            "tone.read",
            lambda: tone_path.read_text(encoding="utf-8"),
            "",
        )
        if tone_text:
            tonal_rules = recorder.run(
                "tonal_rules",
                lambda: _parse_tonal_rules(tone_text),
                {},
            )

    # ----- rules + callbacks from book CLAUDE.md ----------------------------
    active_rules, active_callbacks = _load_book_rules_and_callbacks(
        book_root, recorder
    )

    return {
        "book_slug": book_slug,
        "chapter_slug": chapter_slug,
        "chapter_timeline": chapter_timeline,
        "previous_chapter_timeline": previous_chapter_timeline,
        "canonical_timeline_entries": canonical_timeline_entries,
        "travel_matrix": travel_matrix,
        "canon_log_facts": canon_log_facts,
        "tonal_rules": tonal_rules,
        "active_rules": active_rules,
        "active_callbacks": active_callbacks,
        "errors": list(recorder.errors),
    }


def _chapter_grid_or_none(chapter_dir: Path) -> dict[str, Any] | None:
    """Load a chapter's timeline grid as a dict, or None if not parseable."""
    grid = parse_chapter_timeline_grid(chapter_dir)
    return grid.to_dict() if grid is not None else None
