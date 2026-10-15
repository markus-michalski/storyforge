"""Voice candidate engine — Epic #663 / Issue #667.

Turns classified ``review_feedback`` rows into promotion candidates for the
author profile. Pure and deterministic: no LLM, no I/O besides loading the
vocabulary. Counting happens on ``(book_category, dimension, direction)``, never
on comment wording.

Rules:
- Each entry weighs by its source (author comments 1.0, humanizer 0.5,
  proofreader 0.25); rejected proposals count like accepted ones because the
  classification already states what the author wants.
- A candidate needs a weighted sum of ``min_weight`` and evidence from
  ``min_chapters`` distinct chapters (counted per book).
- Scope is the intersection of the genre sets of all evidence: a non-empty
  intersection scopes the candidate to those genres, an empty one makes it
  universal. Fiction and memoir are never mixed.
- Opposite directions of one dimension with overlapping scope are reported as
  a conflict and promoted on neither side.
- A discarded candidate returns only once the open evidence has caught up with
  the discarded evidence (it doubles).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.analysis.voice_dimensions import load_voice_dimensions

SOURCE_WEIGHTS: dict[str, float] = {
    "writer": 1.0,
    "reviewer": 1.0,
    "fixer": 1.0,
    "rewriter": 1.0,
    "self_edit": 1.0,
    "humanizer": 0.5,
    "proofreader": 0.25,
}
DEFAULT_MIN_WEIGHT = 3.0
DEFAULT_MIN_CHAPTERS = 2
RECURRING_TIC_REJECTED_SHARE = 0.5

_OPEN = "classified"
_Key = tuple[str, str, str]


def _genres(csv: str) -> frozenset[str]:
    return frozenset(g.strip() for g in str(csv or "").split(",") if g.strip())


def _weight(row: dict[str, Any]) -> float:
    return SOURCE_WEIGHTS.get(str(row.get("source_skill")), 1.0)


def _scope(rows: list[dict[str, Any]]) -> dict[str, Any]:
    common: frozenset[str] | None = None
    for r in rows:
        g = _genres(r.get("genres", ""))
        common = g if common is None else common & g
    if not common:
        return {"universal": True, "genres": []}
    return {"universal": False, "genres": sorted(common)}


def _scopes_overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a["universal"] or b["universal"]:
        return True
    return bool(set(a["genres"]) & set(b["genres"]))


def _most_common_rule(rows: list[dict[str, Any]]) -> str:
    counts: Counter[str] = Counter()
    latest: dict[str, int] = {}
    for r in rows:
        rule = str(r.get("normalized_rule") or "").strip()
        if not rule:
            continue
        counts[rule] += 1
        latest[rule] = max(latest.get(rule, 0), int(r["id"]))
    if not counts:
        return ""
    return max(counts, key=lambda rule: (counts[rule], latest[rule]))


def _stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    chapters = {(r["book_slug"], r["chapter_slug"]) for r in rows}
    return {
        "weight": round(sum(_weight(r) for r in rows), 4),
        "chapter_count": len(chapters),
        "evidence_count": len(rows),
        "evidence_ids": sorted(int(r["id"]) for r in rows),
        "books": sorted({str(r["book_slug"]) for r in rows}),
        "scope": _scope(rows),
        "normalized_rule": _most_common_rule(rows),
    }


def build_voice_candidates(
    rows: list[dict[str, Any]],
    *,
    plugin_root: Path | None = None,
    min_weight: float = DEFAULT_MIN_WEIGHT,
    min_chapters: int = DEFAULT_MIN_CHAPTERS,
) -> dict[str, Any]:
    """Return ``{candidates, conflicts, suppressed, unclassified, skipped_unknown}``."""
    if min_weight <= 0 or min_chapters < 1:
        raise ValueError("min_weight must be > 0 and min_chapters >= 1")

    vocab = load_voice_dimensions(plugin_root)
    groups: dict[_Key, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"open": [], "discarded": [], "harvested": []}
    )
    unclassified = 0
    skipped_unknown = 0

    for r in rows:
        status = r.get("status")
        if status == "pending":
            unclassified += 1
            continue
        if status not in {_OPEN, "discarded", "harvested"}:
            continue
        category = str(r.get("book_category") or "fiction")
        dimension, direction = r.get("dimension"), r.get("direction")
        dim = vocab.get(dimension) if isinstance(dimension, str) else None
        if (
            not isinstance(dimension, str)
            or not isinstance(direction, str)
            or dim is None
            or category not in dim["categories"]
            or direction not in dim["directions"]
        ):
            if status == _OPEN:
                skipped_unknown += 1
            continue
        bucket = "open" if status == _OPEN else str(status)
        groups[(category, dimension, direction)][bucket].append(r)

    def passes(stats: dict[str, Any]) -> bool:
        return stats["weight"] >= min_weight and stats["chapter_count"] >= min_chapters

    open_stats: dict[_Key, dict[str, Any]] = {
        key: _stats(parts["open"]) for key, parts in groups.items() if parts["open"]
    }

    # Conflicts: opposite directions of one dimension with overlapping scope,
    # where at least one side would otherwise be promoted.
    conflicted: set[_Key] = set()
    conflicts: list[dict[str, Any]] = []
    for (category, dimension, direction), stats in sorted(open_stats.items()):
        opposite = vocab[dimension]["directions"][direction].get("opposite")
        if not opposite or direction > opposite:
            continue
        other_key = (category, dimension, opposite)
        other = open_stats.get(other_key)
        if other is None:
            continue
        if not (passes(stats) or passes(other)):
            continue
        if not _scopes_overlap(stats["scope"], other["scope"]):
            continue
        conflicted.update({(category, dimension, direction), other_key})
        sides = [
            {"direction": direction, **_side(stats)},
            {"direction": opposite, **_side(other)},
        ]
        conflicts.append({"book_category": category, "dimension": dimension, "sides": sides})

    candidates: list[dict[str, Any]] = []
    suppressed = 0
    for key, stats in open_stats.items():
        if key in conflicted or not passes(stats):
            continue
        category, dimension, direction = key
        parts = groups[key]
        discarded_weight = round(sum(_weight(r) for r in parts["discarded"]), 4)
        if discarded_weight > 0 and stats["weight"] < discarded_weight:
            suppressed += 1
            continue

        kind = str(vocab[dimension]["directions"][direction]["kind"])
        open_rows = parts["open"]
        total = sum(_weight(r) for r in open_rows)
        rejected = sum(_weight(r) for r in open_rows if r.get("decision") == "rejected")
        rejected_share = round(rejected / total, 4) if total else 0.0
        if kind == "avoid":
            target = "donts"
        elif rejected_share >= RECURRING_TIC_REJECTED_SHARE:
            target = "recurring_tics"
        else:
            target = "style_principles"

        candidates.append({
            "book_category": category,
            "dimension": dimension,
            "direction": direction,
            "kind": kind,
            "target_section": target,
            "rejected_share": rejected_share,
            "discarded_weight": discarded_weight,
            "harvested_weight": round(sum(_weight(r) for r in parts["harvested"]), 4),
            **stats,
        })

    candidates.sort(key=lambda c: (-c["weight"], c["dimension"], c["direction"], c["book_category"]))
    conflicts.sort(key=lambda c: (c["book_category"], c["dimension"]))
    return {
        "candidates": candidates,
        "conflicts": conflicts,
        "suppressed": suppressed,
        "unclassified": unclassified,
        "skipped_unknown": skipped_unknown,
    }


def _side(stats: dict[str, Any]) -> dict[str, Any]:
    keys = ("weight", "chapter_count", "evidence_count", "evidence_ids", "scope", "normalized_rule")
    return {k: stats[k] for k in keys}
