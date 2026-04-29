"""Per-category scanners for the manuscript checker (fiction-side).

Each ``_scan_*`` function takes a book_path, reads chapter drafts via
``text_utils._read_chapter_drafts``, and returns a list of Findings.

Memoir-specific scanners live in ``memoir_patterns.py``.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from tools.analysis.callback_validator import verify_callbacks as _verify_callbacks
from tools.analysis.manuscript.metadata import _read_allowed_repetitions, _read_snapshot_threshold
from tools.analysis.manuscript.text_utils import (
    DIALOGUE_RE as _DIALOGUE_RE,
    _make_snippet,
    _ngrams_in_line,
    _read_chapter_drafts,
    _strip_dialogue,
    _strip_markdown,
    _tokenise,
)
from tools.analysis.manuscript.types import Finding, Occurrence
from tools.analysis.manuscript.vocabularies import (
    ACTION_VERBS_FALLBACK,
    ADVERB_HIGH_PER_1K,
    ADVERB_MEDIUM_PER_1K,
    CALLBACK_DEFERRED_SILENCE,
    CLICHE_PHRASES,
    FILTER_WORD_HIGH_PER_1K,
    FILTER_WORD_MEDIUM_PER_1K,
    LY_EXCLUSIONS,
    QUESTION_OPENER_CONTRACTIONS,
    QUESTION_OPENERS,
)

# Plugin root: tools/analysis/manuscript/scanners.py is three levels deep.
_PLUGIN_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Filter words — POV distancing verbs
# ---------------------------------------------------------------------------

FILTER_WORD_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("felt", re.compile(r"\b(?:felt)\b", re.IGNORECASE)),
    ("noticed", re.compile(r"\bnoticed\b", re.IGNORECASE)),
    ("saw that", re.compile(r"\bsaw\s+(?:that|how|the\s+way)\b", re.IGNORECASE)),
    ("heard that", re.compile(r"\bheard\s+(?:that|how|the)\b", re.IGNORECASE)),
    ("seemed", re.compile(r"\bseemed\b", re.IGNORECASE)),
    ("appeared", re.compile(r"\bappeared\s+to\b", re.IGNORECASE)),
    ("realized", re.compile(r"\brealized\b", re.IGNORECASE)),
    ("wondered", re.compile(r"\bwondered\b", re.IGNORECASE)),
    ("watched", re.compile(r"\bwatched\b", re.IGNORECASE)),
    ("observed", re.compile(r"\bobserved\b", re.IGNORECASE)),
    ("thought that", re.compile(r"\bthought\s+(?:that|of)\b", re.IGNORECASE)),
    ("decided", re.compile(r"\bdecided\b", re.IGNORECASE)),
    ("knew that", re.compile(r"\bknew\s+(?:that|how)\b", re.IGNORECASE)),
    ("remembered", re.compile(r"\bremembered\b", re.IGNORECASE)),
    ("sensed", re.compile(r"\bsensed\b", re.IGNORECASE)),
)


def _scan_filter_words(book_path: Path) -> list[Finding]:
    """Flag POV filter-word overuse per chapter."""
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
        per_word_counts: dict[str, int] = defaultdict(int)
        for line_no, line in enumerate(cleaned.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            narration = _strip_dialogue(stripped)
            if not narration.strip():
                continue
            for label, pattern in FILTER_WORD_PATTERNS:
                for m in pattern.finditer(narration):
                    per_word_counts[label] += 1
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
        if density < FILTER_WORD_MEDIUM_PER_1K:
            continue
        severity = "high" if density >= FILTER_WORD_HIGH_PER_1K else "medium"

        top = sorted(per_word_counts.items(), key=lambda kv: -kv[1])[:3]
        top_str = ", ".join(f"{word}×{n}" for word, n in top)
        phrase = f"{chapter_slug}: {top_str} ({density:.1f}/1k words)"

        findings.append(
            Finding(
                phrase=phrase,
                category="filter_word",
                severity=severity,
                count=len(occurrences),
                occurrences=occurrences[:20],
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Adverb density
# ---------------------------------------------------------------------------

_LY_WORD_RE = re.compile(r"\b([a-z]+ly)\b", re.IGNORECASE)


def _scan_adverb_density(book_path: Path) -> list[Finding]:
    """Flag chapters with heavy ``-ly`` adverb density."""
    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    findings: list[Finding] = []
    for chapter_slug, raw_text in drafts:
        cleaned = _strip_markdown(raw_text)
        tokens = _tokenise(cleaned)
        word_count = len(tokens)
        if word_count < 200:
            continue

        adverb_counts: dict[str, int] = defaultdict(int)
        occurrences: list[Occurrence] = []
        for line_no, line in enumerate(cleaned.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            narration = _strip_dialogue(stripped)
            for m in _LY_WORD_RE.finditer(narration):
                word = m.group(1).lower()
                if word in LY_EXCLUSIONS:
                    continue
                if len(word) < 5:
                    continue
                adverb_counts[word] += 1
                if len(occurrences) < 20:
                    occurrences.append(
                        Occurrence(
                            chapter=chapter_slug,
                            line=line_no,
                            snippet=_make_snippet(stripped, word),
                        )
                    )

        total = sum(adverb_counts.values())
        if total == 0:
            continue
        density = (total / word_count) * 1000.0
        if density < ADVERB_MEDIUM_PER_1K:
            continue
        severity = "high" if density >= ADVERB_HIGH_PER_1K else "medium"

        top = sorted(adverb_counts.items(), key=lambda kv: -kv[1])[:5]
        top_str = ", ".join(f"{w}×{n}" for w, n in top)
        phrase = f"{chapter_slug}: {top_str} ({density:.1f}/1k words, {total} total)"

        findings.append(
            Finding(
                phrase=phrase,
                category="adverb_density",
                severity=severity,
                count=total,
                occurrences=occurrences,
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Cliché detection
# ---------------------------------------------------------------------------

_ENTRY_RE = re.compile(
    r"^\s*-\s+(.+?)(?:\s+\(severity:\s+(high|medium)\))?(?:\s+—.*)?$",
    re.IGNORECASE,
)


def _load_cliche_banlist(
    plugin_root: Path,
    genres: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Load the cliché banlist from reference/craft/cliche-banlist.md.

    Falls back to the hardcoded ``CLICHE_PHRASES`` constant (all severity
    'high') when the file is missing. Each genre in ``genres`` merges its
    cliche-banlist-{genre}.md on top; missing files are silently skipped.
    """
    craft_dir = plugin_root / "reference" / "craft"

    def _parse_file(path: Path) -> list[tuple[str, str]]:
        if not path.is_file():
            return []
        entries: list[tuple[str, str]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _ENTRY_RE.match(line)
            if not m:
                continue
            phrase = m.group(1).strip()
            severity = (m.group(2) or "high").lower()
            if phrase and len(phrase) > 2:
                entries.append((phrase, severity))
        return entries

    base = _parse_file(craft_dir / "cliche-banlist.md")
    if not base:
        base = [(p, "high") for p in CLICHE_PHRASES]

    if genres:
        seen = {p for p, _ in base}
        for genre_slug in genres:
            for phrase, severity in _parse_file(craft_dir / f"cliche-banlist-{genre_slug}.md"):
                if phrase not in seen:
                    base.append((phrase, severity))
                    seen.add(phrase)

    return base


def _scan_cliches(
    book_path: Path,
    plugin_root: Path | None = None,
    genres: list[str] | None = None,
) -> list[Finding]:
    """Flag hits from the curated cliché banlist."""
    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    root = plugin_root if plugin_root is not None else _PLUGIN_ROOT
    banlist = _load_cliche_banlist(root, genres=genres)
    patterns = [
        (phrase, severity, re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)) for phrase, severity in banlist
    ]

    findings: list[Finding] = []
    for phrase, severity, pattern in patterns:
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
                    phrase=phrase,
                    category="cliche",
                    severity=severity,
                    count=len(occurrences),
                    occurrences=sorted(occurrences, key=lambda o: (o.chapter, o.line)),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Question-as-statement
