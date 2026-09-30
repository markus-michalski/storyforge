"""Deterministic pre-scan for the chapter-humanizer.

Finds the AI-construction candidates that can be matched mechanically — the
``**Banned shape:**`` regexes of ``anti-ai-patterns.md`` Section 11, the
Section 1 flagged vocabulary, and the author's own bans — and applies the
per-scene density rules (11.5 near-miss, 11.9 negation loop, 11.10 hedges) plus
dash density, repeated sentence openers, and invisible characters. Shapes that
need judgement (11.8, 11.11, 11.12, literal vs. metaphorical vocabulary) stay
with the model; hits inside dialogue are marked so the model can weigh
in-character usage.

``scan_draft`` and ``check_replacement`` are pure functions over already-loaded
patterns; ``load_patterns`` and ``load_author_dash_limit`` are the only parts
that touch the filesystem.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from tools.analysis.manuscript.text_utils import _make_snippet
from tools.analysis.prose_metrics import (
    _DASH_RE,
    _DIALOGUE_RE,
    _HEADING_RE,
    _HEDGE_RE,
    _MASK,
    _MD_FORMAT_RE,
    DEFAULT_DASH_PER_1K_LIMIT,
    HEDGE_SEGMENT_MIN,
    UNIFORM_BURSTINESS_BELOW,
    _mask_dialogue,
    analyse_draft,
    is_invisible_char,
    split_lines,
    split_segments,
)
from tools.banlist_loader import BannedPattern

# The catalog's 11.9 / 11.10 regexes match a single use. Those shapes are
# density rules: they are handled per scene below, never as plain hits.
_DENSITY_SHAPE_MARKERS = ("seemed|appeared to", "It wasn't", "It wasn’t")

_APOS = "['’]"
_NEAR_MISS_RE = re.compile(rf"\b(?:did not quite|didn{_APOS}t quite|never quite|almost became)\b", re.IGNORECASE)
_NEGATION_RE = re.compile(rf"\bIt wasn{_APOS}t [^.\n]{{1,40}}\.\s+It was\b|\bNot [A-Z][a-z]+\.\s+[A-Z][a-z]+\.")
_MIN_SENTENCES_FOR_RHYTHM_FLAG = 8

_CATEGORY_ORDER = {
    "invisible_char": 0,
    "author_rule": 1,
    "shape": 2,
    "vocabulary": 3,
    "near_miss": 4,
    "negation_loop": 5,
    "hedge_density": 6,
    "repeated_openers": 7,
}


def load_patterns(
    plugin_root: Path,
    author_slug: str | None,
    storyforge_home: Path | None = None,
) -> tuple[list[BannedPattern], list[BannedPattern], list[BannedPattern]]:
    """Load ``(global_shapes, global_tells, author_patterns)``.

    Every loader failure degrades to an empty list, matching the manuscript
    scanners: one broken source must not take the whole scan down.
    """
    from tools.banlist_loader import (
        load_author_dont_rules,
        load_author_vocab,
        load_author_writing_discoveries,
        load_global_ai_tells,
        load_global_shape_bans,
    )

    def _safe(fn, *args, **kwargs) -> list[BannedPattern]:
        try:
            return list(fn(*args, **kwargs))
        except Exception:  # pylint: disable=broad-except
            return []

    shapes = _safe(load_global_shape_bans, plugin_root)
    tells = _safe(load_global_ai_tells, plugin_root)
    author: list[BannedPattern] = []
    if author_slug:
        for loader in (load_author_vocab, load_author_writing_discoveries, load_author_dont_rules):
            author.extend(_safe(loader, author_slug, storyforge_home=storyforge_home))
    return shapes, tells, author


def load_author_dash_limit(author_dir: Path) -> float | None:
    """Read ``em_dash_per_1k_limit`` from an author's ``profile.md`` frontmatter."""
    from tools.state.parsers import parse_frontmatter

    profile = author_dir / "profile.md"
    try:
        meta, _ = parse_frontmatter(profile.read_text(encoding="utf-8"))
    except OSError:
        return None
    value = meta.get("em_dash_per_1k_limit")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return float(value)


def _is_density_shape(pattern: BannedPattern) -> bool:
    return any(marker in pattern.label for marker in _DENSITY_SHAPE_MARKERS)


def _in_dialogue(line: str, offset: int) -> bool:
    return any(m.start() <= offset < m.end() for m in _DIALOGUE_RE.finditer(line))


def _clean_line(raw: str) -> str:
    return _MD_FORMAT_RE.sub("", raw)


def _make_hit(
    *,
    line_no: int,
    segment: int,
    category: str,
    label: str,
    snippet: str,
    source: str,
    severity: str = "warn",
    matched: str = "",
    in_dialogue: bool = False,
) -> dict[str, Any]:
    return {
        "line": line_no,
        "segment": segment,
        "category": category,
        "label": label,
        "matched": matched,
        "snippet": snippet,
        "source": source,
        "severity": severity,
        "in_dialogue": in_dialogue,
    }


