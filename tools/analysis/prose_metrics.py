"""Deterministic prose measurements for the chapter-humanizer.

Measures the mechanical signals of machine-written prose that a model reading
a draft cannot count reliably: sentence-length variation, dash density,
hedge-word density, runs of identical sentence openers, and invisible
characters. Pure stdlib, no book-state I/O.

Narration and dialogue are measured separately. Dashes inside quoted speech
(abrupt interruptions, per ``reference/craft/dialog-craft.md``) are legitimate
and never count toward the narration dash density.

``draft.md`` carries no explicit scene marker. Segments are split only on
explicit horizontal rules (``---``, ``***``, ``* * *``); without one, the whole
chapter is a single segment and ``scene_breaks_found`` is ``False``.

The limits below are provisional defaults, not calibrated on published prose.
Callers (and author profiles) can override the dash limit.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from typing import Any

# Provisional defaults, checked against 34 reviewed chapters of one book
# (Firelight): narration dashes per 1k words ran 5.2-18.5 (median 12.5) and
# narration sentence-length variation 0.80-1.24. No human-written reference
# corpus was available, so these are not a measured human baseline — authors
# override the dash limit in profile.md.
#
# Narration dashes (em dash, spaced en dash) per 1,000 narration words.
DEFAULT_DASH_PER_1K_LIMIT = 8.0
# Narration sentence-length variation below this reads as uniform. Only an
# extreme chapter trips it; prose that varies at all sits far above.
UNIFORM_BURSTINESS_BELOW = 0.35
MIN_SENTENCES_FOR_BURSTINESS = 5
# Runs of 3 identical openers fired ~3x per chapter on the same book
# (107 of 143 runs); 4+ is about one per chapter.
OPENER_RUN_MIN = 4
HEDGE_SEGMENT_MIN = 3

_HR_LINE_RE = re.compile(r"^\s*(?:[*_-]\s*){3,}$")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s")
# Quoted speech in the styles fiction actually uses: straight and curly double
# quotes, German „…“, guillemets »…« / «…», curly single ‘…’, and straight
# single '…'. A single quote only opens speech when it does not follow a word
# character (so don't / dogs' are not quotes) and only closes it when no word
# character follows. Speech that spans paragraphs has no closing quote on its
# first line and is not recognised.
_DIALOGUE_RE = re.compile(
    r'"[^"\n]{2,}?"'
    r"|“[^“”\n]{2,}?”"
    r"|„[^„“”\n]{2,}?[“”]"
    r"|»[^»«\n]{2,}?«"
    r"|«[^«»\n]{2,}?»"
    r"|‘.{2,}?’(?!\w)"
    r"|(?<![\w’'])'.{2,}?'(?!\w)"
)
_MD_FORMAT_RE = re.compile(r"[*_`~]")
_WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")
# Honorifics and titles whose period does not end a sentence.
_ABBREVIATIONS = ("Mr", "Mrs", "Ms", "Dr", "Prof", "Sr", "Jr", "St", "Mt", "vs", "Capt", "Col", "Gen", "Lt", "Sgt")
_SENTENCE_SPLIT_RE = re.compile(
    "".join(rf"(?<!\b{a}\.)" for a in _ABBREVIATIONS) + r"(?<=[.!?\u2026])[\"'\u201d\u2019\u201c\u00bb\u00ab)]*\s+"
)
_DASH_RE = re.compile(r"—|(?<=\s)–(?=\s)")
_HEDGE_RE = re.compile(r"\b(?:seemed|appeared to|as if|might have)\b", re.IGNORECASE)
_NBSP_CHARS = "\u00a0\u202f\u2007"
_MASK = "\x00"
# A closing quote preceded by one of these ends the sentence the speech sits in.
_SPEECH_TERMINALS = ".!?…—–"


def _mask_span(m: re.Match[str]) -> str:
    span = m.group(0)
    if span[-2] in _SPEECH_TERMINALS:
        # Keep a sentence boundary visible to the sentence splitter: `"Hi." He sat`
        # is two sentences, `"Hi," he said.` is one.
        return _MASK * (len(span) - 2) + "." + span[-1]
    return _MASK * len(span)


def _mask_dialogue(line: str) -> str:
    """Replace each quoted span with same-length mask characters."""
    return _DIALOGUE_RE.sub(_mask_span, line)


def is_invisible_char(char: str) -> bool:
    """Format characters, line/paragraph separators, and no-break spaces."""
    return unicodedata.category(char) in ("Cf", "Zl", "Zp") or char in _NBSP_CHARS


def split_lines(text: str) -> list[str]:
    """Split on ``\\n`` only, so line numbers match an editor's (``str.splitlines``
    also breaks on U+2028, U+0085 and form feeds)."""
    return [line.rstrip("\r") for line in text.split("\n")]


def _dialogue_spans(line: str) -> list[str]:
    return [m.group(0) for m in _DIALOGUE_RE.finditer(line)]


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def _content_lines(text: str) -> list[tuple[int, str]]:
    """Return ``(line_no, line)`` for every line outside frontmatter."""
    lines = split_lines(text)
    start = 0
    if lines and lines[0].lstrip("\ufeff").strip() == "---":
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                start = idx + 1
                break
    return [(i + 1, lines[i]) for i in range(start, len(lines))]


def split_segments(text: str) -> tuple[list[list[tuple[int, str]]], bool]:
    segments: list[list[tuple[int, str]]] = [[]]
    found = False
    for line_no, line in _content_lines(text):
        if _HR_LINE_RE.match(line):
            found = True
            segments.append([])
            continue
        segments[-1].append((line_no, line))
    non_empty = [s for s in segments if any(ln.strip() for _, ln in s)]
    return (non_empty or [[]]), found


def _opener_runs(sentences: list[tuple[int, str | None]]) -> list[dict[str, Any]]:
    """Find runs of 3+ consecutive sentences sharing the same first word.

    ``None`` marks a dialogue-led sentence: it is never an opener and breaks a run.
    """
    runs: list[dict[str, Any]] = []
    i = 0
    while i < len(sentences):
        line_no, opener = sentences[i]
        if opener is None:
            i += 1
            continue
        j = i
        while j + 1 < len(sentences) and sentences[j + 1][1] == opener:
            j += 1
        length = j - i + 1
        if length >= OPENER_RUN_MIN:
            runs.append({"line": line_no, "opener": opener, "run": length})
        i = j + 1
    return runs


def _segment_metrics(lines: list[tuple[int, str]]) -> dict[str, Any]:
    narration_words = 0
    dialogue_words = 0
    dash_count = 0
    dialogue_dash_count = 0
    dash_lines: list[int] = []
    hedge_lines: list[int] = []
    pure_sentence_lengths: list[int] = []
    opener_sentences: list[tuple[int, str | None]] = []
    content_line_nos: list[int] = []

    for line_no, raw in lines:
        if not raw.strip() or _HEADING_RE.match(raw):
            continue
        content_line_nos.append(line_no)
        line = _MD_FORMAT_RE.sub("", raw)
        masked = _mask_dialogue(line)
        narration = masked.replace(_MASK, " ")

        narration_words += len(_words(narration))
        for span in _dialogue_spans(line):
            dialogue_words += len(_words(span))
            dialogue_dash_count += len(_DASH_RE.findall(span))

        n_dashes = len(_DASH_RE.findall(narration))
        if n_dashes:
            dash_count += n_dashes
            dash_lines.extend([line_no] * n_dashes)

        n_hedges = len(_HEDGE_RE.findall(narration))
        if n_hedges:
            hedge_lines.extend([line_no] * n_hedges)

        for sentence in _SENTENCE_SPLIT_RE.split(masked.strip()):
            sentence = sentence.strip()
            if not sentence:
                continue
            if sentence.startswith(_MASK):
                opener_sentences.append((line_no, None))
                continue
            words = _words(sentence.replace(_MASK, " "))
            if not words:
                continue
            opener_sentences.append((line_no, words[0].lower().replace("’", "'")))
            if _MASK not in sentence:
                pure_sentence_lengths.append(len(words))

    cv: float | None = None
    if len(pure_sentence_lengths) >= MIN_SENTENCES_FOR_BURSTINESS:
        mean = statistics.mean(pure_sentence_lengths)
        cv = round(statistics.pstdev(pure_sentence_lengths) / mean, 3) if mean else 0.0

    per_1k = round(dash_count * 1000 / narration_words, 2) if narration_words else 0.0
    return {
        "first_line": content_line_nos[0] if content_line_nos else None,
        "last_line": content_line_nos[-1] if content_line_nos else None,
        "narration_words": narration_words,
        "dialogue_words": dialogue_words,
        "narration_sentences": len(pure_sentence_lengths),
        "burstiness_cv": cv,
        "dash_count": dash_count,
        "dialogue_dash_count": dialogue_dash_count,
        "dash_per_1k": per_1k,
        "dash_lines": dash_lines,
        "hedge_count": len(hedge_lines),
        "hedge_lines": hedge_lines,
        "repeated_openers": _opener_runs(opener_sentences),
        "_sentence_lengths": pure_sentence_lengths,
    }


def _invisible(text: str) -> tuple[int, list[int]]:
    count = 0
    lines: list[int] = []
    for line_no, line in enumerate(split_lines(text), start=1):
        n = sum(1 for c in line if is_invisible_char(c))
        if n:
            count += n
            lines.append(line_no)
    return count, lines


def analyse_draft(text: str) -> dict[str, Any]:
    """Measure a chapter draft. Returns per-segment and chapter-level metrics."""
    groups, found = split_segments(text)
    segments = [_segment_metrics(g) for g in groups]

    all_lengths = [n for s in segments for n in s["_sentence_lengths"]]
    cv: float | None = None
    if len(all_lengths) >= MIN_SENTENCES_FOR_BURSTINESS:
        mean = statistics.mean(all_lengths)
        cv = round(statistics.pstdev(all_lengths) / mean, 3) if mean else 0.0

    narration_words = sum(s["narration_words"] for s in segments)
    dash_count = sum(s["dash_count"] for s in segments)
    invisible_chars, invisible_lines = _invisible(text)
    openers = [r for s in segments for r in s["repeated_openers"]]

    for s in segments:
        del s["_sentence_lengths"]

    chapter = {
        "narration_words": narration_words,
        "dialogue_words": sum(s["dialogue_words"] for s in segments),
        "narration_sentences": len(all_lengths),
        "burstiness_cv": cv,
        "dash_count": dash_count,
        "dialogue_dash_count": sum(s["dialogue_dash_count"] for s in segments),
        "dash_per_1k": round(dash_count * 1000 / narration_words, 2) if narration_words else 0.0,
        "dash_lines": [n for s in segments for n in s["dash_lines"]],
        "hedge_count": sum(s["hedge_count"] for s in segments),
        "repeated_openers": openers,
        "invisible_chars": invisible_chars,
        "invisible_lines": invisible_lines,
    }
    return {"scene_breaks_found": found, "segments": segments, "chapter": chapter}


def compare_metrics(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Before/after view of the metrics the humanizer is meant to move."""
    b, a = before["chapter"], after["chapter"]
    return {
        "burstiness_cv": {"before": b["burstiness_cv"], "after": a["burstiness_cv"]},
        "dash_count": {"before": b["dash_count"], "after": a["dash_count"]},
        "dash_per_1k": {"before": b["dash_per_1k"], "after": a["dash_per_1k"]},
        "hedge_count": {"before": b["hedge_count"], "after": a["hedge_count"]},
        "repeated_opener_runs": {
            "before": len(b["repeated_openers"]),
            "after": len(a["repeated_openers"]),
        },
        "invisible_chars": {"before": b["invisible_chars"], "after": a["invisible_chars"]},
    }
