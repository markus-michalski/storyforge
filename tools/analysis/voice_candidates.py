"""Voice candidate engine — Epic #663 / Issue #667.

Turns classified ``review_feedback`` rows into promotion candidates for the
author profile. Pure and deterministic: no LLM, no I/O besides loading the
vocabulary. Counting happens on ``(book_category, dimension, direction)``, never
on comment wording; the generic ``other`` dimension additionally keys on its
normalized rule, because its direction carries no meaning of its own.

Rules:
- Each entry weighs by its source (author comments 1.0, humanizer 0.5,
  proofreader 0.25). Rejected proposals count like accepted ones because the
  classification already states what the author wants. Proofreader entries the
  author accepted are noise and weigh nothing.
- A candidate needs a weighted sum of ``min_weight`` and evidence from
  ``min_chapters`` distinct chapters (counted per book).
- Scope is the intersection of the genre sets of the evidence that carries
  genres: a non-empty intersection scopes the candidate to those genres, an
  empty one (or no genre information at all) makes it universal. Fiction and
  memoir are never mixed.
- Opposite directions of one dimension with overlapping scope are reported as
  a conflict and promoted on neither side, provided the weaker side carries at
  least ``CONFLICT_MIN_WEIGHT``. A weaker opposition is attached to the
  candidate as ``opposed_by``.
- A discarded candidate returns only once the open evidence has caught up with
  the discarded evidence of overlapping scope. Suppressed directions do not
  take part in conflicts.
- Conflicts and repeats only look at open evidence: a rule that was already
  promoted is reported through ``harvested_weight``, and the harvest skill
  compares candidates with existing discoveries.
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
CONFLICT_MIN_WEIGHT = 1.0

_OPEN = "classified"
_REQUIRED = ("id", "book_slug", "chapter_slug")
_Key = tuple[str, str, str, str]


def _genres(csv: Any) -> frozenset[str]:
    return frozenset(g.strip().casefold() for g in str(csv or "").split(",") if g.strip())


def _weight(row: dict[str, Any]) -> float:
    source = str(row.get("source_skill"))
    if source == "proofreader" and row.get("decision") != "rejected":
        return 0.0
    return SOURCE_WEIGHTS.get(source, 1.0)


def _scope_of_genres(sets: list[frozenset[str]]) -> dict[str, Any]:
    known = [s for s in sets if s]
    if not known:
        return {"universal": True, "genres": []}
    common = frozenset.intersection(*known)
    if not common:
        return {"universal": True, "genres": []}
    return {"universal": False, "genres": sorted(common)}


def _scope(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return _scope_of_genres([_genres(r.get("genres", "")) for r in rows])


def _scopes_overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a["universal"] or b["universal"]:
        return True
    return bool(set(a["genres"]) & set(b["genres"]))


def _row_overlaps(row: dict[str, Any], scope: dict[str, Any]) -> bool:
    genres = _genres(row.get("genres", ""))
    if scope["universal"] or not genres:
        return True
    return bool(genres & set(scope["genres"]))


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


def _side(stats: dict[str, Any]) -> dict[str, Any]:
    keys = ("weight", "chapter_count", "evidence_count", "evidence_ids", "scope", "normalized_rule")
    return {k: stats[k] for k in keys}


def _well_formed(row: dict[str, Any]) -> bool:
    if any(row.get(k) in (None, "") for k in _REQUIRED):
        return False
    try:
        int(row["id"])
    except (TypeError, ValueError):
        return False
    return True


def build_voice_candidates(
    rows: list[dict[str, Any]],
    *,
    plugin_root: Path | None = None,
    min_weight: float = DEFAULT_MIN_WEIGHT,
    min_chapters: int = DEFAULT_MIN_CHAPTERS,
) -> dict[str, Any]:
    """Return ``{candidates, conflicts, suppressed, unclassified, skipped_unknown,
    skipped_malformed}``."""
    if min_weight <= 0 or min_chapters < 1:
        raise ValueError("min_weight must be > 0 and min_chapters >= 1")

    vocab = load_voice_dimensions(plugin_root)
    groups: dict[_Key, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"open": [], "discarded": [], "harvested": []}
    )
    unclassified = 0
    skipped_unknown = 0
    skipped_malformed = 0

    for r in rows:
        status = r.get("status")
        if status == "pending":
            unclassified += 1
            continue
        if status not in {_OPEN, "discarded", "harvested"}:
            continue
        if not _well_formed(r):
            skipped_malformed += 1
            continue
        category = r.get("book_category")
        dimension, direction = r.get("dimension"), r.get("direction")
        dim = vocab.get(dimension) if isinstance(dimension, str) else None
        if (
            not isinstance(category, str)
            or not isinstance(dimension, str)
            or not isinstance(direction, str)
            or dim is None
            or category not in dim["categories"]
            or direction not in dim["directions"]
        ):
            if status == _OPEN:
                skipped_unknown += 1
            continue
        rule_key = str(r.get("normalized_rule") or "").strip().casefold() if dimension == "other" else ""
        bucket = "open" if status == _OPEN else str(status)
        groups[(category, dimension, direction, rule_key)][bucket].append(r)

    def passes(stats: dict[str, Any]) -> bool:
        return stats["weight"] >= min_weight and stats["chapter_count"] >= min_chapters

    open_stats: dict[_Key, dict[str, Any]] = {
        key: _stats(parts["open"]) for key, parts in groups.items() if parts["open"]
    }

    # Suppression first: a direction the author already discarded must neither
    # be proposed nor block its opposite until its evidence has doubled.
    discarded_weight: dict[_Key, float] = {}
    for key, stats in open_stats.items():
        total = sum(
            _weight(r) for r in groups[key]["discarded"] if _row_overlaps(r, stats["scope"])
        )
        discarded_weight[key] = round(total, 4)
    suppressed_keys = {
        key for key, stats in open_stats.items()
        if discarded_weight[key] > 0 and stats["weight"] < discarded_weight[key]
    }

    conflicted: set[_Key] = set()
    conflicts: list[dict[str, Any]] = []
    opposed_by: dict[_Key, list[dict[str, Any]]] = defaultdict(list)
    for key, stats in sorted(open_stats.items()):
        category, dimension, direction, rule_key = key
        if key in suppressed_keys:
            continue
        opposite = vocab[dimension]["directions"][direction].get("opposite")
        if not opposite or direction > opposite:
            continue
        other_key: _Key = (category, dimension, opposite, rule_key)
        other = open_stats.get(other_key)
        if other is None or other_key in suppressed_keys:
            continue
        if not _scopes_overlap(stats["scope"], other["scope"]):
            continue
        strong, weak = (stats, other) if stats["weight"] >= other["weight"] else (other, stats)
        if not passes(strong):
            continue
        if weak["weight"] < CONFLICT_MIN_WEIGHT:
            weak_key = other_key if weak is other else key
            strong_key = key if weak is other else other_key
            opposed_by[strong_key].append({
                "direction": weak_key[2], "weight": weak["weight"],
                "evidence_ids": weak["evidence_ids"],
            })
            continue
        conflicted.update({key, other_key})
        conflicts.append({
            "book_category": category,
            "dimension": dimension,
            "sides": [
                {"direction": direction, **_side(stats)},
                {"direction": opposite, **_side(other)},
            ],
        })

    candidates: list[dict[str, Any]] = []
    suppressed = 0
    for key, stats in open_stats.items():
        if key in conflicted or not passes(stats):
            continue
        if key in suppressed_keys:
            suppressed += 1
            continue
        category, dimension, direction, _rule_key = key
        parts = groups[key]

        kind = str(vocab[dimension]["directions"][direction]["kind"])
        open_rows = parts["open"]
        total = sum(_weight(r) for r in open_rows)
        rejected = sum(_weight(r) for r in open_rows if r.get("decision") == "rejected")
        rejected_share = round(rejected / total, 4) if total else 0.0
        # recurring_tics feed the banlist, so a quirk the author defended
        # (rejected proposals) is a style principle, never a tic.
        target = "donts" if kind == "avoid" else "style_principles"

        candidates.append({
            "book_category": category,
            "dimension": dimension,
            "direction": direction,
            "kind": kind,
            "target_section": target,
            "rejected_share": rejected_share,
            "discarded_weight": discarded_weight[key],
            "harvested_weight": round(sum(_weight(r) for r in parts["harvested"]), 4),
            "opposed_by": opposed_by.get(key, []),
            **stats,
        })

    candidates.sort(
        key=lambda c: (-c["weight"], c["dimension"], c["direction"], c["book_category"],
                       c["normalized_rule"])
    )
    conflicts.sort(key=lambda c: (c["book_category"], c["dimension"], c["sides"][0]["direction"]))
    return {
        "candidates": candidates,
        "conflicts": conflicts,
        "suppressed": suppressed,
        "unclassified": unclassified,
        "skipped_unknown": skipped_unknown,
        "skipped_malformed": skipped_malformed,
    }