def _pattern_hits(
    lines: list[tuple[int, int, str]],
    global_shapes: list[BannedPattern],
    global_tells: list[BannedPattern],
    author_patterns: list[BannedPattern],
) -> list[dict[str, Any]]:
    """Shape / vocabulary / author hits over ``(segment, line_no, raw)`` lines.

    Every occurrence is a hit. A global hit is dropped only when its span
    overlaps an author-rule span — the author's own ban wins for that text,
    while unrelated constructions on the same paragraph are still reported.
    """
    shapes = [p for p in global_shapes if not _is_density_shape(p)]
    hits: list[dict[str, Any]] = []
    for segment, line_no, raw in lines:
        if not raw.strip() or _HEADING_RE.match(raw):
            continue
        line = _clean_line(raw).strip()

        author_spans: list[tuple[int, int]] = []
        for pattern in author_patterns:
            for m in pattern.pattern.finditer(line):
                author_spans.append((m.start(), m.end()))
                hits.append(
                    _make_hit(
                        line_no=line_no,
                        segment=segment,
                        category="author_rule",
                        label=pattern.label,
                        matched=m.group(0),
                        snippet=_make_snippet(line, m.group(0).lower()),
                        source=pattern.source,
                        severity=pattern.severity,
                        in_dialogue=_in_dialogue(line, m.start()),
                    )
                )

        seen_spans: set[tuple[str, int, int]] = set()
        for category, group in (("shape", shapes), ("vocabulary", global_tells)):
            for pattern in group:
                for m in pattern.pattern.finditer(line):
                    if any(m.start() < end and start < m.end() for start, end in author_spans):
                        continue
                    # Several catalog entries can match the same words (e.g. an
                    # inflected and a base form); report the text once.
                    if (category, m.start(), m.end()) in seen_spans:
                        continue
                    seen_spans.add((category, m.start(), m.end()))
                    hits.append(
                        _make_hit(
                            line_no=line_no,
                            segment=segment,
                            category=category,
                            label=pattern.label,
                            matched=m.group(0),
                            snippet=_make_snippet(line, m.group(0).lower()),
                            source=pattern.source,
                            severity=pattern.severity,
                            in_dialogue=_in_dialogue(line, m.start()),
                        )
                    )
    return hits