# ---------------------------------------------------------------------------


def _scan_question_as_statement(book_path: Path) -> list[Finding]:
    """Flag dialogue that starts with a question word but ends with a period."""
    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    occurrences: list[Occurrence] = []
    for chapter_slug, raw_text in drafts:
        cleaned = _strip_markdown(raw_text)
        for line_no, line in enumerate(cleaned.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            for m in _DIALOGUE_RE.finditer(stripped):
                dialogue = (m.group(1) or m.group(2) or "").strip()
                if len(dialogue) < 2:
                    continue
                last = dialogue[-1]
                if last != ".":
                    continue
                if dialogue.endswith("..") or dialogue.endswith("…"):
                    continue
                first_tokens = _tokenise(dialogue)
                if not first_tokens:
                    continue
                first = first_tokens[0]
                if first in QUESTION_OPENERS or first in QUESTION_OPENER_CONTRACTIONS:
                    snippet = _make_snippet(stripped, m.group(0).lower())
                    occurrences.append(
                        Occurrence(
                            chapter=chapter_slug,
                            line=line_no,
                            snippet=snippet,
                        )
                    )

    if not occurrences:
        return []

    severity = "high" if len(occurrences) >= 5 else "medium"
    return [
        Finding(
            phrase='Dialogue Q-word ending with "." instead of "?"',
            category="question_as_statement",
            severity=severity,
            count=len(occurrences),
            occurrences=sorted(occurrences, key=lambda o: (o.chapter, o.line))[:40],
        )
    ]


# ---------------------------------------------------------------------------
# Sentence-level repetition (8–15 word n-grams)
# ---------------------------------------------------------------------------

DEFAULT_SENTENCE_NGRAM_SIZES = tuple(range(8, 16))


def _scan_sentence_repetitions(
    book_path: Path,
    min_length: int = 8,
    max_length: int = 15,
    min_occurrences: int = 2,
) -> list[Finding]:
    """Detect repeated whole-sentence-level phrases (8-15 word n-grams)."""
    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    allowed = _read_allowed_repetitions(book_path)
    sizes = tuple(range(min_length, max_length + 1))
    index: dict[str, list[Occurrence]] = defaultdict(list)

    for chapter_slug, raw_text in drafts:
        cleaned = _strip_markdown(raw_text)
        for line_no, original_line in enumerate(cleaned.splitlines(), start=1):
            stripped = original_line.strip()
            if not stripped:
                continue
            tokens = _tokenise(stripped)
            if len(tokens) < min_length:
                continue
            for _size, _i, phrase in _ngrams_in_line(tokens, sizes):
                index[phrase].append(
                    Occurrence(
                        chapter=chapter_slug,
                        line=line_no,
                        snippet=_make_snippet(stripped, phrase),
                    )
                )

    findings: list[Finding] = []
    for phrase, occs in index.items():
        if len(occs) < min_occurrences:
            continue
        if any(phrase in allowed_phrase for allowed_phrase in allowed):
            continue
        findings.append(
            Finding(
                phrase=phrase,
                category="sentence_repetition",
                severity="high",
                count=len(occs),
                occurrences=sorted(occs, key=lambda o: (o.chapter, o.line)),
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Snapshot detector — static description blocks
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[a-zA-Z\d][.!?])\s+")
_DIALOG_CHAR_RE = re.compile(r'["“”]')


def _load_action_verbs(plugin_root: Path) -> frozenset[str]:
    """Load the action verb list from reference/craft/action-verbs.md."""
    path = plugin_root / "reference" / "craft" / "action-verbs.md"
    if not path.is_file():
        return ACTION_VERBS_FALLBACK
    verbs: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip().lstrip("- ").strip()
        if stripped and not stripped.startswith("#") and len(stripped) >= 2:
            verbs.add(stripped.lower())
    return frozenset(verbs) if verbs else ACTION_VERBS_FALLBACK


def _sentence_has_action(sentence: str, action_verbs: frozenset[str]) -> bool:
    """Return True if the sentence contains at least one action verb."""
    tokens = set(_tokenise(sentence))
    for verb in action_verbs:
        if verb in tokens:
            return True
        if f"{verb}s" in tokens or f"{verb}ed" in tokens or f"{verb}ing" in tokens:
            return True
        if verb.endswith("e") and f"{verb[:-1]}ing" in tokens:
            return True
        if len(verb) >= 3 and verb[-1] == verb[-2] and f"{verb}ing" in tokens:
            return True
    return False


def _scan_snapshots(
    book_path: Path,
    plugin_root: Path | None = None,
) -> list[Finding]:
    """Flag static description blocks with no action verbs and no dialog."""
    drafts = _read_chapter_drafts(book_path)
    if not drafts:
        return []

    threshold = _read_snapshot_threshold(book_path)
    root = plugin_root if plugin_root is not None else _PLUGIN_ROOT
    action_verbs = _load_action_verbs(root)

    findings: list[Finding] = []

    for chapter_slug, raw_text in drafts:
        cleaned = _strip_markdown(raw_text)
        lines = cleaned.splitlines()

        paragraphs: list[tuple[int, str]] = []
        para_start = 0
        para_lines: list[str] = []
        for line_no, line in enumerate(lines, start=1):
            if line.strip():
                if not para_lines:
                    para_start = line_no
                para_lines.append(line)
            else:
                if para_lines:
                    paragraphs.append((para_start, " ".join(para_lines)))
                    para_lines = []
        if para_lines:
            paragraphs.append((para_start, " ".join(para_lines)))

        for para_start_line, para_text in paragraphs:
            sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(para_text) if s.strip()]
            if len(sentences) < threshold:
                continue

            streak: list[str] = []
            streak_start = para_start_line

            def _flush_streak(streak: list[str], start: int) -> None:
                if len(streak) >= threshold:
                    snippet = " ".join(streak)[:200].rstrip()
                    if len(" ".join(streak)) > 200:
                        snippet += "…"
                    findings.append(
                        Finding(
                            phrase=f"snapshot:{chapter_slug}:{start}",
                            category="snapshot",
                            severity="medium",
                            count=len(streak),
                            occurrences=[
                                Occurrence(
                                    chapter=chapter_slug,
                                    line=start,
                                    snippet=snippet,
                                )
                            ],
                        )
                    )

            for sent in sentences:
                if not sent:
                    continue
                if _DIALOG_CHAR_RE.search(sent) or _sentence_has_action(sent, action_verbs):
                    _flush_streak(streak, streak_start)
                    streak = []
                else:
                    if not streak:
                        streak_start = para_start_line
                    streak.append(sent)

            _flush_streak(streak, streak_start)

    return findings


# ---------------------------------------------------------------------------
# Callback register scanner
# ---------------------------------------------------------------------------


def _scan_callbacks(book_path: Path) -> list[Finding]:
    """Surface broken callback promises as manuscript findings."""
    claudemd_path = book_path / "CLAUDE.md"
    if not claudemd_path.exists():
        return []

    claudemd_text = claudemd_path.read_text(encoding="utf-8")
    result = _verify_callbacks(book_path, claudemd_text)

    findings: list[Finding] = []

    for entry in result.get("potentially_dropped", []):
        warning = entry.get("warning", "no appearance found")
        occ = Occurrence(chapter="CLAUDE.md", line=0, snippet=warning)
        findings.append(
            Finding(
                phrase=entry["name"],
                category="callback_dropped",
                severity="high",
                count=entry.get("chapters_since", 0),
                occurrences=[occ],
            )
        )

    for entry in result.get("deferred", []):
        chapters_since = entry.get("chapters_since", 0)
        if chapters_since <= CALLBACK_DEFERRED_SILENCE:
            continue
        snippet = f"not appeared in {chapters_since} drafted chapters"
        occ = Occurrence(chapter="CLAUDE.md", line=0, snippet=snippet)
        findings.append(
            Finding(
                phrase=entry["name"],
                category="callback_deferred",
                severity="medium",
                count=chapters_since,
                occurrences=[occ],
            )
        )

    return findings


__all__ = [
    "FILTER_WORD_PATTERNS",
    "_load_action_verbs",
    "_load_cliche_banlist",
    "_scan_adverb_density",
    "_scan_callbacks",
    "_scan_cliches",
    "_scan_filter_words",
    "_scan_question_as_statement",
    "_scan_sentence_repetitions",
    "_scan_snapshots",
    "_strip_dialogue",
]
