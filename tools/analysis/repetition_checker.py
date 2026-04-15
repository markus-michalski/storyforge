"""Cross-chapter repetition detection.

Scans all chapter drafts of a book for repeated phrases, similes, character
tells, blocking tics, and structural patterns. The output is a structured
report meant to be consumed by the `repetition-checker` skill, which then
turns it into a human-readable Markdown file with revision recommendations.

Algorithmic approach
--------------------
- Normalise text (strip frontmatter, lowercase, collapse whitespace, strip
  punctuation that doesn't matter for n-gram identity).
- Build n-grams of length 4..7 over the running prose, recording every
  occurrence with chapter slug + line number + a context snippet.
- Drop n-grams that appear only once.
- Drop n-grams that are dominated by stop-words (every token is a stop-word).
- Classify each repeated n-gram into a category by inspecting its tokens and
  the immediate surrounding context (similes via "like|as|as if|as though",
  blocking tics via verb patterns, character tells via body-part vocabulary).
- Rank by severity: 4+ occurrences = high, 2..3 = medium.

The module is intentionally dependency-free (stdlib only) so it can run
inside the MCP server without extra installs.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Range of n-gram lengths to consider. 4 catches "the ghost of a", 7 catches
# longer signature constructions like "for a hundred and fifty years" without
# blowing up the index for very long books.
DEFAULT_NGRAM_SIZES = (4, 5, 6, 7)

# Minimum occurrences to keep an n-gram. 2 means "appears at least twice".
DEFAULT_MIN_OCCURRENCES = 2

# Stop-words used for the "skip n-grams that are entirely stop-words" filter.
# Kept small on purpose — we want to catch "for a hundred and fifty years",
# which contains stop-words but also distinctive content tokens.
STOP_WORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "if", "then", "of", "to", "in",
        "on", "at", "by", "for", "with", "from", "into", "onto", "as", "is",
        "are", "was", "were", "be", "been", "being", "it", "its", "this",
        "that", "these", "those", "he", "she", "him", "her", "his", "hers",
        "they", "them", "their", "i", "me", "my", "we", "us", "our", "you",
        "your", "not", "no", "do", "does", "did", "have", "has", "had", "so",
        "than", "there", "here", "out", "up", "down", "over", "under", "off",
        "about", "again", "very", "just",
    }
)

# Body-part / face-part vocabulary that, when present in a repeated phrase,
# strongly suggests a character tell.
BODY_PARTS = frozenset(
    {
        "eye", "eyes", "eyebrow", "eyebrows", "brow", "brows", "lip", "lips",
        "mouth", "jaw", "jaws", "cheek", "cheeks", "chin", "ear", "ears",
        "nose", "nostril", "nostrils", "tongue", "throat", "neck", "shoulder",
        "shoulders", "chest", "back", "spine", "arm", "arms", "elbow",
        "wrist", "hand", "hands", "finger", "fingers", "thumb", "knuckle",
        "knuckles", "fist", "fists", "hip", "hips", "leg", "legs", "knee",
        "knees", "foot", "feet", "toe", "toes", "muscle", "muscles", "vein",
        "veins", "tendon", "tendons", "head", "skull", "temple", "temples",
        "scalp", "hair", "face",
    }
)

# Verbs that frequently appear in blocking tics (small physical movements
# repeated as a beat between dialog).
BLOCKING_VERBS = frozenset(
    {
        "opened", "closed", "shut", "blinked", "swallowed", "nodded",
        "shrugged", "shook", "shifted", "leaned", "looked", "glanced",
        "stared", "turned", "tilted", "frowned", "smiled", "smirked",
        "exhaled", "inhaled", "sighed", "shivered", "flinched", "twitched",
        "jumped", "tightened", "loosened", "pressed", "clenched", "unclenched",
    }
)

# Sensory adjectives / nouns. If a repeated phrase contains one of these,
# bias it toward "sensory repetition".
SENSORY_TOKENS = frozenset(
    {
        "smell", "scent", "stink", "stench", "odour", "odor", "perfume",
        "taste", "tasted", "tang", "bitter", "sweet", "sour", "salty",
        "metallic", "coppery", "iron", "rusty",
        "warm", "cold", "icy", "hot", "burning", "cool",
        "sound", "noise", "echo", "whisper", "hum", "buzz",
    }
)

# Tokens commonly inside structural tics like "the kind of X that Y" or
# "the first time in X". Used as a hint for the structural category.
STRUCTURAL_HINTS = frozenset(
    {"kind", "sort", "type", "first", "last", "only", "way"}
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Occurrence:
    """A single occurrence of a repeated phrase in the manuscript."""

    chapter: str
    line: int
    snippet: str  # ~120 chars of surrounding context, with the phrase intact


@dataclass
class Finding:
    """A repeated phrase with all its occurrences and a category guess."""

    phrase: str
    category: str
    severity: str  # "high" | "medium"
    count: int
    occurrences: list[Occurrence] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^\s*#{1,6}\s.*$", re.MULTILINE)
_HORIZONTAL_RULE_RE = re.compile(r"^\s*[*_-]{3,}\s*$", re.MULTILINE)
_MD_FORMAT_RE = re.compile(r"[*_`~]")
# Punctuation to drop for the n-gram identity. We keep apostrophes inside
# words ("don't") so they aren't split, and we keep "—" as a soft separator.
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'\u2019]*")


def _strip_markdown(text: str) -> str:
    text = _FRONTMATTER_RE.sub("", text)
    text = _HEADING_RE.sub("", text)
    text = _HORIZONTAL_RULE_RE.sub("", text)
    text = _MD_FORMAT_RE.sub("", text)
    return text


def _tokenise(line: str) -> list[str]:
    """Lowercase tokens, apostrophes preserved inside words."""
    return [m.group(0).lower().replace("\u2019", "'") for m in _TOKEN_RE.finditer(line)]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

# Compiled patterns for category detection on the original (non-normalised)
# context snippet, so we can spot punctuation cues like "Closed it." or
# quotation marks.
_SIMILE_HINT_RE = re.compile(r"\b(like|as if|as though)\b", re.IGNORECASE)
_AS_X_AS_RE = re.compile(r"\bas\s+\w+\s+as\b", re.IGNORECASE)
_BLOCKING_PUNCT_RE = re.compile(r"\.\s+\w+(ed|s)?\s+(it|him|her|them)\.")


def _classify(phrase: str, occurrences: list[Occurrence]) -> str:
    """Pick the best category for a repeated phrase."""
    tokens = phrase.split()
    token_set = set(tokens)
    contexts = " ".join(o.snippet for o in occurrences)

    # Similes first — they're the most distinctive.
    if "like" in token_set or "as" in token_set:
        if (
            _SIMILE_HINT_RE.search(contexts)
            or _AS_X_AS_RE.search(contexts)
            or "like" in tokens[:2]
        ):
            return "simile"

    # Blocking tic: physical micro-action between dialog beats.
    if token_set & BLOCKING_VERBS:
        if _BLOCKING_PUNCT_RE.search(contexts) or any(
            t in token_set for t in ("opened", "closed", "shut")
        ):
            return "blocking_tic"

    # Character tell: repeated body-part description.
    if token_set & BODY_PARTS:
        return "character_tell"

    # Sensory repetition: same smell/taste/sound description.
    if token_set & SENSORY_TOKENS:
        return "sensory"

    # Structural tic: "the kind of X that Y" / "for X years" / "the first time"
    if token_set & STRUCTURAL_HINTS or _looks_structural(tokens):
        return "structural"

    return "signature_phrase"


def _looks_structural(tokens: list[str]) -> bool:
    """Heuristic for repeated structural patterns."""
    if not tokens:
        return False
    # "for <number-ish> years/days/months"
    if tokens[0] == "for" and tokens[-1] in {"years", "year", "days", "months", "weeks"}:
        return True
    # "the X of Y" patterns
    if len(tokens) >= 4 and tokens[0] == "the" and "of" in tokens:
        return True
    return False


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def _make_snippet(line: str, ngram_text: str, max_len: int = 140) -> str:
    """Return a trimmed snippet around the n-gram match in the original line."""
    line = line.strip()
    if len(line) <= max_len:
        return line
    idx = line.lower().find(ngram_text)
    if idx < 0:
        return line[:max_len].rstrip() + "…"
    half = max_len // 2
    start = max(0, idx - half)
    end = min(len(line), idx + len(ngram_text) + half)
    snippet = line[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(line):
        snippet = snippet + "…"
    return snippet


def _ngrams_in_line(
    tokens: list[str], sizes: Iterable[int]
) -> list[tuple[int, int, str]]:
    """Yield (size, start_index, joined_phrase) for every n-gram in the line.

    Skips n-grams that are 100% stop-words — they're noise like "of the and a".
    """
    out: list[tuple[int, int, str]] = []
    for size in sizes:
        if len(tokens) < size:
            continue
        for i in range(len(tokens) - size + 1):
            window = tokens[i : i + size]
            if all(t in STOP_WORDS for t in window):
                continue
            out.append((size, i, " ".join(window)))
    return out


def _read_chapter_drafts(book_path: Path) -> list[tuple[str, str]]:
    """Return [(chapter_slug, draft_text), ...] sorted by chapter folder name."""
    chapters_dir = book_path / "chapters"
    if not chapters_dir.is_dir():
        return []
    drafts: list[tuple[str, str]] = []
    for chapter_dir in sorted(chapters_dir.iterdir()):
        if not chapter_dir.is_dir():
            continue
        draft_path = chapter_dir / "draft.md"
        if not draft_path.exists():
            continue
        try:
            text = draft_path.read_text(encoding="utf-8")
        except OSError:
            continue
        drafts.append((chapter_dir.name, text))
    return drafts


def scan_repetitions(
    book_path: Path,
    ngram_sizes: Iterable[int] = DEFAULT_NGRAM_SIZES,
    min_occurrences: int = DEFAULT_MIN_OCCURRENCES,
    max_findings_per_category: int | None = None,
) -> dict[str, Any]:
    """Scan all chapter drafts of a book for repeated phrases.

    Returns a dict with `findings` (list[Finding-as-dict]), grouped counts,
    and basic metadata. The caller — typically the MCP tool — turns this into
    a Markdown report.
    """
    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return {
            "book_path": str(book_path),
            "chapters_scanned": 0,
            "findings": [],
            "summary": {},
        }

    # Map: phrase -> list[Occurrence]
    index: dict[str, list[Occurrence]] = defaultdict(list)
    sizes = tuple(ngram_sizes)

    for chapter_slug, raw_text in drafts:
        cleaned = _strip_markdown(raw_text)
        for line_no, original_line in enumerate(cleaned.splitlines(), start=1):
            stripped = original_line.strip()
            if not stripped:
                continue
            tokens = _tokenise(stripped)
            if len(tokens) < min(sizes):
                continue
            for _size, _i, phrase in _ngrams_in_line(tokens, sizes):
                snippet = _make_snippet(stripped, phrase)
                index[phrase].append(
                    Occurrence(chapter=chapter_slug, line=line_no, snippet=snippet)
                )

    # Per-length thresholds. Shorter n-grams need MORE occurrences to be
    # considered noteworthy, otherwise the report drowns in 4-grams that are
    # just common English connective tissue.
    length_thresholds = {
        4: max(min_occurrences, 5),
        5: max(min_occurrences, 3),
        6: max(min_occurrences, 2),
        7: max(min_occurrences, 2),
    }

    # Build findings, dropping sub-phrases that a longer accepted phrase
    # already explains. Tolerance of 1 catches the case where the shorter
    # phrase appears once outside the longer match.
    findings: list[Finding] = []
    sorted_phrases = sorted(index.keys(), key=lambda p: (-len(p.split()), p))
    seen_long: list[tuple[str, int]] = []  # (phrase, count) of accepted longer phrases

    for phrase in sorted_phrases:
        occs = index[phrase]
        size = len(phrase.split())
        threshold = length_thresholds.get(size, min_occurrences)
        if len(occs) < threshold:
            continue
        # Skip if a longer accepted phrase fully contains this one with a
        # comparable occurrence count (within +/- 1).
        if any(
            phrase in longer and abs(len(occs) - longer_count) <= 1
            for longer, longer_count in seen_long
        ):
            continue
        category = _classify(phrase, occs)
        severity = "high" if len(occs) >= 4 else "medium"
        findings.append(
            Finding(
                phrase=phrase,
                category=category,
                severity=severity,
                count=len(occs),
                occurrences=sorted(occs, key=lambda o: (o.chapter, o.line)),
            )
        )
        seen_long.append((phrase, len(occs)))

    # Sort: severity desc, count desc, phrase asc.
    severity_rank = {"high": 0, "medium": 1}
    findings.sort(key=lambda f: (severity_rank[f.severity], -f.count, f.phrase))

    if max_findings_per_category is not None:
        per_cat: dict[str, int] = defaultdict(int)
        capped: list[Finding] = []
        for f in findings:
            if per_cat[f.category] >= max_findings_per_category:
                continue
            per_cat[f.category] += 1
            capped.append(f)
        findings = capped

    # Summary
    summary: dict[str, dict[str, int]] = defaultdict(lambda: {"high": 0, "medium": 0})
    for f in findings:
        summary[f.category][f.severity] += 1

    return {
        "book_path": str(book_path),
        "chapters_scanned": len(drafts),
        "findings": [_finding_to_dict(f) for f in findings],
        "summary": {k: dict(v) for k, v in summary.items()},
    }


def _finding_to_dict(f: Finding) -> dict[str, Any]:
    d = asdict(f)
    return d


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

CATEGORY_LABELS = {
    "simile": "Similes & Metaphors",
    "blocking_tic": "Blocking Tics",
    "character_tell": "Character Tells",
    "sensory": "Sensory Repetitions",
    "structural": "Structural Tics",
    "signature_phrase": "Signature Phrases",
}

CATEGORY_ORDER = [
    "simile",
    "character_tell",
    "blocking_tic",
    "structural",
    "sensory",
    "signature_phrase",
]


def render_report(scan_result: dict[str, Any]) -> str:
    """Turn a scan result into a human-readable Markdown report."""
    findings = scan_result.get("findings", [])
    chapters_scanned = scan_result.get("chapters_scanned", 0)
    summary = scan_result.get("summary", {})

    lines: list[str] = []
    lines.append("# Repetition Report")
    lines.append("")
    lines.append(f"**Chapters scanned:** {chapters_scanned}")
    lines.append(f"**Findings:** {len(findings)}")
    lines.append("")

    if not findings:
        lines.append("No cross-chapter repetitions detected with the current thresholds.")
        lines.append("")
        return "\n".join(lines)

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Category | High (4+) | Medium (2-3) |")
    lines.append("|---|---:|---:|")
    for cat in CATEGORY_ORDER:
        if cat not in summary:
            continue
        s = summary[cat]
        lines.append(
            f"| {CATEGORY_LABELS[cat]} | {s.get('high', 0)} | {s.get('medium', 0)} |"
        )
    lines.append("")

    # Group findings by category
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in findings:
        by_category[f["category"]].append(f)

    for cat in CATEGORY_ORDER:
        items = by_category.get(cat, [])
        if not items:
            continue
        lines.append(f"## {CATEGORY_LABELS[cat]}")
        lines.append("")
        for f in items:
            severity_marker = "**HIGH**" if f["severity"] == "high" else "MEDIUM"
            lines.append(f"### `{f['phrase']}` — {f['count']}× ({severity_marker})")
            lines.append("")
            for occ in f["occurrences"]:
                lines.append(f"- **{occ['chapter']}** (line {occ['line']}): {occ['snippet']}")
            lines.append("")
            lines.append(_recommendation_for(f))
            lines.append("")
    return "\n".join(lines)


def _recommendation_for(finding: dict[str, Any]) -> str:
    """Short, category-aware revision recommendation."""
    cat = finding["category"]
    count = finding["count"]
    if cat == "simile":
        return (
            f"_Recommendation:_ Keep the strongest occurrence (usually the first) "
            f"and rewrite the other {count - 1} with fresh imagery rooted in the "
            f"current scene's senses."
        )
    if cat == "character_tell":
        return (
            "_Recommendation:_ A repeated body-part tell becomes invisible after "
            "the second use. Keep one or two, then vary the physical signal — "
            "a different body part, an action, or a verbal beat."
        )
    if cat == "blocking_tic":
        return (
            f"_Recommendation:_ Blocking beats lose impact when reused. Replace "
            f"{count - 1} occurrences with action that advances the scene or "
            f"reveals subtext."
        )
    if cat == "structural":
        return (
            f"_Recommendation:_ A structural tic ({count}×) trains the reader to "
            f"see the seams. Recast the weaker instances with different syntax."
        )
    if cat == "sensory":
        return (
            f"_Recommendation:_ Same sensory description in {count} places — "
            f"vary at least {count - 1} of them so each scene has its own texture."
        )
    return (
        f"_Recommendation:_ Decide which occurrence is most necessary; cut or "
        f"rewrite the other {count - 1}."
    )