def _invisible_hits(lines: list[tuple[int, int, str]]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for segment, line_no, raw in lines:
        chars = [c for c in raw if is_invisible_char(c)]
        if not chars:
            continue
        codes = " ".join(f"U+{ord(c):04X}" for c in chars)
        hits.append(
            _make_hit(
                line_no=line_no,
                segment=segment,
                category="invisible_char",
                label="invisible character",
                matched=codes,
                snippet=_make_snippet(raw.replace("\ufeff", "").strip(), ""),
                source="fingerprint",
                severity="warn",
            )
        )
    return hits


def _density_hits(
    segments_lines: list[list[tuple[int, str]]],
    metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    segment_of_line: dict[int, int] = {}
    line_text: dict[int, str] = {}
    for idx, group in enumerate(segments_lines, start=1):
        for line_no, raw in group:
            segment_of_line[line_no] = idx
            line_text[line_no] = _clean_line(raw).strip()

    for idx, group in enumerate(segments_lines, start=1):
        near: list[tuple[int, str]] = []
        negation: list[tuple[int, str]] = []
        for line_no, raw in group:
            if not raw.strip() or _HEADING_RE.match(raw):
                continue
            # Narration only: in-character speech neither counts toward nor
            # carries these density rules (hedges are narration-only too).
            narration = _mask_dialogue(_clean_line(raw).strip())
            for m in _NEAR_MISS_RE.finditer(narration):
                near.append((line_no, m.group(0)))
            for m in _NEGATION_RE.finditer(narration):
                negation.append((line_no, m.group(0)))
        if len(near) >= 2:
            for line_no, matched in near:
                hits.append(
                    _make_hit(
                        line_no=line_no,
                        segment=idx,
                        category="near_miss",
                        label=f"11.5 near-miss body language ({len(near)} in this scene, limit 1)",
                        matched=matched,
                        snippet=_make_snippet(line_text[line_no], matched.lower()),
                        source="global anti-ai (11.5)",
                    )
                )
        for line_no, matched in negation[1:]:
            hits.append(
                _make_hit(
                    line_no=line_no,
                    segment=idx,
                    category="negation_loop",
                    label="11.9 negation-as-assertion loop (2nd+ in this scene)",
                    matched=matched,
                    snippet=_make_snippet(line_text[line_no], matched.lower()),
                    source="global anti-ai (11.9)",
                )
            )

    for idx, seg in enumerate(metrics["segments"], start=1):
        if seg["hedge_count"] >= HEDGE_SEGMENT_MIN:
            for line_no in sorted(set(seg["hedge_lines"])):
                hits.append(
                    _make_hit(
                        line_no=line_no,
                        segment=idx,
                        category="hedge_density",
                        label=f"11.10 hedge-word density ({seg['hedge_count']} in this scene, limit 2)",
                        snippet=line_text.get(line_no, ""),
                        source="global anti-ai (11.10)",
                    )
                )

    chapter = metrics["chapter"]
    for run in chapter["repeated_openers"]:
        line_no = run["line"]
        hits.append(
            _make_hit(
                line_no=line_no,
                segment=segment_of_line.get(line_no, 1),
                category="repeated_openers",
                label=f'11.13 {run["run"]} consecutive sentences open with "{run["opener"]}"',
                matched=run["opener"],
                snippet=line_text.get(line_no, ""),
                source="global anti-ai (11.13)",
            )
        )
    return hits


def scan_draft(
    text: str,
    *,
    global_shapes: list[BannedPattern],
    global_tells: list[BannedPattern],
    author_patterns: list[BannedPattern],
    dash_limit: float | None = None,
) -> dict[str, Any]:
    """Scan a chapter draft. Returns hits, chapter-level flags, and metrics."""
    limit = dash_limit if dash_limit is not None else DEFAULT_DASH_PER_1K_LIMIT
    groups, scene_breaks_found = split_segments(text)
    lines = [(idx, line_no, raw) for idx, group in enumerate(groups, start=1) for line_no, raw in group]
    metrics = analyse_draft(text)

    hits = _pattern_hits(lines, global_shapes, global_tells, author_patterns)
    hits += _invisible_hits(lines)
    hits += _density_hits(groups, metrics)
    hits.sort(key=lambda h: (h["line"], _CATEGORY_ORDER.get(h["category"], 99)))
    for n, hit in enumerate(hits, start=1):
        hit["id"] = n

    flags: list[dict[str, Any]] = []
    chapter = metrics["chapter"]
    cv = chapter["burstiness_cv"]
    if (
        cv is not None
        and cv < UNIFORM_BURSTINESS_BELOW
        and chapter["narration_sentences"] >= _MIN_SENTENCES_FOR_RHYTHM_FLAG
    ):
        flags.append(
            {
                "kind": "uniform_rhythm",
                "detail": (
                    f"narration sentence-length variation {cv} is below "
                    f"{UNIFORM_BURSTINESS_BELOW} across {chapter['narration_sentences']} sentences"
                ),
            }
        )
    if chapter["dash_per_1k"] > limit:
        # Chapter-level, not per-dash: a dashy chapter has dozens of dash lines,
        # which would swamp the 20-hit batch. `excess` is how many to rework.
        allowed = limit * chapter["narration_words"] / 1000
        flags.append(
            {
                "kind": "dash_density",
                "per_1k": chapter["dash_per_1k"],
                "limit": limit,
                "excess": max(1, math.ceil(chapter["dash_count"] - allowed)),
                "lines": chapter["dash_lines"],
                "detail": (
                    f"{chapter['dash_count']} narration dashes, {chapter['dash_per_1k']} per 1k words "
                    f"(limit {limit:g}); dialogue dashes not counted"
                ),
            }
        )
    if not scene_breaks_found:
        flags.append(
            {
                "kind": "no_scene_breaks",
                "detail": "no horizontal-rule scene break found; density rules were applied to the whole chapter",
            }
        )

    counts: dict[str, int] = {}
    for hit in hits:
        counts[hit["category"]] = counts.get(hit["category"], 0) + 1

    return {
        "hits": hits,
        "flags": flags,
        "counts": counts,
        "dash_limit": limit,
        "scene_breaks_found": scene_breaks_found,
        "metrics": metrics,
    }


def check_replacement(
    text: str,
    *,
    global_shapes: list[BannedPattern],
    global_tells: list[BannedPattern],
    author_patterns: list[BannedPattern],
) -> dict[str, Any]:
    """Check a proposed replacement before it is shown to the user.

    Hard hits (catalog shape, flagged vocabulary, author ban, invisible
    character) make it unclean. Hedges, near-miss constructions, negation
    loops and narration dashes are cautions: one is fine, but the caller
    should weigh them against the density of the surrounding scene.
    """
    lines = [(1, n, raw) for n, raw in enumerate(split_lines(text), start=1)]
    hits = _pattern_hits(lines, global_shapes, global_tells, author_patterns)
    hits += _invisible_hits(lines)
    hits.sort(key=lambda h: (h["line"], _CATEGORY_ORDER.get(h["category"], 99)))
    for n, hit in enumerate(hits, start=1):
        hit["id"] = n

    masked = _mask_dialogue(text)
    narration = masked.replace(_MASK, " ")
    cautions: list[dict[str, Any]] = []
    for kind, count in (
        ("hedge", len(_HEDGE_RE.findall(narration))),
        ("near_miss", len(_NEAR_MISS_RE.findall(masked))),
        ("negation_loop", len(_NEGATION_RE.findall(masked))),
        ("dash", len(_DASH_RE.findall(narration))),
    ):
        if count:
            cautions.append({"kind": kind, "count": count})

    return {"clean": not hits, "hits": hits, "cautions": cautions}
