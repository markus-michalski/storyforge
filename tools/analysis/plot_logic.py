"""Plot-logic checker — Issue #150.

Deterministic half of the plothole detector. Builds a knowledge
index from the book's existing data sources (canon log, timeline,
chapter promises), then runs static detectors for the categories
that don't need an LLM:

- ``causality_inversion`` — chapter references a fact whose
  establishing chapter has a later story-day. Mechanically
  detectable via timeline + canon log + token search.
- ``chekhov_gun`` — promise placed in chapter X with a target
  chapter that has been drafted but doesn't reference the promise,
  or marked unfired with no later chapter referencing it.

The semantic categories (``information_leak``, ``motivation_break``,
``premise_violation``, ``pov_knowledge_boundary``) are picked up by
the consuming skills (``chapter-reviewer``, ``manuscript-checker``)
using this module's index data + an LLM pass — they don't run here.

Memoir-aware: ``chekhov_gun`` and ``premise_violation`` are skipped
for ``book_category: memoir``. Memoir doesn't build narratives on
setup-payoff structure or invented world-rules.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from tools.analysis.timeline_validator import parse_plot_timeline
from tools.state.parsers import parse_book_readme
from tools.state.promises import collect_book_promises
from tools.state.review_brief import _parse_canon_log_facts


Scope = Literal["chapter", "manuscript"]

# Severity levels — aligned with the rest of the gate contract.
HIGH = "high"
MEDIUM = "medium"


@dataclass(frozen=True)
class Finding:
    """A single plot-logic issue with enough context for a human to act."""

    category: str
    severity: str
    chapter: str
    location: str
    snippet: str
    evidence: str
    suggested_fix: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Knowledge index
# ---------------------------------------------------------------------------


def build_knowledge_index(book_path: Path) -> dict[str, Any]:
    """Aggregate the deterministic data sources into one index.

    Output dict (always present, may be empty):
        - ``book_category``: "fiction" | "memoir"
        - ``chapter_story_days``: {chapter_slug: int}
        - ``facts``: list of canon-log facts with established_in_slug
        - ``promises``: list of dicts {source_chapter, description, target, status}
    """
    book_meta = parse_book_readme(book_path / "README.md")
    book_category = book_meta.get("book_category", "fiction") or "fiction"

    return {
        "book_category": book_category,
        "chapter_story_days": _chapter_story_days(book_path),
        "facts": _canon_log_facts_with_slugs(book_path),
        "promises": [_promise_to_dict(p) for p in collect_book_promises(book_path)],
    }


def _chapter_story_days(book_path: Path) -> dict[str, int]:
    """Map chapter slug -> story-day from ``plot/timeline.md``.

    Uses ``parse_plot_timeline`` for robust parsing. Each event row
    contributes its ``chapter`` cell -> ``story_day``. Where a
    chapter spans multiple days, the *first* (earliest) day wins —
    causality_inversion uses the earliest moment a chapter could
    plausibly reference a fact.
    """
    cal = parse_plot_timeline(book_path)
    if cal is None:
        return {}

    out: dict[str, int] = {}
    for event in cal.events:
        slug = _normalize_chapter_token(event.chapter_slug)
        if not slug:
            continue
        # Earliest day wins.
        if slug not in out or event.story_day < out[slug]:
            out[slug] = event.story_day

    # Map "Ch 03" -> any matching directory slug in chapters/.
    return _resolve_chapter_keys(book_path, out)


def _normalize_chapter_token(token: str) -> str:
    """Strip whitespace and lower-case for comparison."""
    return token.strip()


def _resolve_chapter_keys(book_path: Path, raw: dict[str, int]) -> dict[str, int]:
    """Translate timeline ``Ch 03``-style cells to actual chapter directory slugs.

    The timeline calendar uses display labels like ``Ch 03``; the
    chapters/ directory uses slugs like ``03-twist``. We match by
    leading number.
    """
    chapters_dir = book_path / "chapters"
    if not chapters_dir.is_dir():
        return raw

    slug_dirs = sorted(p.name for p in chapters_dir.iterdir() if p.is_dir())
    out: dict[str, int] = {}
    for raw_key, day in raw.items():
        # Already a directory slug?
        if raw_key in slug_dirs:
            out[raw_key] = day
            continue
        # "Ch 03" → leading number → match slugs starting with "03-".
        num_match = re.search(r"\d+", raw_key)
        if not num_match:
            continue
        num = int(num_match.group(0))
        prefix = f"{num:02d}-"
        for slug in slug_dirs:
            if slug.startswith(prefix):
                out[slug] = day
                break
    return out


def _canon_log_facts_with_slugs(book_path: Path) -> list[dict]:
    """Return canon-log facts annotated with ``established_in_slug``.

    Adds the resolved chapter directory slug (if any) so detectors
    can compare to the chapter_story_days index without re-doing the
    "Ch 03" -> "03-twist" translation.
    """
    canon_path = book_path / "plot" / "canon-log.md"
    if not canon_path.is_file():
        return []
    try:
        text = canon_path.read_text(encoding="utf-8")
    except OSError:
        return []

    facts = _parse_canon_log_facts(text)
    chapters_dir = book_path / "chapters"
    slug_dirs = sorted(p.name for p in chapters_dir.iterdir() if p.is_dir()) if chapters_dir.is_dir() else []

    for fact in facts:
        fact["established_in_slug"] = _resolve_to_slug(fact.get("established_in", ""), slug_dirs)
    return facts


def _resolve_to_slug(label: str, slug_dirs: list[str]) -> str:
    """Map a ``Ch 03``-style label to a chapter directory slug.

    Returns "" when no match — callers must treat that as
    "unparseable, skip rather than false-positive".
    """
    if label in slug_dirs:
        return label
    num_match = re.search(r"\d+", label)
    if not num_match:
        return ""
    prefix = f"{int(num_match.group(0)):02d}-"
    for slug in slug_dirs:
        if slug.startswith(prefix):
            return slug
    return ""


def _promise_to_dict(entry: dict) -> dict:
    p = entry["promise"]
    return {
        "source_chapter": entry["source_chapter"],
        "description": p.description,
        "target": p.target,
        "status": p.status,
    }


# ---------------------------------------------------------------------------
# detect_causality_inversion
# ---------------------------------------------------------------------------


# Words that strongly signal a fact-reference — not exhaustive, but
# the canon-log fact's main noun phrase is the actual signal we use.
def detect_causality_inversion(book_path: Path, idx: dict[str, Any]) -> list[Finding]:
    """Find chapters that reference a fact established in a later
    story-day chapter.

    For each fact in the canon log:
    - Determine its establishing chapter slug + story-day.
    - For every chapter with story-day < establishing-day, scan the
      draft for token-matching the fact's main noun.
    - Each hit yields a ``causality_inversion`` finding with
      enough evidence for a human to act.
    """
    facts = idx.get("facts", [])
    chapter_days = idx.get("chapter_story_days", {})
    if not facts or not chapter_days:
        return []

    findings: list[Finding] = []
    for fact in facts:
        establish_slug = fact.get("established_in_slug") or ""
        if not establish_slug or establish_slug not in chapter_days:
            continue
        establish_day = chapter_days[establish_slug]
        keywords = _fact_keywords(fact["fact"])
        if not keywords:
            continue

        for ch_slug, day in chapter_days.items():
            if ch_slug == establish_slug or day >= establish_day:
                continue
            # Earlier chapter: scan draft for any of the keywords.
            draft_path = book_path / "chapters" / ch_slug / "draft.md"
            if not draft_path.is_file():
                continue
            try:
                draft_text = draft_path.read_text(encoding="utf-8")
            except OSError:
                continue
            seen_lines: set[int] = set()
            for keyword in keywords:
                for line_no, snippet in _find_keyword_lines(draft_text, keyword):
                    # De-dupe — multiple keywords on the same line yield one finding.
                    if line_no in seen_lines:
                        continue
                    seen_lines.add(line_no)
                    findings.append(
                        Finding(
                            category="causality_inversion",
                            severity=HIGH,
                            chapter=ch_slug,
                            location=f"draft.md:{line_no}",
                            snippet=snippet,
                            evidence=(
                                f"Fact {fact['fact']!r} is established in "
                                f"{fact.get('established_in', establish_slug)} "
                                f"(story-day {establish_day}), but {ch_slug} is "
                                f"story-day {day}."
                            ),
                            suggested_fix=(
                                "Move the reference to a chapter at or after the "
                                "establishing chapter, insert an earlier source for "
                                "the knowledge, or remove the line."
                            ),
                        )
                    )
    return findings


_KEYWORD_STOPLIST: frozenset[str] = frozenset(
    {
        "everything",
        "something",
        "anything",
        "nothing",
        "somewhere",
        "anywhere",
        "nowhere",
        "themselves",
        "themself",
        "whether",
        "because",
        "however",
        "although",
        "actually",
        "really",
        "though",
        "almost",
        "always",
        "never",
        "before",
        "after",
        "during",
        "while",
        "could",
        "would",
        "should",
        "might",
    }
)


def _fact_keywords(fact_text: str) -> list[str]:
    """Extract scannable keyword stems from a fact statement.

    Returns up to three stems ordered by length (longest first), with
    common stoplist tokens filtered out. Multiple stems make the
    detector more forgiving when the longest noun is generic
    ("everything", "themselves") and the actual topic word is the
    verb stem.
    """
    text = fact_text.strip().lower()
    text = re.sub(r"^(the |a |an )", "", text)
    tokens = [t for t in re.findall(r"[a-z]{5,}", text) if t not in _KEYWORD_STOPLIST]
    if not tokens:
        return []
    # Sort by length descending; cap at 3 stems.
    tokens.sort(key=len, reverse=True)
    return [_stem(t) for t in tokens[:3]]


def _fact_keyword(fact_text: str) -> str:
    """Backwards-compatible single-keyword accessor (longest stem)."""
    keywords = _fact_keywords(fact_text)
    return keywords[0] if keywords else ""


def _stem(word: str) -> str:
    """Cheap stem: drop common English inflectional suffixes."""
    for suffix in ("sses", "ies", "ied", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def _find_keyword_lines(text: str, keyword: str) -> list[tuple[int, str]]:
    """Locate ``keyword`` matches as (line_number, snippet) pairs."""
    pattern = re.compile(rf"\b{re.escape(keyword)}\w*\b", re.IGNORECASE)
    out: list[tuple[int, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            out.append((line_no, line.strip()[:200]))
    return out


# ---------------------------------------------------------------------------
# detect_chekhov_guns
# ---------------------------------------------------------------------------


def detect_chekhov_guns(book_path: Path, idx: dict[str, Any]) -> list[Finding]:
    """Find promises that haven't been honored.

    For each active promise:
    - target is a chapter slug → if that chapter draft exists and
      doesn't token-match the promise description, raise high.
    - target is "unfired" → if no later-chapter draft references the
      promise description, raise high (the manuscript-end check; we
      conservatively assume the manuscript scope means the book is
      far enough along that an unfired promise is concerning).
    - target is "Ch N" (legacy form) → resolve to slug, treat as above.
    """
    promises = idx.get("promises", [])
    if not promises:
        return []

    chapters_dir = book_path / "chapters"
    if not chapters_dir.is_dir():
        return []
    slug_dirs = sorted(p.name for p in chapters_dir.iterdir() if p.is_dir())

    findings: list[Finding] = []
    for p in promises:
        if p["status"] != "active":
            continue
        keyword = _promise_keyword(p["description"])
        if not keyword:
            continue

        target = (p["target"] or "").strip()
        if target.lower() == "unfired":
            # Scan all later chapters (after source) for any reference.
            later_slugs = [s for s in slug_dirs if s > p["source_chapter"]]
            if _any_chapter_references(book_path, later_slugs, keyword):
                continue
            findings.append(
                Finding(
                    category="chekhov_gun",
                    severity=HIGH,
                    chapter=p["source_chapter"],
                    location="README.md:promises",
                    snippet=p["description"],
                    evidence=(
                        f"Promise placed in {p['source_chapter']} (target: unfired); "
                        "no later chapter draft references it."
                    ),
                    suggested_fix=(
                        "Either land a payoff in a later chapter, retire the promise "
                        "(set status=retired), or revise the chapter to drop the setup."
                    ),
                )
            )
            continue

        # Target is a specific chapter — resolve to slug if needed.
        target_slug = _resolve_to_slug(target, slug_dirs) or target
        if target_slug not in slug_dirs:
            # Target chapter doesn't exist (yet) — defer, no finding.
            continue
        target_draft = book_path / "chapters" / target_slug / "draft.md"
        if not target_draft.is_file():
            # Chapter not yet drafted → deferred, no finding.
            continue
        try:
            target_text = target_draft.read_text(encoding="utf-8")
        except OSError:
            continue
        if _has_keyword(target_text, keyword):
            continue
        findings.append(
            Finding(
                category="chekhov_gun",
                severity=HIGH,
                chapter=p["source_chapter"],
                location="README.md:promises",
                snippet=p["description"],
                evidence=(
                    f"Promise placed in {p['source_chapter']} with target {target_slug}; "
                    f"the target chapter draft does not reference {keyword!r}."
                ),
                suggested_fix=(
                    f"Land the payoff in {target_slug}, retarget the promise, or set its status to retired."
                ),
            )
        )
    return findings


def _promise_keyword(description: str) -> str:
    """Extract a scannable keyword stem from a promise description.

    Same strategy as ``_fact_keyword``.
    """
    text = description.strip().lower()
    text = re.sub(r"^(the |a |an )", "", text)
    tokens = re.findall(r"[a-z]{5,}", text)
    if not tokens:
        return ""
    longest = max(tokens, key=len)
    return _stem(longest)


def _has_keyword(text: str, keyword: str) -> bool:
    return bool(re.search(rf"\b{re.escape(keyword)}\w*\b", text, re.IGNORECASE))


def _any_chapter_references(book_path: Path, slugs: list[str], keyword: str) -> bool:
    for slug in slugs:
        draft = book_path / "chapters" / slug / "draft.md"
        if not draft.is_file():
            continue
        try:
            text = draft.read_text(encoding="utf-8")
        except OSError:
            continue
        if _has_keyword(text, keyword):
            return True
    return False


# ---------------------------------------------------------------------------
# Top-level analyze_plot_logic
# ---------------------------------------------------------------------------


def analyze_plot_logic(
    book_path: Path,
    scope: Scope = "manuscript",
    chapter_slug: str | None = None,
) -> dict[str, Any]:
    """Run the deterministic plot-logic checks for a book.

    For ``scope="manuscript"``: all detectors run, including the
    cross-chapter chekhov_gun scan.

    For ``scope="chapter"``: only causality_inversion runs (the
    only detector with a per-chapter signal). chekhov_gun requires
    full-book context.

    Memoir books skip ``chekhov_gun`` regardless of scope.

    Returns a dict shaped for the gate envelope used elsewhere:
        - ``knowledge_index``: the deterministic data the consuming
          skill can feed into its LLM pass.
        - ``findings``: list[Finding.to_dict()].
        - ``gate``: GateResult-style envelope with status, reasons,
          and metadata.
    """
    if scope not in ("chapter", "manuscript"):
        raise ValueError(f"Invalid scope {scope!r} — must be 'chapter' or 'manuscript'.")
    if scope == "chapter" and not chapter_slug:
        raise ValueError("scope='chapter' requires chapter_slug.")

    idx = build_knowledge_index(book_path)
    is_memoir = idx["book_category"] == "memoir"

    findings: list[Finding] = []

    findings.extend(detect_causality_inversion(book_path, idx))
    if scope == "manuscript" and not is_memoir:
        findings.extend(detect_chekhov_guns(book_path, idx))

    if scope == "chapter":
        findings = [f for f in findings if f.chapter == chapter_slug]

    findings_dicts = [f.to_dict() for f in findings]
    gate = _derive_gate(findings_dicts, scope=scope, chapters_scanned=len(idx["chapter_story_days"]))

    return {
        "book_slug": book_path.name,
        "scope": scope,
        "book_category": idx["book_category"],
        "chapters_scanned": len(idx["chapter_story_days"]),
        "knowledge_index": idx,
        "findings": findings_dicts,
        "gate": gate,
    }


def _derive_gate(
    findings: list[dict[str, Any]],
    *,
    scope: str,
    chapters_scanned: int,
) -> dict[str, Any]:
    if not findings:
        return {
            "status": "PASS",
            "reasons": [],
            "findings": [],
            "metadata": {"scope": scope, "chapters_scanned": chapters_scanned},
        }

    high = [f for f in findings if f.get("severity") == HIGH]
    medium = [f for f in findings if f.get("severity") == MEDIUM]

    if high:
        status = "FAIL"
    elif medium:
        status = "WARN"
    else:
        status = "PASS"

    reasons: list[str] = []
    by_cat: dict[str, int] = {}
    for f in findings:
        by_cat[f["category"]] = by_cat.get(f["category"], 0) + 1
    for cat, count in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        reasons.append(f"{count} {cat} finding{'s' if count != 1 else ''}")

    return {
        "status": status,
        "reasons": reasons,
        "findings": [
            {
                "code": f["category"].upper(),
                "message": f["evidence"],
                "severity": f["severity"].upper(),
                "location": {"chapter": f["chapter"], "path": f["location"]},
            }
            for f in findings
        ],
        "metadata": {
            "scope": scope,
            "chapters_scanned": chapters_scanned,
            "by_category": by_cat,
        },
    }
