"""Memoir-specific scanners (Issue #61, refactored #118).

Five passes that only run when ``book_category == "memoir"``:

- ``_scan_anonymization_leak`` — real name appears despite people-profile anonymization
- ``_scan_tidy_lesson_endings`` — chapter closes on a moral instead of a moment
- ``_scan_reflective_platitudes`` — retrospective commentary density per chapter
- ``_scan_timeline_ambiguity`` — temporal hand-waving density per chapter
- ``_scan_real_people_consistency`` — same person referred to by inconsistent display forms
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from tools.analysis.manuscript.metadata import _read_people_profiles
from tools.analysis.manuscript.text_utils import (
    _make_snippet,
    _read_chapter_drafts,
    _strip_markdown,
    _tokenise,
)
from tools.analysis.manuscript.types import Finding, Occurrence
from tools.analysis.manuscript.vocabularies import (
    PLATITUDE_HIGH_THRESHOLD,
    PLATITUDE_MEDIUM_THRESHOLD,
    TIMELINE_AMBIGUITY_HIGH_PER_1K,
    TIMELINE_AMBIGUITY_MEDIUM_PER_1K,
)

# ---------------------------------------------------------------------------
# Timeline ambiguity
# ---------------------------------------------------------------------------

_TEMPORAL_VAGUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("some time later", re.compile(r"\bsome\s+time\s+later\b", re.IGNORECASE)),
    ("at some point", re.compile(r"\bat\s+some\s+point\b", re.IGNORECASE)),
    ("one day", re.compile(r"\bone\s+day\b", re.IGNORECASE)),
    ("one night", re.compile(r"\bone\s+night\b", re.IGNORECASE)),
    ("eventually", re.compile(r"\beventually\b", re.IGNORECASE)),
    ("after a while", re.compile(r"\bafter\s+a\s+while\b", re.IGNORECASE)),
    ("a while later", re.compile(r"\ba\s+while\s+later\b", re.IGNORECASE)),
    ("years later", re.compile(r"\byears\s+later\b", re.IGNORECASE)),
    ("years earlier", re.compile(r"\byears\s+earlier\b", re.IGNORECASE)),
    ("years before", re.compile(r"\byears\s+before\b", re.IGNORECASE)),
    ("years ago", re.compile(r"\byears\s+ago\b", re.IGNORECASE)),
    ("a long time ago", re.compile(r"\ba\s+long\s+time\s+ago\b", re.IGNORECASE)),
    ("back then", re.compile(r"\bback\s+then\b", re.IGNORECASE)),
    ("in those days", re.compile(r"\bin\s+those\s+days\b", re.IGNORECASE)),
    ("at that time", re.compile(r"\bat\s+that\s+time\b", re.IGNORECASE)),
    ("around that time", re.compile(r"\baround\s+that\s+time\b", re.IGNORECASE)),
    ("sometime later", re.compile(r"\bsometime\s+later\b", re.IGNORECASE)),
    ("not long after", re.compile(r"\bnot\s+long\s+after\b", re.IGNORECASE)),
    ("before long", re.compile(r"\bbefore\s+long\b", re.IGNORECASE)),
)


def _scan_timeline_ambiguity(book_path: Path) -> list[Finding]:
    """Memoir: flag chapters with excessive temporal hand-waving."""
    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    findings: list[Finding] = []
    for chapter_slug, raw_text in drafts:
        cleaned = _strip_markdown(raw_text)
        word_count = len(_tokenise(cleaned))
        if word_count < 200:
            continue

        occurrences: list[Occurrence] = []
        per_pattern_counts: dict[str, int] = defaultdict(int)

        for line_no, line in enumerate(cleaned.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            for label, pattern in _TEMPORAL_VAGUE_PATTERNS:
                for m in pattern.finditer(stripped):
                    per_pattern_counts[label] += 1
                    occurrences.append(
                        Occurrence(
                            chapter=chapter_slug,
                            line=line_no,
                            snippet=_make_snippet(stripped, m.group(0).lower()),
                        )
                    )

        if not occurrences:
            continue

        density = (len(occurrences) / word_count) * 1000.0
        if density < TIMELINE_AMBIGUITY_MEDIUM_PER_1K:
            continue

        severity = "high" if density >= TIMELINE_AMBIGUITY_HIGH_PER_1K else "medium"
        top = sorted(per_pattern_counts.items(), key=lambda kv: -kv[1])[:3]
        top_str = ", ".join(f"{label}×{n}" for label, n in top)
        phrase = f"{chapter_slug}: {top_str} ({density:.1f}/1k words)"

        findings.append(
            Finding(
                phrase=phrase,
                category="timeline_ambiguity",
                severity=severity,
                count=len(occurrences),
                occurrences=occurrences[:20],
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Reflective platitude density
# ---------------------------------------------------------------------------

_REFLECTIVE_PLATITUDE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("looking back", re.compile(r"\blooking\s+back\b", re.IGNORECASE)),
    ("in retrospect", re.compile(r"\bin\s+retrospect\b", re.IGNORECASE)),
    ("in hindsight", re.compile(r"\bin\s+hindsight\b", re.IGNORECASE)),
    ("with hindsight", re.compile(r"\bwith\s+hindsight\b", re.IGNORECASE)),
    ("I now realize", re.compile(r"\bI\s+now\s+realiz", re.IGNORECASE)),
    ("I now understand", re.compile(r"\bI\s+now\s+understand\b", re.IGNORECASE)),
    ("I now know", re.compile(r"\bI\s+now\s+know\b", re.IGNORECASE)),
    ("I realize now", re.compile(r"\bI\s+realiz\w*\s+now\b", re.IGNORECASE)),
    ("I understand now", re.compile(r"\bI\s+understand\s+now\b", re.IGNORECASE)),
    ("what I learned", re.compile(r"\bwhat\s+I\s+learned\b", re.IGNORECASE)),
    ("I came to realize", re.compile(r"\bI\s+came\s+to\s+realiz", re.IGNORECASE)),
    ("I came to understand", re.compile(r"\bI\s+came\s+to\s+understand\b", re.IGNORECASE)),
    ("I would later", re.compile(r"\bI\s+would\s+later\b", re.IGNORECASE)),
    ("it taught me", re.compile(r"\bit\s+taught\s+me\b", re.IGNORECASE)),
    ("taught me that", re.compile(r"\btaught\s+me\s+that\b", re.IGNORECASE)),
    ("I had come to", re.compile(r"\bI\s+had\s+come\s+to\b", re.IGNORECASE)),
    ("the lesson was", re.compile(r"\bthe\s+lesson\s+was\b", re.IGNORECASE)),
)


def _scan_reflective_platitudes(book_path: Path) -> list[Finding]:
    """Memoir: flag chapters heavy with retrospective lesson-summary language."""
    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    findings: list[Finding] = []
    for chapter_slug, raw_text in drafts:
        cleaned = _strip_markdown(raw_text)

        occurrences: list[Occurrence] = []
        per_pattern_counts: dict[str, int] = defaultdict(int)

        for line_no, line in enumerate(cleaned.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            for label, pattern in _REFLECTIVE_PLATITUDE_PATTERNS:
                for m in pattern.finditer(stripped):
                    per_pattern_counts[label] += 1
                    occurrences.append(
                        Occurrence(
                            chapter=chapter_slug,
                            line=line_no,
                            snippet=_make_snippet(stripped, m.group(0).lower()),
                        )
                    )

        if len(occurrences) < PLATITUDE_MEDIUM_THRESHOLD:
            continue

        severity = "high" if len(occurrences) >= PLATITUDE_HIGH_THRESHOLD else "medium"
        top = sorted(per_pattern_counts.items(), key=lambda kv: -kv[1])[:3]
        top_str = ", ".join(f"{label}×{n}" for label, n in top)
        phrase = f"{chapter_slug}: {top_str} ({len(occurrences)} hits)"

        findings.append(
            Finding(
                phrase=phrase,
                category="reflective_platitude",
                severity=severity,
                count=len(occurrences),
                occurrences=occurrences[:20],
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Tidy lesson endings
# ---------------------------------------------------------------------------

_LESSON_ENDING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bI\s+(?:had\s+)?learned\b", re.IGNORECASE),
    re.compile(r"\btaught\s+me\b", re.IGNORECASE),
    re.compile(r"\bmade\s+me\s+realiz", re.IGNORECASE),
    re.compile(r"\bhelped\s+me\s+(?:realiz|understand|see)\b", re.IGNORECASE),
    re.compile(r"\bshowed\s+me\s+that\b", re.IGNORECASE),
    re.compile(r"\bmade\s+me\s+understand\b", re.IGNORECASE),
    re.compile(r"\bI\s+(?:had\s+)?come\s+to\s+understand\b", re.IGNORECASE),
    re.compile(r"\bI\s+now\s+(?:understood|knew)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+I\s+came\s+away\s+with\b", re.IGNORECASE),
    re.compile(r"\bchanged\s+(?:the\s+way\s+I|me\s+forever|everything)\b", re.IGNORECASE),
    re.compile(r"\bI\s+would\s+never\s+(?:forget|be\s+the\s+same)\b", re.IGNORECASE),
    re.compile(r"\bthe\s+lesson\s+(?:I|was|here)\b", re.IGNORECASE),
)


def _last_paragraph(text: str) -> str:
    """Return the last non-empty paragraph of a text block."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return paragraphs[-1] if paragraphs else ""


def _scan_tidy_lesson_endings(book_path: Path) -> list[Finding]:
    """Memoir: flag chapters whose final paragraph closes on a moral or lesson summary."""
    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    findings: list[Finding] = []
    for chapter_slug, raw_text in drafts:
        cleaned = _strip_markdown(raw_text)
        last_para = _last_paragraph(cleaned)
        if not last_para or len(last_para.split()) < 10:
            continue

        hits: list[str] = []
        for pattern in _LESSON_ENDING_PATTERNS:
            for m in pattern.finditer(last_para):
                hits.append(m.group(0))

        if len(hits) < 2:
            continue

        severity = "high" if len(hits) >= 3 else "medium"
        snippet = last_para[:200].rstrip()
        if len(last_para) > 200:
            snippet += "…"

        findings.append(
            Finding(
                phrase=f"{chapter_slug}: chapter ends on lesson-summary language",
                category="tidy_lesson_ending",
                severity=severity,
                count=len(hits),
                occurrences=[Occurrence(chapter=chapter_slug, line=0, snippet=snippet)],
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Anonymization leak
# ---------------------------------------------------------------------------


def _scan_anonymization_leak(book_path: Path) -> list[Finding]:
    """Memoir: flag draft chapters that contain a person's real name despite anonymization."""
    people = _read_people_profiles(book_path)
    anon_people = [p for p in people if p["anonymization"] != "none" and p["real_name"]]
    if not anon_people:
        return []

    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    findings: list[Finding] = []
    for person in anon_people:
        real_name = person["real_name"]
        display_name = person["name"]
        pattern = re.compile(r"\b" + re.escape(real_name) + r"\b", re.IGNORECASE)

        occurrences: list[Occurrence] = []
        for chapter_slug, raw_text in drafts:
            cleaned = _strip_markdown(raw_text)
            for line_no, line in enumerate(cleaned.splitlines(), start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                for m in pattern.finditer(stripped):
                    occurrences.append(
                        Occurrence(
                            chapter=chapter_slug,
                            line=line_no,
                            snippet=_make_snippet(stripped, m.group(0).lower()),
                        )
                    )

        if occurrences:
            findings.append(
                Finding(
                    phrase=f'real name "{real_name}" (pseudonym: "{display_name}")',
                    category="anonymization_leak",
                    severity="high",
                    count=len(occurrences),
                    occurrences=sorted(occurrences, key=lambda o: (o.chapter, o.line)),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Real-people name consistency
# ---------------------------------------------------------------------------


def _scan_real_people_consistency(book_path: Path) -> list[Finding]:
    """Memoir: flag inconsistent capitalisation/form of a person's display name."""
    people = _read_people_profiles(book_path)
    if not people:
        return []

    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    findings: list[Finding] = []

    for person in people:
        display_name = person["name"]
        if not display_name or len(display_name) < 2:
            continue

        forms_found: dict[str, list[Occurrence]] = defaultdict(list)
        name_pattern = re.compile(r"\b" + re.escape(display_name) + r"\b", re.IGNORECASE)

        for chapter_slug, raw_text in drafts:
            cleaned = _strip_markdown(raw_text)
            for line_no, line in enumerate(cleaned.splitlines(), start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                for m in name_pattern.finditer(stripped):
                    matched_form = m.group(0)  # preserve original case
                    forms_found[matched_form].append(
                        Occurrence(
                            chapter=chapter_slug,
                            line=line_no,
                            snippet=_make_snippet(stripped, matched_form.lower()),
                        )
                    )

        if len(forms_found) <= 1:
            continue

        forms_str = ", ".join(f'"{f}"' for f in sorted(forms_found.keys()))
        all_occurrences = [occ for occs in forms_found.values() for occ in occs]
        findings.append(
            Finding(
                phrase=f'"{display_name}": multiple forms found — {forms_str}',
                category="real_people_consistency",
                severity="medium",
                count=len(forms_found),
                occurrences=sorted(all_occurrences, key=lambda o: (o.chapter, o.line))[:10],
            )
        )
    return findings


__all__ = [
    "_scan_anonymization_leak",
    "_scan_real_people_consistency",
    "_scan_reflective_platitudes",
    "_scan_tidy_lesson_endings",
    "_scan_timeline_ambiguity",
]
